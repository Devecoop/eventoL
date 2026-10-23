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
    event.ticket_price = Decimal('1000')
    event.save()
    return event


def purchase_url(event, quantity=None):
    url = reverse('event_purchase', args=[event.event_slug])
    return f'{url}?quantity={quantity}' if quantity else url


def purchase_data(*dnis, emails=None):
    emails = emails or [''] * len(dnis)
    data = {
        'name': 'Ana Pez',
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
                f'attendees-{index}-last_name': 'Pez',
                f'attendees-{index}-dni': dni,
                f'attendees-{index}-email': email,
            }
        )
    return data


def test_purchase_asks_for_the_quantity_first(client, paid_event, seller):
    response = client.get(purchase_url(paid_event))
    assert response.status_code == 200
    assert 'quantity_form' in response.context
    assert 'formset' not in response.context


def test_quantity_choices_are_limited_by_the_quota(client, paid_event, seller):
    paid_event.ticket_quota = 3
    paid_event.save()
    response = client.get(purchase_url(paid_event))
    choices = response.context['quantity_form'].fields['quantity'].choices
    assert [value for value, _label in choices] == [1, 2, 3]


def test_purchase_creates_the_order_and_redirects_to_mercado_pago(
    client, paid_event, seller, preference
):
    response = client.post(purchase_url(paid_event, 2), purchase_data('30.000.000', '30000001'))
    assert response.status_code == 302
    assert response.url == 'https://mp.test/checkout'
    order = Order.objects.get()
    assert order.quantity == 2
    assert order.total == Decimal('2000')
    assert order.buyer_email == 'ana@example.com'
    assert sorted(order.items.values_list('dni', flat=True)) == ['30000000', '30000001']


def test_purchase_rejects_repeated_dni(client, paid_event, seller, preference):
    response = client.post(purchase_url(paid_event, 2), purchase_data('30000000', '30000000'))
    assert response.status_code == 200
    assert response.context['formset'].non_form_errors()
    assert not Order.objects.exists()


def test_purchase_rejects_dni_with_ticket(client, paid_event, seller, preference):
    Attendee.objects.create(event=paid_event, email='old@example.com', dni='30000000')
    response = client.post(purchase_url(paid_event, 1), purchase_data('30000000'))
    assert response.status_code == 200
    assert response.context['formset'].forms[0].errors['dni']
    assert not Order.objects.exists()


def test_purchase_without_tickets_left(client, paid_event, seller, preference):
    paid_event.ticket_quota = 1
    paid_event.save()
    client.post(purchase_url(paid_event, 1), purchase_data('30000000'))
    response = client.get(purchase_url(paid_event))
    assert response.context['available'] == 0
    assert 'quantity_form' not in response.context


def test_purchase_of_free_event_goes_to_registration(client, event):
    response = client.get(purchase_url(event))
    assert response.url == reverse('attendee_registration', args=[event.event_slug])


def test_registration_of_paid_event_goes_to_purchase(client, paid_event):
    response = client.get(reverse('attendee_registration', args=[paid_event.event_slug]))
    assert response.url == reverse('event_purchase', args=[paid_event.event_slug])
