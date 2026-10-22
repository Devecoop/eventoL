# payments: cobro de entradas con Mercado Pago

App autocontenida que cobra órdenes de entradas con **Checkout Pro** en modo **marketplace**:
- la cuenta vendedora (por ejemplo, Gran Pez) recibe el pago;
- la aplicación de Devecoop retiene `MP_MARKETPLACE_FEE_PERCENT` como `marketplace_fee`.

Todavía no está conectada al flujo de registro de `manager` (ver [Integración](#integración)).

## Configuración

Variables en `.env` (documentadas en `.env.template`):

| Variable | Uso |
| --- | --- |
| `MP_CLIENT_ID`, `MP_CLIENT_SECRET` | Credenciales de la aplicación marketplace ("Tus integraciones") |
| `MP_OAUTH_REDIRECT_URI` | Redirect URI registrada en esa aplicación |
| `MP_WEBHOOK_SECRET` | Clave secreta de los webhooks. Obligatoria con `DEBUG=False` |
| `MP_TOKEN_ENCRYPTION_KEY` | Clave Fernet para cifrar los tokens de la vendedora |
| `MP_BASE_URL` | URL pública para webhooks y back URLs (por defecto `https://APP_DNS`) |
| `MP_MARKETPLACE_FEE_PERCENT` | Fee de Devecoop (por defecto 3) |
| `MP_RESERVATION_MINUTES` | Minutos que una orden pendiente reserva cupo (por defecto 30) |

Sin credenciales, las operaciones fallan: **nunca** se aprueba un pago sin Mercado Pago.

## Puesta en marcha

1. `python manage.py migrate`
2. Vincular la cuenta vendedora (una sola vez; el token se renueva solo):
   `python manage.py mp_link_seller`. Imprime la URL de autorización: abrirla logueado con la cuenta vendedora, aceptar y pegar la URL a la que redirige MP. `--event <slug>` vincula una cuenta solo para ese evento.
3. Reconciliación periódica (pagos cuyo webhook no llegó + renovación del token):
   - **cron:** `python manage.py sync_mp_orders`, por ejemplo cada 15 minutos;
   - **celery beat:** la tarea `payments.tasks.reconcile_pending_orders_task`.
4. Prueba en sandbox sin formulario: `python manage.py mp_create_test_order --event <slug> --price 1000 --qty 2`. Imprime la URL de pago.
   - Para recibir webhooks en local, exponer el servidor con un túnel (cloudflared/ngrok) y apuntar `MP_BASE_URL` a la URL del túnel.

## Modelo

- `SellerAccount`: cuenta vendedora con los tokens cifrados. `event` vacío = vendedora por defecto.
- `Order`: el UUID es el `external_reference` en MP.
  - Estados: `pending` → `approved` | `approved_over_quota` → `refunded`.
  - Los intentos rechazados no cambian el estado de la orden: el comprador puede reintentar.
- `OrderItem`: una entrada nominativa (nombre, apellido, DNI, email opcional).
- `Payment`: cada pago de MP de la orden. `validation_error` se completa si monto, moneda o collector no coinciden; ese pago nunca aprueba la orden.
- `WebhookEvent`: auditoría de notificaciones. Se deduplican por `x-request-id`.

## Flujo

1. `domain.create_order(event, buyer, attendees, unit_price, quota)`:
   - bloquea el evento y valida el cupo (pagadas + pendientes con reserva vigente);
   - crea la orden y la preferencia, y deja en `order.init_point` la URL de pago.
2. MP notifica a `POST /payments/mercadopago/webhook`:
   - se valida la firma y se guarda el `WebhookEvent`;
   - el pago se consulta en la API y se aplica con `domain.apply_payment`, en celery si `CELERY_ENABLED`, si no en la request.
   - `apply_payment` es idempotente y los estados solo avanzan.
3. El comprador vuelve a `/payments/order/<uuid>`, que se actualiza sola hasta ver el pago confirmado.
4. Si el pago llega después de vencida la reserva y no hay cupo, la orden queda en `approved_over_quota` para resolverla a mano. No se emite `order_paid`.

## Integración

Lo que falta para venderle al público (siguiente etapa):

- **Precio y cupo del evento** (`Event.is_paid`, `ticket_price`, `ticket_quota`, o tipos de entrada en E07). Se pasan a `create_order`.
- **Formulario de compra** (`/events/<slug>/purchase`): comprador + N asistentes → `create_order` → redirect a `order.init_point`.
- **Receiver de `payments.signals.order_paid`** en `manager`:
  - crea un `Attendee` + `Ticket` por `OrderItem` (y guarda `item.attendee`);
  - envía los tickets (`send_event_ticket`), usando `item.ticket_email`.
- **Receiver de `order_refunded`** para invalidar los tickets.

Las dos señales se envían después del commit, con el argumento `order`.

## Tests

```
cd eventol && pytest payments -p no:xdist
```

El SDK se mockea con `mock.patch('payments.services._build_sdk')` o con las funciones de `payments.services`.
