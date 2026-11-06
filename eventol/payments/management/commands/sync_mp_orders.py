from django.core.management.base import BaseCommand

from payments import domain


class Command(BaseCommand):
    help = (
        'Reconcile pending orders with Mercado Pago (payments whose notification never arrived) '
        'and refresh the seller tokens that are about to expire. Run it periodically (cron) when '
        'celery beat is off.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=domain.RECONCILIATION_DAYS,
            help='Look at orders of the last N days',
        )

    def handle(self, *args, **options):
        domain.refresh_seller_tokens()
        applied = domain.reconcile_pending_orders(days=options['days'])
        self.stdout.write(self.style.SUCCESS(f'Applied {applied} Mercado Pago payments'))
