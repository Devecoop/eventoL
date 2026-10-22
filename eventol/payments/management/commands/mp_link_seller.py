import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from manager.models import Event
from payments import services
from payments.models import SellerAccount


class Command(BaseCommand):
    help = (
        'Link the Mercado Pago account that receives the payments (seller) to the marketplace '
        'application. Prints the authorization URL; open it logged in as the seller, accept, '
        'and paste the URL you are redirected to.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--event',
            help='Event slug, to link an account only for that event (default: all events)',
        )
        parser.add_argument('--code', help='Authorization code, to skip the interactive step')

    def handle(self, *args, **options):
        event = None
        if options['event']:
            event = Event.objects.filter(event_slug=options['event']).first()
            if event is None:
                raise CommandError(f'Event "{options["event"]}" does not exist')

        code = options['code'] or self._ask_code()
        try:
            data = services.exchange_code(code)
        except services.MercadoPagoError as error:
            raise CommandError(str(error)) from error

        seller = SellerAccount.objects.filter(
            mp_user_id=str(data['user_id'])
        ).first() or SellerAccount(mp_user_id=str(data['user_id']))
        seller.event = event
        seller.public_key = data.get('public_key', '')
        seller.access_token = data['access_token']
        seller.refresh_token = data['refresh_token']
        seller.expires_at = timezone.now() + timedelta(seconds=int(data['expires_in']))
        seller.save()
        self.stdout.write(
            self.style.SUCCESS(
                f'Linked Mercado Pago account {seller.mp_user_id} '
                f'(expires {seller.expires_at:%Y-%m-%d})'
            )
        )

    def _ask_code(self):
        state = secrets.token_urlsafe(24)
        try:
            url = services.build_authorization_url(state)
        except services.MercadoPagoError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            'Open this URL logged in with the seller Mercado Pago account and accept:\n'
        )
        self.stdout.write(url + '\n')
        redirected = input('Paste the URL you were redirected to: ').strip()
        query = parse_qs(urlparse(redirected).query)
        if query.get('state', [''])[0] != state:
            raise CommandError('The "state" parameter does not match: start again')
        code = query.get('code', [''])[0]
        if not code:
            raise CommandError('The URL has no "code" parameter')
        return code
