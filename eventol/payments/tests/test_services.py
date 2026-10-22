# pylint: disable=redefined-outer-name,unused-argument

import pytest

from payments import services

from .conftest import sign


def test_sdk_result_raises_on_api_errors():
    with pytest.raises(services.MercadoPagoError):
        services._sdk_result({'status': 400, 'response': {'message': 'bad'}})  # pylint: disable=protected-access


def test_build_sdk_without_token_never_works():
    with pytest.raises(services.MercadoPagoNotConfiguredError):
        services._build_sdk('')  # pylint: disable=protected-access


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
