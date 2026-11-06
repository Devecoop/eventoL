"""Symmetric encryption for the Mercado Pago seller tokens stored in the database.

Uses its own Fernet key (``MP_TOKEN_ENCRYPTION_KEY``) instead of deriving one from
``SECRET_KEY``, so rotating the Django secret does not make the tokens unreadable.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet():
    key = settings.MP_TOKEN_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured('MP_TOKEN_ENCRYPTION_KEY is not configured')
    try:
        return Fernet(key)
    except ValueError as error:
        raise ImproperlyConfigured('MP_TOKEN_ENCRYPTION_KEY is not a valid Fernet key') from error


def encrypt(value):
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value):
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as error:
        raise ImproperlyConfigured(
            'Cannot decrypt the Mercado Pago token: MP_TOKEN_ENCRYPTION_KEY changed. '
            'Run "manage.py mp_link_seller" again.'
        ) from error
