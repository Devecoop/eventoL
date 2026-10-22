# pylint: disable=redefined-outer-name,unused-argument
from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.utils import timezone

from payments import domain
from payments.models import Order, Payment, SellerAccountNotConfiguredError
from payments.services import MercadoPagoError
from payments.signals import order_paid, order_refunded

from .conftest import mp_payment

pytestmark = pytest.mark.django_db

BUYER = domain.Buyer(name='Ana Pez', email='ana@example.com', phone='1122334455')


def attendees(quantity):
    return [
        domain.AttendeeData(first_name='Ana', last_name=f'Pez {number}', dni=f'3000000{number}')
        for number in range(quantity)
    ]


@pytest.fixture
def order(event, seller, preference):
    return domain.create_order(event, BUYER, attendees(2), '1000', quota=10)


@pytest.fixture
def paid_receiver():
    receiver = mock.Mock()
    order_paid.connect(receiver)
    yield receiver
    order_paid.disconnect(receiver)


@pytest.fixture
def refunded_receiver():
    receiver = mock.Mock()
    order_refunded.connect(receiver)
    yield receiver
    order_refunded.disconnect(receiver)


def test_marketplace_fee_is_rounded_to_cents():
    assert domain.calculate_marketplace_fee(Decimal('1001')) == Decimal('30.03')


def test_create_order(order, seller, preference):
    assert order.status == Order.Status.PENDING
    assert order.quantity == 2
    assert order.total == Decimal('2000.00')
    assert order.marketplace_fee == Decimal('60.00')
    assert order.seller == seller
    assert order.items.count() == 2
    assert order.reserved_until > timezone.now() + timedelta(minutes=29)
    assert order.preference_id == 'pref-1'
    assert order.init_point == 'https://mp.test/checkout'
    preference.assert_called_once_with(order, 'seller-access-token')


def test_create_order_requires_a_seller(event, preference):
    with pytest.raises(SellerAccountNotConfiguredError):
        domain.create_order(event, BUYER, attendees(1), '1000')


@pytest.mark.parametrize(('price', 'quantity'), [('0', 1), ('1000', 0)])
def test_create_order_validates_price_and_attendees(event, seller, preference, price, quantity):
    with pytest.raises(domain.InvalidOrderError):
        domain.create_order(event, BUYER, attendees(quantity), price)


def test_pending_orders_reserve_quota(event, seller, preference):
    domain.create_order(event, BUYER, attendees(2), '1000', quota=3)
    with pytest.raises(domain.QuotaExceededError):
        domain.create_order(event, BUYER, attendees(2), '1000', quota=3)


def test_expired_reservations_free_the_quota(event, seller, preference):
    first = domain.create_order(event, BUYER, attendees(2), '1000', quota=3)
    Order.objects.filter(pk=first.pk).update(reserved_until=timezone.now() - timedelta(minutes=1))
    domain.create_order(event, BUYER, attendees(1), '1000', quota=3)
    assert domain.available_quota(event, 3) == 2


def test_mercado_pago_error_releases_the_reservation(event, seller):
    with (
        mock.patch('payments.services.create_preference', side_effect=MercadoPagoError('down')),
        pytest.raises(MercadoPagoError),
    ):
        domain.create_order(event, BUYER, attendees(2), '1000', quota=2)
    assert domain.available_quota(event, 2) == 2


def test_approved_payment_approves_the_order(
    order, paid_receiver, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        domain.apply_payment(mp_payment(order))
    order.refresh_from_db()
    assert order.status == Order.Status.APPROVED
    assert order.paid_at is not None
    paid_receiver.assert_called_once()
    assert paid_receiver.call_args.kwargs['order'] == order


def test_applying_the_same_payment_twice_is_idempotent(
    order, paid_receiver, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        domain.apply_payment(mp_payment(order))
        domain.apply_payment(mp_payment(order))
    assert Payment.objects.filter(order=order).count() == 1
    paid_receiver.assert_called_once()


@pytest.mark.parametrize(
    'overrides',
    [{'transaction_amount': 1.0}, {'currency_id': 'USD'}, {'collector_id': 999}],
)
def test_payment_not_matching_the_order_does_not_approve_it(order, paid_receiver, overrides):
    domain.apply_payment(mp_payment(order, **overrides))
    order.refresh_from_db()
    assert order.status == Order.Status.PENDING
    assert order.payments.get().validation_error
    paid_receiver.assert_not_called()


def test_rejected_attempt_then_approved_payment(order):
    domain.apply_payment(mp_payment(order, payment_id='1', status='rejected'))
    order.refresh_from_db()
    assert order.status == Order.Status.PENDING
    domain.apply_payment(mp_payment(order, payment_id='2'))
    order.refresh_from_db()
    assert order.status == Order.Status.APPROVED
    assert order.payments.count() == 2


def test_late_payment_over_quota(
    event, seller, preference, paid_receiver, django_capture_on_commit_callbacks
):
    late = domain.create_order(event, BUYER, attendees(2), '1000', quota=2)
    Order.objects.filter(pk=late.pk).update(reserved_until=timezone.now() - timedelta(minutes=1))
    other = domain.create_order(event, BUYER, attendees(2), '1000', quota=2)
    with django_capture_on_commit_callbacks(execute=True):
        domain.apply_payment(mp_payment(other, payment_id='1'))
        domain.apply_payment(mp_payment(late, payment_id='2'))
    late.refresh_from_db()
    assert late.status == Order.Status.APPROVED_OVER_QUOTA
    # Only the order that fits the quota issues tickets
    paid_receiver.assert_called_once()
    assert paid_receiver.call_args.kwargs['order'] == other


def test_refund_of_a_paid_order(order, refunded_receiver, django_capture_on_commit_callbacks):
    domain.apply_payment(mp_payment(order))
    with django_capture_on_commit_callbacks(execute=True):
        domain.apply_payment(mp_payment(order, status='refunded'))
    order.refresh_from_db()
    assert order.status == Order.Status.REFUNDED
    refunded_receiver.assert_called_once()


def test_payment_of_an_unknown_order_is_ignored(order):
    assert domain.apply_payment(mp_payment(order, external_reference='not-an-order')) is None
    assert domain.apply_payment({**mp_payment(order), 'external_reference': None}) is None
    assert not Payment.objects.exists()


def test_reconcile_pending_orders(order):
    with mock.patch(
        'payments.services.search_payments', return_value=[mp_payment(order)]
    ) as search:
        assert domain.reconcile_pending_orders() == 1
    search.assert_called_once_with(str(order.id), 'seller-access-token')
    order.refresh_from_db()
    assert order.status == Order.Status.APPROVED


def test_refresh_seller_tokens(seller):
    seller.expires_at = timezone.now() + timedelta(days=5)
    seller.save()
    tokens = {'access_token': 'new-access', 'refresh_token': 'new-refresh', 'expires_in': 15552000}
    with mock.patch('payments.services.refresh_access_token', return_value=tokens):
        domain.refresh_seller_tokens()
    seller.refresh_from_db()
    assert seller.access_token == 'new-access'
    assert seller.refresh_token == 'new-refresh'
    assert not seller.expires_soon()
