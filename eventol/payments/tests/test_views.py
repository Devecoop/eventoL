# pylint: disable=redefined-outer-name,unused-argument
import json
from unittest import mock

import pytest
from django.urls import reverse

from payments import domain
from payments.models import Order, WebhookEvent
from payments.services import MercadoPagoError

from .conftest import mp_payment, sign

pytestmark = pytest.mark.django_db


@pytest.fixture
def order(event, seller, preference):
    buyer = domain.Buyer(name='Ana Pez', email='ana@example.com', phone='1122334455')
    people = [domain.AttendeeData(first_name='Ana', last_name='Pez', dni='30000000')]
    return domain.create_order(event, buyer, people, '1000')


def notify(client, payment_id='1001', request_id='req-1', signature=None):
    url = reverse('payments_mercadopago_webhook') + f'?data.id={payment_id}&type=payment'
    body = {'type': 'payment', 'action': 'payment.updated', 'data': {'id': payment_id}}
    return client.post(
        url,
        data=json.dumps(body),
        content_type='application/json',
        HTTP_X_SIGNATURE=signature or sign(payment_id, request_id),
        HTTP_X_REQUEST_ID=request_id,
    )


def test_webhook_approves_the_order(client, order):
    with mock.patch('payments.services.get_payment', return_value=mp_payment(order)) as get_payment:
        response = notify(client)
    assert response.status_code == 200
    get_payment.assert_called_once_with('1001', 'seller-access-token')
    order.refresh_from_db()
    assert order.status == Order.Status.APPROVED
    event = WebhookEvent.objects.get()
    assert event.processed_at is not None
    assert event.topic == 'payment'


def test_repeated_notification_is_processed_once(client, order):
    with mock.patch('payments.services.get_payment', return_value=mp_payment(order)) as get_payment:
        notify(client)
        response = notify(client)
    assert response.status_code == 200
    get_payment.assert_called_once()
    assert WebhookEvent.objects.count() == 1


def test_invalid_signature_is_rejected(client, order):
    with mock.patch('payments.services.get_payment') as get_payment:
        response = notify(client, signature=sign('1001', 'req-1', secret='other'))
    assert response.status_code == 400
    get_payment.assert_not_called()
    assert not WebhookEvent.objects.exists()


def test_failed_processing_asks_for_a_retry(client, order):
    with mock.patch('payments.services.get_payment', side_effect=MercadoPagoError('down')):
        response = notify(client)
    assert response.status_code == 500
    event = WebhookEvent.objects.get()
    assert event.processed_at is None
    assert 'down' in event.error

    with mock.patch('payments.services.get_payment', return_value=mp_payment(order)):
        response = notify(client)
    assert response.status_code == 200
    event.refresh_from_db()
    assert event.processed_at is not None
    assert event.attempts == 2


def test_order_status_json(client, order):
    response = client.get(reverse('payments_order_status', args=[order.id]) + '?format=json')
    assert response.json() == {'status': 'pending', 'is_paid': False}


def test_order_status_page(client, order):
    response = client.get(reverse('payments_order_status', args=[order.id]))
    assert response.status_code == 200
    assert order.init_point in response.content.decode()
