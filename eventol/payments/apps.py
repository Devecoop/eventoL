from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PaymentsConfig(AppConfig):
    name = 'payments'
    verbose_name = _('Payments')
    default_auto_field = 'django.db.models.BigAutoField'
