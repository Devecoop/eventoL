from django.core.management.base import BaseCommand, CommandError

from manager.models import Event
from payments import domain
from payments.models import SellerAccountNotConfiguredError
from payments.services import MercadoPagoError


class Command(BaseCommand):
    help = (
        'Create an order and print the Mercado Pago checkout URL '
        '(to test the integration without the purchase form)'
    )

    def add_arguments(self, parser):
        parser.add_argument('--event', required=True, help='Event slug')
        parser.add_argument(
            '--type', dest='ticket_type', help='Ticket type name (default: the cheapest one)'
        )
        parser.add_argument('--qty', type=int, default=1, help='Number of tickets')
        parser.add_argument('--email', default='test_user@testuser.com', help='Buyer email')

    def handle(self, *args, **options):
        event = Event.objects.filter(event_slug=options['event']).first()
        if event is None:
            raise CommandError(f'Event "{options["event"]}" does not exist')
        ticket_types = event.ticket_types.all()
        if options['ticket_type']:
            ticket_types = ticket_types.filter(name=options['ticket_type'])
        ticket_type = ticket_types.first()
        if ticket_type is None:
            raise CommandError('The event has no ticket types (add them in the event form)')
        buyer = domain.Buyer(name='Test Buyer', email=options['email'], phone='1100000000')
        attendees = [
            domain.AttendeeData(
                first_name='Test',
                last_name=f'Attendee {number}',
                dni=f'{30000000 + number}',
                ticket_type=ticket_type,
            )
            for number in range(1, options['qty'] + 1)
        ]
        try:
            order = domain.create_order(event, buyer, attendees)
        except (
            domain.QuotaExceededError,
            domain.InvalidOrderError,
            SellerAccountNotConfiguredError,
            MercadoPagoError,
        ) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f'Order: {order.id} (total {order.total}, fee {order.marketplace_fee})')
        self.stdout.write(f'Pay at: {order.init_point}')
