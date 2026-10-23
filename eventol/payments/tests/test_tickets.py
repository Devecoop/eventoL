# pylint: disable=redefined-outer-name,unused-argument
import os
from datetime import timedelta
from decimal import Decimal

import pytest
from django.conf import settings as django_settings
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from manager.forms import AttendeeRegistrationForm, EventForm
from manager.models import Attendee, EventDate
from payments import domain
from payments.models import Order

from .conftest import mp_payment

pytestmark = pytest.mark.django_db


@pytest.fixture
def ticket_settings(settings):
    # The ticket template is read from STATIC_ROOT (collectstatic is not run in the tests)
    settings.STATIC_ROOT = os.path.join(django_settings.BASE_DIR, 'manager', 'static')
    return settings


@pytest.fixture
def order(event, seller, preference, ticket_settings):
    EventDate.objects.create(event=event, date=timezone.localdate() + timedelta(days=10))
    buyer = domain.Buyer(name='Ana Pez', email='ana@example.com', phone='1122334455')
    people = [
        domain.AttendeeData(first_name='Ana', last_name='Pez', dni='30000000'),
        domain.AttendeeData(
            first_name='Beto', last_name='Pez', dni='30000001', email='beto@example.com'
        ),
    ]
    return domain.create_order(event, buyer, people, '1000')


def pay(order, django_capture_on_commit_callbacks, status='approved'):
    with django_capture_on_commit_callbacks(execute=True):
        domain.apply_payment(mp_payment(order, status=status))


def test_paid_order_issues_one_ticket_by_attendee(order, django_capture_on_commit_callbacks):
    pay(order, django_capture_on_commit_callbacks)

    attendees = Attendee.objects.filter(event=order.event).order_by('dni')
    assert [attendee.dni for attendee in attendees] == ['30000000', '30000001']
    assert [attendee.email for attendee in attendees] == ['ana@example.com', 'beto@example.com']
    assert all(attendee.email_confirmed and attendee.ticket for attendee in attendees)
    assert all(attendee.ticket.sent for attendee in attendees)
    assert order.items.filter(attendee__isnull=True).count() == 0


def test_buyer_receives_every_ticket_and_attendees_their_own(
    order, django_capture_on_commit_callbacks
):
    pay(order, django_capture_on_commit_callbacks)

    by_recipient = {message.to[0]: message for message in mail.outbox}
    assert set(by_recipient) == {'ana@example.com', 'beto@example.com'}
    assert len(by_recipient['ana@example.com'].attachments) == 2
    assert len(by_recipient['beto@example.com'].attachments) == 1


def test_ticket_is_not_issued_twice_for_a_dni(order, django_capture_on_commit_callbacks):
    # Another purchase took the DNI after this order was created
    Attendee.objects.create(event=order.event, email='other@example.com', dni='30000001')

    pay(order, django_capture_on_commit_callbacks)

    order.refresh_from_db()
    assert order.status == Order.Status.APPROVED
    assert Attendee.objects.filter(event=order.event, dni='30000001').count() == 1
    assert order.items.get(dni='30000001').attendee is None
    assert order.items.get(dni='30000000').attendee is not None


def test_refund_cancels_the_tickets(order, django_capture_on_commit_callbacks):
    pay(order, django_capture_on_commit_callbacks)
    pay(order, django_capture_on_commit_callbacks, status='refunded')

    tickets = [item.attendee.ticket for item in order.items.select_related('attendee__ticket')]
    assert all(ticket.cancelled and ticket.cancelled_at for ticket in tickets)


def test_cancelled_ticket_does_not_allow_entry(
    admin_client, order, django_capture_on_commit_callbacks
):
    pay(order, django_capture_on_commit_callbacks)
    pay(order, django_capture_on_commit_callbacks, status='refunded')
    attendee = order.items.first().attendee
    event = order.event
    EventDate.objects.create(event=event, date=timezone.localdate())

    response = admin_client.get(
        reverse('attendance_by_autoreadqr', args=[event.event_slug]),
        {'event_registration_code': event.registration_code, 'ticket': attendee.ticket.code},
        follow=True,
    )

    assert 'cancelled' in str(list(response.context['messages'])[0])
    assert not attendee.attended


def test_paid_event_needs_price_and_seller(event):
    data = {
        'name': event.name,
        'event_slug': 'paid-event',
        'tz_event': 'UTC',
        'email': event.email,
        'abstract': event.abstract,
        'is_paid': True,
    }
    form = EventForm(data)
    assert not form.is_valid()
    assert 'ticket_price' in form.errors
    assert 'is_paid' in form.errors


def test_paid_event_with_price_and_seller_is_valid(event, seller):
    data = {
        'name': event.name,
        'event_slug': 'paid-event',
        'tz_event': 'UTC',
        'email': event.email,
        'abstract': event.abstract,
        'is_paid': True,
        'ticket_price': Decimal('1000'),
    }
    assert EventForm(data).is_valid()


def test_free_registration_still_rejects_a_repeated_email(event, captcha_passes):
    Attendee.objects.create(event=event, email='ana@example.com')
    form = AttendeeRegistrationForm(
        {
            'email': 'ANA@example.com',
            'repeat_email': 'ANA@example.com',
            'event': event.pk,
            'captcha_0': 'key',
            'captcha_1': 'PASSED',
        }
    )
    assert not form.is_valid()
    assert form.errors.as_data()['__all__'][0].message == (
        'You are already registered for this event'
    )


def test_attendees_without_dni_do_not_collide(event):
    Attendee.objects.create(event=event, email='ana@example.com', dni='')
    Attendee.objects.create(event=event, email='beto@example.com', dni='')
    assert Attendee.objects.filter(event=event, dni__isnull=True).count() == 2
