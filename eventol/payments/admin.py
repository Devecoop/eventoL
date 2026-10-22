from django.contrib import admin

from payments.models import Order, OrderItem, Payment, SellerAccount, WebhookEvent


class ReadOnlyAdminMixin:
    """Payments are written only by Mercado Pago notifications and the reconciliation."""

    def has_add_permission(self, request, obj=None):  # pylint: disable=unused-argument
        return False

    def has_change_permission(self, request, obj=None):  # pylint: disable=unused-argument
        return False

    def has_delete_permission(self, request, obj=None):  # pylint: disable=unused-argument
        return False


class OrderItemInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = OrderItem
    fields = ('first_name', 'last_name', 'dni', 'email', 'attendee')
    readonly_fields = fields
    extra = 0


class PaymentInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = Payment
    fields = (
        'mp_payment_id',
        'status',
        'status_detail',
        'transaction_amount',
        'payment_method',
        'date_approved',
        'validation_error',
    )
    readonly_fields = fields
    extra = 0


@admin.register(Order)
class OrderAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        'id',
        'event',
        'buyer_email',
        'quantity',
        'total',
        'status',
        'created_at',
        'paid_at',
    )
    list_filter = ('status', 'event')
    search_fields = ('id', 'buyer_email', 'buyer_name', 'items__dni', 'payments__mp_payment_id')
    readonly_fields = [field.name for field in Order._meta.fields]
    inlines = (OrderItemInline, PaymentInline)


@admin.register(Payment)
class PaymentAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        'mp_payment_id',
        'order',
        'status',
        'transaction_amount',
        'validation_error',
        'created_at',
    )
    list_filter = ('status',)
    search_fields = ('mp_payment_id', 'order__id', 'order__buyer_email')
    readonly_fields = [field.name for field in Payment._meta.fields]


@admin.register(WebhookEvent)
class WebhookEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        'received_at',
        'topic',
        'action',
        'resource_id',
        'attempts',
        'processed_at',
        'error',
    )
    list_filter = ('topic', 'processed_at')
    search_fields = ('resource_id', 'request_id')
    readonly_fields = [field.name for field in WebhookEvent._meta.fields]


@admin.register(SellerAccount)
class SellerAccountAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    # Tokens are never shown; use the mp_link_seller command to link an account
    list_display = ('mp_user_id', 'event', 'expires_at', 'updated_at')
    fields = ('mp_user_id', 'event', 'public_key', 'expires_at', 'created_at', 'updated_at')
    readonly_fields = fields
