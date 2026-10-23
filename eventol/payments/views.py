import json
import logging

from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from manager.views import update_event_info
from payments import services
from payments.models import Order, WebhookEvent
from payments.tasks import dispatch_webhook_event

logger = logging.getLogger(__name__)


def _parse_notification(request):
    try:
        body = json.loads(request.body or b'{}')
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    data = body.get('data') if isinstance(body.get('data'), dict) else {}
    return {
        'topic': str(body.get('type') or request.GET.get('type') or request.GET.get('topic') or ''),
        'action': str(body.get('action') or ''),
        'resource_id': str(
            data.get('id') or request.GET.get('data.id') or request.GET.get('id') or ''
        ),
        'mp_user_id': str(body.get('user_id') or ''),
        'payload': body,
    }


@csrf_exempt
@require_POST
def mercadopago_webhook(request):
    """Receive Mercado Pago notifications.

    Answers 200 as soon as the notification is stored; the payment is fetched and applied by
    ``domain.process_webhook_event`` (in celery when enabled). Retries of the same notification
    (same x-request-id) are processed again only if they were not processed yet.
    """
    # request.headers is case insensitive and request.GET values are strings
    request_id = request.headers.get('x-request-id') or None
    try:
        services.validate_webhook_signature(
            x_signature=request.headers.get('x-signature'),
            x_request_id=request_id,
            data_id=request.GET.get('data.id'),
        )
    except services.InvalidWebhookSignatureError as error:
        logger.warning('Rejected Mercado Pago notification with invalid signature: %s', error)
        return HttpResponseBadRequest()

    notification = _parse_notification(request)
    event = WebhookEvent.objects.filter(request_id=request_id).first() if request_id else None
    if event is None:
        try:
            event = WebhookEvent.objects.create(request_id=request_id, **notification)
        except IntegrityError:  # the same notification arrived twice at the same time
            return HttpResponse(status=200)
    if event.processed_at:
        return HttpResponse(status=200)

    try:
        dispatch_webhook_event(event.pk)
    except Exception:  # pylint: disable=broad-except
        # Synchronous mode: ask Mercado Pago to retry (the error is stored in the event)
        logger.exception('Error processing Mercado Pago notification %s', event.pk)
        return HttpResponse(status=500)
    return HttpResponse(status=200)


@require_GET
def order_status(request, order_id):
    """Page where Mercado Pago sends the buyer back. ``?format=json`` is used to poll the status."""
    order = get_object_or_404(Order.objects.select_related('event'), pk=order_id)
    if request.GET.get('format') == 'json':
        return JsonResponse({'status': order.status, 'is_paid': order.is_paid})
    return render(
        request,
        'payments/order_status.html',
        update_event_info(order.event.event_slug, {'order': order}),
    )
