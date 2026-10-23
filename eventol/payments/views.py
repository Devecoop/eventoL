import json
import logging

from django.contrib import messages
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from manager.models import Event
from manager.views import update_event_info
from payments import domain, services
from payments.forms import BuyerForm, TicketQuantityForm, attendee_formset
from payments.models import Order, SellerAccountNotConfiguredError, WebhookEvent
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


def _buyer_initial(user):
    if not user.is_authenticated:
        return {}
    return {'name': user.get_full_name(), 'email': user.email}


def purchase(request, event_slug):
    """Buy tickets of a paid event: choose the quantity, then the buyer and attendees data."""
    event = get_object_or_404(Event, event_slug=event_slug)
    if not event.is_paid:
        return redirect(reverse('attendee_registration', args=[event_slug]))
    if not event.registration_is_open or event.registration_closed:
        return render(
            request,
            'registration/closed-registration.html',
            update_event_info(event_slug, event=event),
        )

    available = domain.available_quota(event, event.ticket_quota)
    render_dict = {'available': available, 'unit_price': event.ticket_price}
    if available == 0:
        return render(request, 'payments/purchase.html', update_event_info(event_slug, render_dict))

    quantity_kwargs = {} if available is None else {'max_quantity': available}
    quantity_form = TicketQuantityForm(
        request.GET if 'quantity' in request.GET else None, **quantity_kwargs
    )
    if not quantity_form.is_valid():
        render_dict['quantity_form'] = quantity_form
        return render(request, 'payments/purchase.html', update_event_info(event_slug, render_dict))

    quantity = quantity_form.cleaned_data['quantity']
    data = request.POST or None
    buyer_form = BuyerForm(data, initial=_buyer_initial(request.user))
    # The formset class is built by formset_factory: pylint does not see its __init__
    # pylint: disable-next=unexpected-keyword-arg
    formset = attendee_formset(quantity)(data, event=event, prefix='attendees')
    if request.method == 'POST':
        if buyer_form.is_valid() and formset.is_valid():
            order = _create_order(request, event, buyer_form, formset)
            if order is not None:
                return redirect(order.init_point)
        else:
            messages.error(request, _('There is a problem with the purchase (check form errors)'))

    render_dict.update(
        {
            'quantity': quantity,
            'total': event.ticket_price * quantity,
            'buyer_form': buyer_form,
            'formset': formset,
        }
    )
    return render(request, 'payments/purchase.html', update_event_info(event_slug, render_dict))


def _create_order(request, event, buyer_form, formset):
    buyer = domain.Buyer(
        name=buyer_form.cleaned_data['name'],
        email=buyer_form.cleaned_data['email'],
        phone=buyer_form.cleaned_data['phone'],
        user=request.user,
    )
    attendees = [domain.AttendeeData(**form.cleaned_data) for form in formset]
    try:
        return domain.create_order(event, buyer, attendees, event.ticket_price, event.ticket_quota)
    except domain.QuotaExceededError:
        messages.error(request, _('There are not enough tickets left'))
    except (SellerAccountNotConfiguredError, services.MercadoPagoError):
        logger.exception('Could not create the order of event %s', event.event_slug)
        messages.error(request, _('The payment could not be started. Please try again later'))
    return None
