import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from manager.models import Attendee, Event
from payments import crypto


class SellerAccountNotConfiguredError(Exception):
    pass


class SellerAccount(models.Model):
    """Mercado Pago account that receives the money, linked by OAuth to the marketplace app.

    ``event`` empty means the default seller of the instance.
    """

    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    mp_user_id = models.CharField(_('Mercado Pago user id'), max_length=50, unique=True)
    event = models.ForeignKey(
        Event,
        verbose_name=_('Event'),
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        help_text=_('Leave empty to use this account for every event'),
    )
    public_key = models.CharField(_('Public key'), max_length=200, blank=True)
    encrypted_access_token = models.TextField(editable=False)
    encrypted_refresh_token = models.TextField(editable=False)
    expires_at = models.DateTimeField(_('Token expires at'))

    class Meta:
        verbose_name = _('Seller account')
        verbose_name_plural = _('Seller accounts')

    def __str__(self):
        return f'{self.mp_user_id} ({self.event or _("default")})'

    @property
    def access_token(self):
        return crypto.decrypt(self.encrypted_access_token)

    @access_token.setter
    def access_token(self, value):
        self.encrypted_access_token = crypto.encrypt(value)

    @property
    def refresh_token(self):
        return crypto.decrypt(self.encrypted_refresh_token)

    @refresh_token.setter
    def refresh_token(self, value):
        self.encrypted_refresh_token = crypto.encrypt(value)

    def expires_soon(self, days=30):
        return self.expires_at <= timezone.now() + timedelta(days=days)

    @classmethod
    def for_event(cls, event):
        seller = (
            cls.objects.filter(event=event).first()
            or cls.objects.filter(event__isnull=True).first()
        )
        if seller is None:
            raise SellerAccountNotConfiguredError(
                _('There is no Mercado Pago account linked. Run "mp_link_seller".')
            )
        return seller


class OrderQuerySet(models.QuerySet):
    def holding_quota(self, now=None):
        """Orders whose items count against the event quota."""
        now = now or timezone.now()
        return self.filter(
            models.Q(status__in=Order.PAID_STATUSES)
            | models.Q(status=Order.Status.PENDING, reserved_until__gt=now)
        )


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        APPROVED_OVER_QUOTA = 'approved_over_quota', _('Approved over quota')
        REFUNDED = 'refunded', _('Refunded')

    PAID_STATUSES = (Status.APPROVED, Status.APPROVED_OVER_QUOTA)

    objects = OrderQuerySet.as_manager()

    # The id is sent to Mercado Pago as external_reference
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # pylint: disable=invalid-name
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    event = models.ForeignKey(Event, verbose_name=_('Event'), on_delete=models.PROTECT)
    seller = models.ForeignKey(
        SellerAccount, verbose_name=_('Seller account'), on_delete=models.PROTECT
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('User'),
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    status = models.CharField(
        _('Status'), max_length=30, choices=Status.choices, default=Status.PENDING
    )
    buyer_name = models.CharField(_('Buyer name'), max_length=200)
    buyer_email = models.EmailField(_('Buyer email'))
    buyer_phone = models.CharField(_('Buyer phone'), max_length=50)
    quantity = models.PositiveIntegerField(_('Quantity'))
    unit_price = models.DecimalField(_('Unit price'), max_digits=12, decimal_places=2)
    total = models.DecimalField(_('Total'), max_digits=12, decimal_places=2)
    marketplace_fee = models.DecimalField(_('Marketplace fee'), max_digits=12, decimal_places=2)
    currency = models.CharField(_('Currency'), max_length=3, default='ARS')
    quota = models.PositiveIntegerField(
        _('Event quota'),
        blank=True,
        null=True,
        help_text=_('Quota of the event when the order was created'),
    )
    reserved_until = models.DateTimeField(_('Reserved until'))
    preference_id = models.CharField(_('Preference id'), max_length=100, blank=True)
    init_point = models.URLField(_('Checkout URL'), max_length=500, blank=True)
    paid_at = models.DateTimeField(_('Paid at'), blank=True, null=True)

    class Meta:
        verbose_name = _('Order')
        verbose_name_plural = _('Orders')
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.event} - {self.buyer_email} ({self.get_status_display()})'

    @property
    def external_reference(self):
        return str(self.id)

    @property
    def is_paid(self):
        return self.status in self.PAID_STATUSES


class OrderItem(models.Model):
    """One ticket of the order. The attendee is created when the order is paid."""

    order = models.ForeignKey(
        Order, verbose_name=_('Order'), related_name='items', on_delete=models.CASCADE
    )
    first_name = models.CharField(_('First Name'), max_length=200)
    last_name = models.CharField(_('Last Name'), max_length=200)
    dni = models.CharField(_('DNI'), max_length=20)
    email = models.EmailField(_('Email'), blank=True)
    attendee = models.ForeignKey(
        Attendee, verbose_name=_('Attendee'), blank=True, null=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name = _('Order item')
        verbose_name_plural = _('Order items')

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.dni})'

    @property
    def ticket_email(self):
        return self.email or self.order.buyer_email


class Payment(models.Model):
    """A Mercado Pago payment attempt of an order.

    An order may have rejected attempts before the approved one.
    """

    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    order = models.ForeignKey(
        Order, verbose_name=_('Order'), related_name='payments', on_delete=models.CASCADE
    )
    mp_payment_id = models.CharField(_('Mercado Pago payment id'), max_length=50, unique=True)
    status = models.CharField(_('Status'), max_length=30)
    status_detail = models.CharField(_('Status detail'), max_length=100, blank=True)
    transaction_amount = models.DecimalField(_('Amount'), max_digits=12, decimal_places=2)
    currency = models.CharField(_('Currency'), max_length=3)
    collector_id = models.CharField(_('Collector id'), max_length=50, blank=True)
    payment_method = models.CharField(_('Payment method'), max_length=50, blank=True)
    date_approved = models.DateTimeField(_('Date approved'), blank=True, null=True)
    validation_error = models.TextField(
        _('Validation error'),
        blank=True,
        help_text=_(
            'Set when the payment does not match the order (amount, currency or collector)'
        ),
    )
    raw = models.JSONField(_('Mercado Pago data'), default=dict)

    class Meta:
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.mp_payment_id} ({self.status})'


class WebhookEvent(models.Model):
    """Every notification received from Mercado Pago, for auditing and deduplication."""

    received_at = models.DateTimeField(_('Received at'), auto_now_add=True)
    request_id = models.CharField(
        _('Request id'), max_length=100, blank=True, null=True, unique=True
    )
    topic = models.CharField(_('Topic'), max_length=50, blank=True)
    action = models.CharField(_('Action'), max_length=50, blank=True)
    resource_id = models.CharField(_('Resource id'), max_length=50, blank=True)
    mp_user_id = models.CharField(_('Mercado Pago user id'), max_length=50, blank=True)
    payload = models.JSONField(_('Payload'), default=dict)
    attempts = models.PositiveIntegerField(_('Attempts'), default=0)
    processed_at = models.DateTimeField(_('Processed at'), blank=True, null=True)
    error = models.TextField(_('Error'), blank=True)

    class Meta:
        verbose_name = _('Webhook event')
        verbose_name_plural = _('Webhook events')
        ordering = ('-received_at',)

    def __str__(self):
        return f'{self.topic}:{self.resource_id} ({self.received_at:%Y-%m-%d %H:%M})'
