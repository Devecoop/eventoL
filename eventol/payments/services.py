"""Thin wrapper around the Mercado Pago SDK and OAuth API.

Adapted from Devecoop/mercadopago-mvp (``mp/services.py``) with these fixes:

- every call uses the seller access token (the payments belong to the seller account);
- no "dev mode": without credentials the call fails, it never approves anything;
- webhook signature is validated with the raw header and query values (the mvp passed
  ``dict(request.headers)`` and ``dict(request.GET)``, so the signature never matched);
- amounts are Decimal in the domain and only converted at the API boundary.

This module knows nothing about orders state: see ``payments.domain``.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlencode

import mercadopago
import requests
from django.conf import settings
from django.urls import reverse
from mercadopago import webhook as mp_webhook

logger = logging.getLogger(__name__)

OAUTH_AUTHORIZATION_URL = 'https://auth.mercadopago.com.ar/authorization'
OAUTH_TOKEN_URL = 'https://api.mercadopago.com/oauth/token'  # noqa: S105
REQUEST_TIMEOUT = 15


class MercadoPagoError(RuntimeError):
    """Mercado Pago could not be reached or answered with an error. Safe to retry."""


class MercadoPagoNotConfiguredError(MercadoPagoError):
    pass


class InvalidWebhookSignatureError(Exception):
    pass


@dataclass
class PreferenceResult:
    preference_id: str
    init_point: str
    sandbox_init_point: str = ''


def _build_sdk(access_token):
    if not access_token:
        raise MercadoPagoNotConfiguredError('Mercado Pago access token is empty')
    return mercadopago.SDK(access_token)


def _sdk_result(result):
    """Return the ``response`` of an SDK call or raise MercadoPagoError."""
    if not isinstance(result, dict):
        raise MercadoPagoError(f'Unexpected SDK response type: {type(result).__name__}')
    status = result.get('status', 0)
    if status not in (200, 201):
        raise MercadoPagoError(
            f'Mercado Pago API error (HTTP {status}): {result.get("response", result)}'
        )
    response = result.get('response')
    if not response:
        raise MercadoPagoError(f'Empty response from Mercado Pago (HTTP {status})')
    return response


def _amount(value):
    """Mercado Pago expects JSON numbers: convert a Decimal at the boundary, rounded to cents."""
    return float(Decimal(value).quantize(Decimal('0.01')))


def absolute_url(path):
    return f'{settings.MP_BASE_URL.rstrip("/")}{path}'


def notification_url():
    # source_news=webhooks: receive only Webhooks (v1) notifications, not the legacy IPN ones
    return absolute_url(reverse('payments_mercadopago_webhook')) + '?source_news=webhooks'


def order_status_url(order):
    return absolute_url(reverse('payments_order_status', args=[order.id]))


# Checkout Pro


def create_preference(order, access_token):
    """Create the checkout preference of an order with the seller token and the marketplace fee."""
    sdk = _build_sdk(access_token)
    back_url = order_status_url(order)
    body = {
        'items': [
            {
                'id': str(order.event_id),
                'title': str(order.event.name)[:250],
                'quantity': order.quantity,
                'currency_id': order.currency,
                'unit_price': _amount(order.unit_price),
            }
        ],
        'payer': {'name': order.buyer_name, 'email': order.buyer_email},
        'external_reference': order.external_reference,
        'marketplace_fee': _amount(order.marketplace_fee),
        'back_urls': {'success': back_url, 'pending': back_url, 'failure': back_url},
        'auto_return': 'approved',
        'notification_url': notification_url(),
    }
    logger.info('Creating Mercado Pago preference for order %s', order.id)
    result = _sdk_result(sdk.preference().create(body))
    return PreferenceResult(
        preference_id=result['id'],
        init_point=result.get('init_point', ''),
        sandbox_init_point=result.get('sandbox_init_point', ''),
    )


def get_payment(payment_id, access_token):
    return _sdk_result(_build_sdk(access_token).payment().get(payment_id))


def search_payments(external_reference, access_token):
    """All the payments (any status) of an order, used for reconciliation."""
    result = _sdk_result(
        _build_sdk(access_token)
        .payment()
        .search(filters={'external_reference': external_reference})
    )
    return result.get('results') or []


# Webhooks


def validate_webhook_signature(x_signature, x_request_id, data_id):
    """Raise InvalidWebhookSignature unless the notification was signed with MP_WEBHOOK_SECRET.

    Without a configured secret the check is skipped only when DEBUG is on.
    """
    secret = settings.MP_WEBHOOK_SECRET
    if not secret:
        if settings.DEBUG:
            logger.warning(
                'MP_WEBHOOK_SECRET is not configured: skipping webhook signature validation'
            )
            return
        raise InvalidWebhookSignatureError('MP_WEBHOOK_SECRET is not configured')
    try:
        mp_webhook.WebhookSignatureValidator.validate(
            x_signature=x_signature,
            x_request_id=x_request_id,
            data_id=data_id,
            secret=secret,
        )
    except mp_webhook.InvalidWebhookSignatureError as error:
        raise InvalidWebhookSignatureError(str(error)) from error


# Seller OAuth


def _oauth_credentials():
    if not (settings.MP_CLIENT_ID and settings.MP_CLIENT_SECRET and settings.MP_OAUTH_REDIRECT_URI):
        raise MercadoPagoNotConfiguredError(
            'MP_CLIENT_ID, MP_CLIENT_SECRET and MP_OAUTH_REDIRECT_URI are required'
        )
    return settings.MP_CLIENT_ID, settings.MP_CLIENT_SECRET


def build_authorization_url(state):
    client_id, _ = _oauth_credentials()
    params = {
        'client_id': client_id,
        'response_type': 'code',
        'platform_id': 'mp',
        'state': state,
        'redirect_uri': settings.MP_OAUTH_REDIRECT_URI,
    }
    return f'{OAUTH_AUTHORIZATION_URL}?{urlencode(params)}'


def _request_token(payload):
    client_id, client_secret = _oauth_credentials()
    payload = {'client_id': client_id, 'client_secret': client_secret, **payload}
    try:
        response = requests.post(OAUTH_TOKEN_URL, json=payload, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as error:
        raise MercadoPagoError(f'Mercado Pago OAuth request failed: {error}') from error
    if response.status_code != 200:  # noqa: PLR2004
        raise MercadoPagoError(
            f'Mercado Pago OAuth error (HTTP {response.status_code}): {response.text}'
        )
    return response.json()


def exchange_code(code):
    """Exchange the OAuth authorization code for the seller tokens."""
    return _request_token(
        {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': settings.MP_OAUTH_REDIRECT_URI,
        }
    )


def refresh_access_token(refresh_token):
    return _request_token({'grant_type': 'refresh_token', 'refresh_token': refresh_token})
