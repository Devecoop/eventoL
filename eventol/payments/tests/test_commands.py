# pylint: disable=unused-argument
from unittest import mock

import pytest
from django.core.management import call_command

from payments.models import SellerAccount, SellerAccountNotConfiguredError

pytestmark = pytest.mark.django_db

TOKENS = {
    'user_id': 987654,
    'access_token': 'APP_USR-access',
    'refresh_token': 'TG-refresh',
    'public_key': 'APP_USR-public',
    'expires_in': 15552000,
}


def test_mp_link_seller_stores_encrypted_tokens():
    with mock.patch('payments.services.exchange_code', return_value=TOKENS) as exchange_code:
        call_command('mp_link_seller', code='auth-code')
    exchange_code.assert_called_once_with('auth-code')
    seller = SellerAccount.objects.get(mp_user_id='987654')
    assert seller.access_token == 'APP_USR-access'
    assert 'APP_USR-access' not in seller.encrypted_access_token
    assert not seller.expires_soon()


def test_mp_link_seller_checks_the_oauth_state():
    with (
        mock.patch('builtins.input', return_value='https://eventol.test/oauth?code=x&state=forged'),
        pytest.raises(Exception, match='state'),
    ):
        call_command('mp_link_seller')
    assert not SellerAccount.objects.exists()


def test_new_orders_use_the_last_linked_account():
    with mock.patch('payments.services.exchange_code', return_value=TOKENS):
        call_command('mp_link_seller', code='auth-code')
    with mock.patch('payments.services.exchange_code', return_value={**TOKENS, 'user_id': 111111}):
        call_command('mp_link_seller', code='auth-code')
    assert SellerAccount.current().mp_user_id == '111111'

    # Linking the first account again makes it the current one
    with mock.patch('payments.services.exchange_code', return_value=TOKENS):
        call_command('mp_link_seller', code='auth-code')
    assert SellerAccount.current().mp_user_id == '987654'
    assert SellerAccount.objects.count() == 2


def test_there_is_no_current_seller_until_an_account_is_linked():
    with pytest.raises(SellerAccountNotConfiguredError):
        SellerAccount.current()
