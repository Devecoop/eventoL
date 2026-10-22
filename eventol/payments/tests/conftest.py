# pylint: disable=redefined-outer-name
import hashlib
import hmac
from datetime import timedelta
from unittest import mock

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from manager.models import Event
from payments.models import SellerAccount
from payments.services import PreferenceResult

SELLER_MP_USER_ID = '123456'
WEBHOOK_SECRET = 'webhook-secret'


@pytest.fixture(autouse=True)
def mp_settings(settings):
    settings.MP_TOKEN_ENCRYPTION_KEY = Fernet.generate_key().decode()
    settings.MP_WEBHOOK_SECRET = WEBHOOK_SECRET
    settings.MP_BASE_URL = 'https://eventol.test'
    settings.MP_MARKETPLACE_FEE_PERCENT = 3
    settings.MP_RESERVATION_MINUTES = 30
    settings.MP_CLIENT_ID = 'client-id'
    settings.MP_CLIENT_SECRET = 'client-secret'
    settings.MP_OAUTH_REDIRECT_URI = 'https://eventol.test/oauth'
    settings.CELERY_ENABLED = False
    settings.DEBUG = False
    return settings


@pytest.fixture
def event(db):  # pylint: disable=unused-argument
    return Event.objects.create(
        name='Gran Pez Fest',
        event_slug='gran-pez',
        email='info@granpez.test',
        abstract='Fest',
        limit_proposal_date=timezone.localdate(),
    )


@pytest.fixture
def seller(db):  # pylint: disable=unused-argument
    account = SellerAccount(
        mp_user_id=SELLER_MP_USER_ID, expires_at=timezone.now() + timedelta(days=180)
    )
    account.access_token = 'seller-access-token'
    account.refresh_token = 'seller-refresh-token'
    account.save()
    return account


@pytest.fixture
def preference():
    with mock.patch(
        'payments.services.create_preference',
        return_value=PreferenceResult(
            preference_id='pref-1', init_point='https://mp.test/checkout'
        ),
    ) as create_preference:
        yield create_preference


def mp_payment(order, payment_id='1001', status='approved', **overrides):
    """A payment as returned by the Mercado Pago API."""
    data = {
        'id': int(payment_id),
        'status': status,
        'status_detail': 'accredited' if status == 'approved' else status,
        'external_reference': str(order.id),
        'transaction_amount': float(order.total),
        'currency_id': 'ARS',
        'collector_id': int(SELLER_MP_USER_ID),
        'payment_method_id': 'visa',
        'date_approved': '2026-10-19T10:00:00.000-03:00' if status == 'approved' else None,
    }
    data.update(overrides)
    return data


def sign(data_id, request_id, timestamp='1760000000000', secret=WEBHOOK_SECRET):
    manifest = f'id:{data_id};request-id:{request_id};ts:{timestamp};'
    digest = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f'ts={timestamp},v1={digest}'
