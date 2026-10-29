# pylint: disable=redefined-outer-name,unused-argument
from datetime import timedelta
from decimal import Decimal

import pytest
from django.forms import modelformset_factory
from django.urls import reverse
from django.utils import timezone

from manager.forms import TicketTypeForm, TicketTypeModelFormset
from manager.models import EventDate, TicketType
from payments import domain

pytestmark = pytest.mark.django_db

TicketTypeFormSet = modelformset_factory(
    TicketType, form=TicketTypeForm, formset=TicketTypeModelFormset, can_delete=True
)


def formset_data(*rows):
    """Management form plus one form by (ticket type or None, name, price, quota, delete)."""
    data = {
        'tt-TOTAL_FORMS': str(len(rows)),
        'tt-INITIAL_FORMS': str(sum(1 for row in rows if row[0] is not None)),
        'tt-MIN_NUM_FORMS': '0',
        'tt-MAX_NUM_FORMS': '1000',
    }
    for index, (ticket_type, name, price, quota, delete) in enumerate(rows):
        data.update(
            {
                f'tt-{index}-id': ticket_type.pk if ticket_type else '',
                f'tt-{index}-name': name,
                f'tt-{index}-price': price,
                f'tt-{index}-quota': quota,
            }
        )
        if delete:
            data[f'tt-{index}-DELETE'] = 'on'
    return data


def bound_formset(event, *rows):
    return TicketTypeFormSet(formset_data(*rows), prefix='tt', queryset=event.ticket_types.all())


def sell(event, ticket_type):
    buyer = domain.Buyer(name='Ana Garcia', email='ana@example.com', phone='1122334455')
    attendee = domain.AttendeeData(
        first_name='Ana', last_name='Garcia', dni='30000000', ticket_type=ticket_type
    )
    return domain.create_order(event, buyer, [attendee])


def test_create_ticket_types(event):
    formset = bound_formset(
        event, (None, 'General', '1000', '', False), (None, 'VIP', '3000', '2', False)
    )
    assert formset.is_valid(), formset.errors
    for ticket_type in formset.save(commit=False):
        ticket_type.event = event
        ticket_type.save()
    assert list(event.ticket_types.values_list('name', 'price', 'quota')) == [
        ('General', Decimal('1000.00'), None),
        ('VIP', Decimal('3000.00'), 2),
    ]


def test_ticket_type_price_must_be_positive(event):
    formset = bound_formset(event, (None, 'General', '0', '', False))
    assert not formset.is_valid()
    assert 'price' in formset.forms[0].errors


def test_ticket_type_names_are_unique(event):
    formset = bound_formset(
        event, (None, 'General', '10', '', False), (None, 'general', '20', '', False)
    )
    assert not formset.is_valid()
    assert formset.non_form_errors()


def test_price_of_a_ticket_type_with_sales_cannot_change(event, seller, preference, general):
    sell(event, general)
    formset = bound_formset(event, (general, 'General Plus', '5', '50', False))
    assert formset.forms[0].has_sales
    assert formset.is_valid(), formset.errors
    formset.save()
    general.refresh_from_db()
    assert (general.name, general.price, general.quota) == ('General Plus', Decimal('1000.00'), 50)


def test_ticket_type_with_orders_cannot_be_deleted(event, seller, preference, general):
    sell(event, general)
    formset = bound_formset(event, (general, 'General', '1000', '', True))
    assert not formset.is_valid()
    assert formset.non_form_errors()


def test_ticket_type_without_orders_can_be_deleted(event, general):
    formset = bound_formset(event, (general, 'General', '1000', '', True))
    assert formset.is_valid(), formset.errors
    formset.save(commit=False)
    assert formset.deleted_objects == [general]


def test_event_page_shows_the_lowest_price(client, event, general, vip):
    event.is_paid = True
    event.save()
    EventDate.objects.create(event=event, date=timezone.localdate() + timedelta(days=10))
    content = client.get(reverse('index', args=[event.event_slug])).content.decode()
    assert 'Tickets from ARS 1000.00<' in content
    assert reverse('event_purchase', args=[event.event_slug]) in content


def test_events_api_exposes_the_price(client, event, general, vip):
    event.is_paid = True
    event.save()
    response = client.get(reverse('event-detail', args=[event.pk]))
    assert response.json()['is_paid'] is True
    assert response.json()['min_ticket_price'] == '1000.00'
