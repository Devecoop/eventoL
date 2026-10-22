from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

from payments import domain
from payments.services import MercadoPagoError

logger = get_task_logger(__name__)


@shared_task(autoretry_for=(MercadoPagoError,), retry_backoff=True, max_retries=6)
def process_webhook_event_task(event_id):
    domain.process_webhook_event(event_id)


@shared_task
def reconcile_pending_orders_task():
    """Periodic task (celery beat or cron through the sync_mp_orders command)."""
    domain.refresh_seller_tokens()
    applied = domain.reconcile_pending_orders()
    logger.info('Reconciled %s Mercado Pago payments', applied)
    return applied


def dispatch_webhook_event(event_id):
    """Process in celery when enabled, otherwise in the request.

    Same pattern as manager.utils.email.send_email.
    """
    if settings.CELERY_ENABLED:
        process_webhook_event_task.delay(event_id)
    else:
        domain.process_webhook_event(event_id)
