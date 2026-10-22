from django.urls import path

from payments import views

urlpatterns = [
    path('mercadopago/webhook', views.mercadopago_webhook, name='payments_mercadopago_webhook'),
    path('order/<uuid:order_id>', views.order_status, name='payments_order_status'),
]
