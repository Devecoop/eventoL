# pylint: disable=redefined-outer-name,unused-argument
from unittest import mock

import pytest

from payments import domain, services

from .conftest import sign


def test_sdk_result_raises_on_api_errors():
    with pytest.raises(services.MercadoPagoError):
        services._sdk_result({'status': 400, 'response': {'message': 'bad'}})  # pylint: disable=protected-access


def test_build_sdk_without_token_never_works():
    with pytest.raises(services.MercadoPagoNotConfiguredError):
        services._build_sdk('')  # pylint: disable=protected-access


@pytest.mark.django_db
def test_create_preference_body(event, seller):
    buyer = domain.Buyer(name='Ana Pez', email='ana@example.com', phone='1122334455')
    people = [domain.AttendeeData(first_name='Ana', last_name='Pez', dni='30000000')] * 2
    sdk = mock.Mock()
    sdk.preference.return_value.create.return_value = {
        'status': 201,
        'response': {'id': 'pref-1', 'init_point': 'https://mp.test/checkout'},
    }
    with mock.patch('payments.services._build_sdk', return_value=sdk) as build_sdk:
        order = domain.create_order(event, buyer, people, '1500.50')

    build_sdk.assert_called_once_with('seller-access-token')
    body = sdk.preference.return_value.create.call_args.args[0]
    assert body['items'][0]['quantity'] == 2
    assert body['items'][0]['unit_price'] == 1500.5
    assert body['items'][0]['currency_id'] == 'ARS'
    assert body['marketplace_fee'] == 90.03
    assert body['external_reference'] == str(order.id)
    assert body['notification_url'] == (
        'https://eventol.test/payments/mercadopago/webhook?source_news=webhooks'
    )
    assert body['back_urls']['success'] == f'https://eventol.test/payments/order/{order.id}'
    assert order.preference_id == 'pref-1'


def test_valid_webhook_signature():
    services.validate_webhook_signature(sign('1001', 'req-1'), 'req-1', '1001')


@pytest.mark.parametrize(
    ('signature', 'data_id'),
    [
        (sign('1001', 'req-1', secret='other'), '1001'),
        (sign('1001', 'req-1'), '9999'),
        (None, '1001'),
    ],
)
def test_invalid_webhook_signature(signature, data_id):
    with pytest.raises(services.InvalidWebhookSignatureError):
        services.validate_webhook_signature(signature, 'req-1', data_id)


def test_webhook_secret_is_mandatory_without_debug(settings):
    settings.MP_WEBHOOK_SECRET = ''
    with pytest.raises(services.InvalidWebhookSignatureError):
        services.validate_webhook_signature(None, None, None)
    settings.DEBUG = True
    services.validate_webhook_signature(None, None, None)


def test_authorization_url_includes_state():
    url = services.build_authorization_url('my-state')
    assert url.startswith(services.OAUTH_AUTHORIZATION_URL)
    assert 'state=my-state' in url
    assert 'client_id=client-id' in url
