"""Order lifecycle: creation with quota reservation, payment application and reconciliation.

Rules:
- An order is created ``pending`` and reserves its tickets for ``MP_RESERVATION_MINUTES``.
- Mercado Pago payments are fetched from the API (never trusted from the notification body)
  and applied idempotently: the same payment can be applied any number of times.
- Order status only moves forward: pending -> approved | approved_over_quota -> refunded.
- A payment that does not match the order (amount, currency, collector) is stored with a
  ``validation_error`` and never approves the order.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from manager.models import Event
from payments import services
from payments.models import Order, OrderItem, Payment, SellerAccount, WebhookEvent
from payments.signals import order_paid, order_refunded

logger = logging.getLogger(__name__)

CENTS = Decimal('0.01')
REFUND_STATUSES = ('refunded', 'charged_back')
RECONCILIATION_DAYS = 7


class QuotaExceededError(Exception):
    pass


class InvalidOrderError(ValueError):
    pass


@dataclass
class Buyer:
    name: str
    email: str
    phone: str
    user: object = None


@dataclass
class AttendeeData:
    first_name: str
    last_name: str
    dni: str
    email: str = ''


def calculate_marketplace_fee(total):
    return (Decimal(total) * settings.MP_MARKETPLACE_FEE_PERCENT / 100).quantize(
        CENTS, rounding=ROUND_HALF_UP
    )


def used_quota(event, now=None, exclude_order=None):
    """Tickets of the event that are paid or reserved by a pending order."""
    orders = Order.objects.holding_quota(now).filter(event=event)
    if exclude_order is not None:
        orders = orders.exclude(pk=exclude_order.pk)
    return OrderItem.objects.filter(order__in=orders).aggregate(total=Count('id'))['total']


def available_quota(event, quota, now=None, exclude_order=None):
    """Remaining tickets, or None when the event has no quota."""
    if quota is None:
        return None
    return max(quota - used_quota(event, now, exclude_order), 0)


def create_order(event, buyer, attendees, unit_price, quota=None):  # noqa: PLR0913
    """Create a pending order, reserve its tickets and create the Mercado Pago preference.

    ``unit_price`` and ``quota`` are given by the caller (``Event.ticket_price`` and
    ``Event.ticket_quota`` in the purchase view).
    Raises QuotaExceededError, InvalidOrderError, SellerAccountNotConfiguredError or
    services.MercadoPagoError.
    """
    unit_price = Decimal(unit_price).quantize(CENTS)
    if not attendees:
        raise InvalidOrderError('An order needs at least one attendee')
    if unit_price <= 0:
        raise InvalidOrderError('The ticket price must be greater than zero')
    seller = SellerAccount.for_event(event)
    total = unit_price * len(attendees)

    with transaction.atomic():
        # Lock the event row so two buyers cannot take the last tickets at the same time.
        # _base_manager avoids the annotations of EventManager (GROUP BY cannot be locked).
        Event._base_manager.select_for_update().filter(pk=event.pk).first()  # pylint: disable=protected-access
        available = available_quota(event, quota)
        if available is not None and available < len(attendees):
            raise QuotaExceededError(f'Only {available} tickets left')
        order = Order.objects.create(
            event=event,
            seller=seller,
            user=buyer.user if getattr(buyer.user, 'is_authenticated', False) else None,
            buyer_name=buyer.name,
            buyer_email=buyer.email,
            buyer_phone=buyer.phone,
            quantity=len(attendees),
            unit_price=unit_price,
            total=total,
            marketplace_fee=calculate_marketplace_fee(total),
            quota=quota,
            reserved_until=timezone.now() + timedelta(minutes=settings.MP_RESERVATION_MINUTES),
        )
        OrderItem.objects.bulk_create(
            OrderItem(
                order=order,
                first_name=attendee.first_name,
                last_name=attendee.last_name,
                dni=attendee.dni,
                email=attendee.email,
            )
            for attendee in attendees
        )

    try:
        preference = services.create_preference(order, seller.access_token)
    except services.MercadoPagoError:
        # Release the reservation: the buyer cannot pay this order
        Order.objects.filter(pk=order.pk).update(reserved_until=timezone.now())
        raise
    order.preference_id = preference.preference_id
    order.init_point = preference.init_point
    order.save(update_fields=['preference_id', 'init_point', 'updated_at'])
    return order


def _validate_payment(order, data):
    errors = []
    amount = Decimal(str(data.get('transaction_amount', '0'))).quantize(CENTS)
    if amount != order.total:
        errors.append(f'amount {amount} != order total {order.total}')
    if data.get('currency_id') != order.currency:
        errors.append(f'currency {data.get("currency_id")} != {order.currency}')
    if str(data.get('collector_id', '')) != order.seller.mp_user_id:
        errors.append(f'collector {data.get("collector_id")} != seller {order.seller.mp_user_id}')
    return '; '.join(errors)


def _save_payment(order, data, validation_error):
    payment, _created = Payment.objects.update_or_create(
        mp_payment_id=str(data['id']),
        defaults={
            'order': order,
            'status': data.get('status', ''),
            'status_detail': data.get('status_detail') or '',
            'transaction_amount': Decimal(str(data.get('transaction_amount', '0'))).quantize(CENTS),
            'currency': data.get('currency_id') or '',
            'collector_id': str(data.get('collector_id') or ''),
            'payment_method': data.get('payment_method_id') or '',
            'date_approved': parse_datetime(data['date_approved'])
            if data.get('date_approved')
            else None,
            'validation_error': validation_error,
            'raw': data,
        },
    )
    return payment


def _order_id(data):
    try:
        return uuid.UUID(str(data.get('external_reference')))
    except ValueError:
        return None


def apply_payment(data):
    """Apply a Mercado Pago payment (as returned by the API) to its order. Idempotent.

    Returns the order, or None when the payment does not belong to an EventoL order.
    """
    order_id = _order_id(data)
    if order_id is None:
        logger.info('Ignoring Mercado Pago payment %s without an order reference', data.get('id'))
        return None

    with transaction.atomic():
        order = (
            Order.objects.select_for_update(of=('self',))
            .select_related('seller')
            .filter(pk=order_id)
            .first()
        )
        if order is None:
            logger.warning(
                'Mercado Pago payment %s references unknown order %s', data.get('id'), order_id
            )
            return None

        validation_error = _validate_payment(order, data)
        if validation_error:
            logger.error(
                'Mercado Pago payment %s does not match order %s: %s',
                data['id'],
                order.id,
                validation_error,
            )
        payment = _save_payment(order, data, validation_error)

        if payment.status == 'approved' and not validation_error:
            _approve(order, payment)
        elif payment.status in REFUND_STATUSES:
            _refund(order, payment)
    return order


def _approve(order, payment):
    if order.status != Order.Status.PENDING:
        if (
            order.payments.filter(status='approved', validation_error='')
            .exclude(pk=payment.pk)
            .exists()
        ):
            logger.error(
                'Order %s was paid twice (payment %s): refund it manually',
                order.id,
                payment.mp_payment_id,
            )
        return
    available = available_quota(order.event, order.quota, exclude_order=order)
    if available is not None and available < order.quantity:
        order.status = Order.Status.APPROVED_OVER_QUOTA
        logger.error(
            'Order %s was paid after its reservation expired and the quota is full', order.id
        )
    else:
        order.status = Order.Status.APPROVED
    order.paid_at = payment.date_approved or timezone.now()
    order.save(update_fields=['status', 'paid_at', 'updated_at'])
    if order.status == Order.Status.APPROVED:
        transaction.on_commit(lambda: order_paid.send(sender=Order, order=order))


def _refund(order, payment):
    if not order.is_paid:
        return
    # Only the payment that paid the order refunds it (not a duplicated one)
    if (
        order.payments.filter(status='approved', validation_error='')
        .exclude(pk=payment.pk)
        .exists()
    ):
        return
    order.status = Order.Status.REFUNDED
    order.save(update_fields=['status', 'updated_at'])
    transaction.on_commit(lambda: order_refunded.send(sender=Order, order=order))


def _seller_for_notification(mp_user_id):
    seller = SellerAccount.objects.filter(mp_user_id=mp_user_id).first() if mp_user_id else None
    return seller or SellerAccount.for_event(None)


def process_webhook_event(event_id):
    """Fetch the notified resource from Mercado Pago and apply it.

    Raises MercadoPagoError so the caller can retry.
    """
    event = WebhookEvent.objects.get(pk=event_id)
    if event.processed_at:
        return
    event.attempts += 1
    try:
        if event.topic == 'payment' and event.resource_id:
            seller = _seller_for_notification(event.mp_user_id)
            apply_payment(services.get_payment(event.resource_id, seller.access_token))
        else:
            logger.info('Ignoring Mercado Pago notification %s:%s', event.topic, event.resource_id)
    except Exception as error:
        event.error = str(error)
        event.save(update_fields=['attempts', 'error'])
        raise
    event.processed_at = timezone.now()
    event.error = ''
    event.save(update_fields=['attempts', 'processed_at', 'error'])


def refresh_seller_tokens(days=30):
    for seller in SellerAccount.objects.all():
        if not seller.expires_soon(days):
            continue
        data = services.refresh_access_token(seller.refresh_token)
        seller.access_token = data['access_token']
        seller.refresh_token = data['refresh_token']
        seller.expires_at = timezone.now() + timedelta(seconds=int(data['expires_in']))
        seller.save()
        logger.info('Refreshed Mercado Pago token of seller %s', seller.mp_user_id)


def reconcile_pending_orders(days=RECONCILIATION_DAYS):
    """Look for payments of recent pending orders whose notification never arrived."""
    since = timezone.now() - timedelta(days=days)
    applied = 0
    for order in Order.objects.filter(
        status=Order.Status.PENDING, created_at__gte=since
    ).select_related('seller'):
        try:
            payments = services.search_payments(order.external_reference, order.seller.access_token)
        except services.MercadoPagoError as error:
            logger.error('Cannot reconcile order %s: %s', order.id, error)
            continue
        for data in payments:
            apply_payment(data)
            applied += 1
    return applied
