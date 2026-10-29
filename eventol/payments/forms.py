import re

from captcha.fields import CaptchaField
from django import forms
from django.utils.translation import gettext_lazy as _

from manager.models import Attendee
from payments.constants import MAX_TICKETS_PER_ORDER


class TicketSelectionForm(forms.Form):
    """How many tickets of each type: one field ``type_<id>`` by ticket type."""

    def __init__(self, *args, ticket_types, availability, **kwargs):
        super().__init__(*args, **kwargs)
        self.availability = availability
        for ticket_type in ticket_types:
            remaining = availability.for_type(ticket_type.pk)
            maximum = MAX_TICKETS_PER_ORDER if remaining is None else remaining
            maximum = min(maximum, MAX_TICKETS_PER_ORDER)
            field = forms.TypedChoiceField(
                label=ticket_type.name,
                choices=[(number, number) for number in range(maximum + 1)],
                coerce=int,
                empty_value=0,
                widget=forms.Select(attrs={'class': 'form-control'}),
                required=False,
                initial=0,
            )
            field.ticket_type = ticket_type
            field.remaining = remaining
            self.fields[self.field_name(ticket_type)] = field

    @staticmethod
    def field_name(ticket_type):
        return f'type_{ticket_type.pk}'

    def clean(self):
        cleaned_data = super().clean()
        counts = {
            field.ticket_type.pk: cleaned_data.get(name) or 0 for name, field in self.fields.items()
        }
        total = sum(counts.values())
        if total == 0:
            raise forms.ValidationError(_('Choose at least one ticket'))
        if total > MAX_TICKETS_PER_ORDER:
            raise forms.ValidationError(
                _('You can buy up to %(max)s tickets by order') % {'max': MAX_TICKETS_PER_ORDER}
            )
        if not self.availability.fits(counts):
            raise forms.ValidationError(_('There are not enough tickets left'))
        return cleaned_data

    def tickets(self):
        """The ticket type of each ticket of the order, in the order they are shown."""
        return [
            field.ticket_type
            for name, field in self.fields.items()
            for _number in range(self.cleaned_data.get(name) or 0)
        ]


class BuyerForm(forms.Form):
    name = forms.CharField(label=_('Full name'), max_length=200)
    email = forms.EmailField(label=_('Email'), help_text=_('We will send the tickets here'))
    phone = forms.CharField(label=_('Phone'), max_length=50)
    captcha = CaptchaField()


class AttendeeForm(forms.Form):
    first_name = forms.CharField(label=_('First Name'), max_length=200)
    last_name = forms.CharField(label=_('Last Name'), max_length=200)
    dni = forms.CharField(label=_('DNI'), max_length=20)
    email = forms.EmailField(
        label=_('Email'),
        required=False,
        help_text=_('Optional: the attendee also receives the ticket'),
    )

    def __init__(self, *args, ticket_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticket_type = ticket_type

    def clean_dni(self):
        dni = re.sub(r'[\s.-]', '', self.cleaned_data['dni'])
        if not dni.isalnum():
            raise forms.ValidationError(_('Enter only the numbers of the DNI'))
        return dni


class BaseAttendeeFormSet(forms.BaseFormSet):
    def __init__(self, *args, event, tickets, **kwargs):
        self.event = event
        self.tickets = tickets
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        if index is not None and index < len(self.tickets):
            kwargs['ticket_type'] = self.tickets[index]
        return kwargs

    def clean(self):
        if any(self.errors):
            return
        dnis = [form.cleaned_data['dni'] for form in self.forms]
        if len(set(dnis)) != len(dnis):
            raise forms.ValidationError(_('Each ticket needs a different DNI'))
        registered = set(
            Attendee.objects.filter(event=self.event, dni__in=dnis).values_list('dni', flat=True)
        )
        for form in self.forms:
            if form.cleaned_data['dni'] in registered:
                form.add_error('dni', _('There is already a ticket for this DNI'))


def attendee_formset(quantity):
    """Formset with exactly ``quantity`` attendees."""
    return forms.formset_factory(
        AttendeeForm,
        formset=BaseAttendeeFormSet,
        extra=0,
        min_num=quantity,
        max_num=quantity,
        validate_min=True,
        validate_max=True,
    )
