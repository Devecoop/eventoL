"""Issue and cancel the tickets of the orders paid with Mercado Pago (payments app)."""

import logging

from django.db import IntegrityError, transaction
from django.dispatch import receiver
from django.utils import timezone

from manager.models import Attendee, Ticket
from manager.utils import email as utils_email
from manager.views import generate_ticket, send_event_ticket
from payments.models import Order
from payments.signals import order_paid, order_refunded

logger = logging.getLogger('eventol')


def _create_attendee(order, item):
    try:
        with transaction.atomic():
            attendee = Attendee.objects.create(
                event=order.event,
                first_name=item.first_name,
                last_name=item.last_name,
                dni=item.dni,
                email=item.ticket_email,
                email_confirmed=True,
                registration_date=timezone.now(),
                ticket=Ticket.objects.create(),
            )
            item.attendee = attendee
            item.save(update_fields=['attendee'])
    except IntegrityError:
        # Another order took this DNI after the purchase form was validated
        logger.error(
            'Order %s was paid but DNI %s already has a ticket for %s: the ticket was not '
            'issued, review the order',
            order.id,
            item.dni,
            order.event,
        )
        return None
    return attendee


def _send_tickets(order, attendees):
    try:
        tickets = [(attendee.ticket.code, generate_ticket(attendee)) for attendee in attendees]
        utils_email.send_order_tickets_email(
            order.event.name, order.buyer_name, order.buyer_email, tickets
        )
        Ticket.objects.filter(attendee__in=attendees).update(sent=True)
    except Exception:  # pylint: disable=broad-except
        # The order is paid and the attendees exist: the tickets can be sent again later
        logger.exception('Could not send the tickets of order %s', order.id)

    for attendee in attendees:
        if attendee.email.lower() == order.buyer_email.lower():
            continue
        try:
            send_event_ticket(attendee)
        except Exception:  # pylint: disable=broad-except
            logger.exception('Could not send the ticket of attendee %s', attendee.pk)


@receiver(order_paid, sender=Order)
def issue_order_tickets(sender, order, **kwargs):  # pylint: disable=unused-argument
    """Create an Attendee with its Ticket for each item of the order and send the tickets."""
    attendees = []
    for item in order.items.filter(attendee__isnull=True):
        attendee = _create_attendee(order, item)
        if attendee is not None:
            attendees.append(attendee)
    if attendees:
        _send_tickets(order, attendees)


@receiver(order_refunded, sender=Order)
def cancel_order_tickets(sender, order, **kwargs):  # pylint: disable=unused-argument
    """A refunded order does not allow entry anymore."""
    tickets = Ticket.objects.filter(attendee__orderitem__order=order, cancelled=False).distinct()
    for ticket in tickets:
        ticket.cancel()
