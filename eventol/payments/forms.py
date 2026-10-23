import re

from captcha.fields import CaptchaField
from django import forms
from django.utils.translation import gettext_lazy as _

from manager.models import Attendee

MAX_TICKETS_PER_ORDER = 10


class TicketQuantityForm(forms.Form):
    quantity = forms.TypedChoiceField(label=_('Tickets'), coerce=int)

    def __init__(self, *args, max_quantity=MAX_TICKETS_PER_ORDER, **kwargs):
        super().__init__(*args, **kwargs)
        max_quantity = min(max_quantity, MAX_TICKETS_PER_ORDER)
        self.fields['quantity'].choices = [(n, n) for n in range(1, max_quantity + 1)]


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

    def clean_dni(self):
        dni = re.sub(r'[\s.-]', '', self.cleaned_data['dni'])
        if not dni.isalnum():
            raise forms.ValidationError(_('Enter only the numbers of the DNI'))
        return dni


class BaseAttendeeFormSet(forms.BaseFormSet):
    def __init__(self, *args, event, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)

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
