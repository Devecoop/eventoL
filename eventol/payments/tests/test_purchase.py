# pylint: disable=redefined-outer-name,unused-argument
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from manager.models import Attendee, EventDate
from payments.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture
def paid_event(event, captcha_passes):
    EventDate.objects.create(event=event, date=timezone.localdate() + timedelta(days=10))
    event.is_paid = True
    event.save()
    return event


def purchase_data(*dnis, emails=None):
    emails = emails or [''] * len(dnis)
    data = {
        'name': 'Ana Garcia',
        'email': 'ana@example.com',
        'phone': '1122334455',
        'captcha_0': 'key',
        'captcha_1': 'PASSED',
        'attendees-TOTAL_FORMS': str(len(dnis)),
        'attendees-INITIAL_FORMS': '0',
        'attendees-MIN_NUM_FORMS': str(len(dnis)),
        'attendees-MAX_NUM_FORMS': str(len(dnis)),
    }
    for index, (dni, email) in enumerate(zip(dnis, emails)):
        data.update(
            {
                f'attendees-{index}-first_name': f'Person {index}',
                f'attendees-{index}-last_name': 'Garcia',
                f'attendees-{index}-dni': dni,
                f'attendees-{index}-email': email,
            }
        )
    return data


def url_for(event, *pairs):
    url = reverse('event_purchase', args=[event.event_slug])
    query = '&'.join(f'type_{ticket_type.pk}={number}' for ticket_type, number in pairs)
    return f'{url}?{query}' if query else url


def test_purchase_asks_for_the_ticket_types_first(client, paid_event, seller, general, vip):
    response = client.get(url_for(paid_event))
    assert response.status_code == 200
    form = response.context['selection_form']
    assert [field.label for field in form] == ['General', 'VIP']
    assert 'formset' not in response.context


def test_quantity_choices_are_limited_by_the_quota(client, paid_event, seller, general, vip):
    response = client.get(url_for(paid_event))
    fields = response.context['selection_form'].fields
    assert [value for value, _label in fields[f'type_{vip.pk}'].choices] == [0, 1, 2]
    assert len(fields[f'type_{general.pk}'].choices) == 11


def test_at_least_one_ticket(client, paid_event, seller, general):
    response = client.get(url_for(paid_event, (general, 0)))
    assert response.context['selection_form'].non_field_errors()


def test_up_to_ten_tickets_by_order(client, paid_event, seller, general, vip):
    response = client.get(url_for(paid_event, (general, 9), (vip, 2)))
    assert response.context['selection_form'].non_field_errors()


def test_event_capacity_is_checked_on_the_selection(client, paid_event, seller, general, vip):
    paid_event.ticket_quota = 2
    paid_event.save()
    response = client.get(url_for(paid_event, (general, 2), (vip, 1)))
    assert response.context['selection_form'].non_field_errors()


def test_attendees_form_shows_the_chosen_types(client, paid_event, seller, general, vip):
    response = client.get(url_for(paid_event, (general, 2), (vip, 1)))
    assert [form.ticket_type for form in response.context['formset']] == [general, general, vip]
    assert response.context['total'] == Decimal('5000')


def test_purchase_creates_the_order_and_redirects_to_mercado_pago(
    client, paid_event, seller, preference, general, vip
):
    response = client.post(
        url_for(paid_event, (general, 1), (vip, 1)), purchase_data('30.000.000', '30000001')
    )
    assert response.status_code == 302
    assert response.url == 'https://mp.test/checkout'
    order = Order.objects.get()
    assert order.quantity == 2
    assert order.total == Decimal('4000')
    assert order.buyer_email == 'ana@example.com'
    assert sorted(order.items.values_list('dni', 'ticket_type__name')) == [
        ('30000000', 'General'),
        ('30000001', 'VIP'),
    ]


def test_purchase_rejects_repeated_dni(client, paid_event, seller, preference, general):
    response = client.post(url_for(paid_event, (general, 2)), purchase_data('30000000', '30000000'))
    assert response.status_code == 200
    assert response.context['formset'].non_form_errors()
    assert not Order.objects.exists()


def test_purchase_rejects_dni_with_ticket(client, paid_event, seller, preference, general):
    Attendee.objects.create(event=paid_event, email='old@example.com', dni='30000000')
    response = client.post(url_for(paid_event, (general, 1)), purchase_data('30000000'))
    assert response.status_code == 200
    assert response.context['formset'].forms[0].errors['dni']
    assert not Order.objects.exists()


def test_purchase_without_tickets_left(client, paid_event, seller, preference, vip):
    client.post(url_for(paid_event, (vip, 2)), purchase_data('30000000', '30000001'))
    response = client.get(url_for(paid_event))
    assert response.context['sold_out']
    assert 'selection_form' not in response.context


def test_paid_event_without_ticket_types(client, paid_event, seller):
    response = client.get(url_for(paid_event))
    assert not response.context['ticket_types']
    assert 'selection_form' not in response.context
    assert 'Tickets coming soon' in response.content.decode()


def test_purchase_of_free_event_goes_to_registration(client, event):
    response = client.get(url_for(event))
    assert response.url == reverse('attendee_registration', args=[event.event_slug])


def test_registration_of_paid_event_goes_to_purchase(client, paid_event):
    response = client.get(reverse('attendee_registration', args=[paid_event.event_slug]))
    assert response.url == reverse('event_purchase', args=[paid_event.event_slug])
