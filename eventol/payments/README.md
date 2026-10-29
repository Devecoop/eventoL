# payments: cobro de entradas con Mercado Pago

App autocontenida que cobra órdenes de entradas con **Checkout Pro** en modo **marketplace**:
- la cuenta vendedora (por ejemplo, la organización del evento) recibe el pago;
- la aplicación de Devecoop retiene `MP_MARKETPLACE_FEE_PERCENT` como `marketplace_fee`.

Los eventos con `is_paid` venden sus entradas desde `/events/<slug>/purchase` (ver [Integración](#integración)).

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
   `python manage.py mp_link_seller`. Imprime la URL de autorización: abrirla logueado con la cuenta vendedora, aceptar y pegar la URL a la que redirige MP. Hay una sola cuenta vendedora para toda la instancia: vincular otra cuenta la reemplaza para las órdenes nuevas.
3. Reconciliación periódica (pagos cuyo webhook no llegó + renovación del token):
   - **cron:** `python manage.py sync_mp_orders`, por ejemplo cada 15 minutos;
   - **celery beat:** la tarea `payments.tasks.reconcile_pending_orders_task`.
4. Prueba en sandbox sin formulario: `python manage.py mp_create_test_order --event <slug> --qty 2 [--type VIP]`. Usa un tipo de entrada del evento (por defecto, el más barato) e imprime la URL de pago.
   - Para recibir webhooks en local, exponer el servidor con un túnel (cloudflared/ngrok) y apuntar `MP_BASE_URL` a la URL del túnel.

## Modelo

- `SellerAccount`: cuenta vendedora con los tokens cifrados. Las órdenes nuevas usan la última vinculada (`SellerAccount.current()`); las anteriores quedan para sus órdenes.
- `Order`: el UUID es el `external_reference` en MP.
  - Estados: `pending` → `approved` | `approved_over_quota` → `refunded`.
  - Los intentos rechazados no cambian el estado de la orden: el comprador puede reintentar.
- `OrderItem`: una entrada nominativa (nombre, apellido, DNI, email opcional), con su tipo de entrada y el precio al que se vendió.
- `Payment`: cada pago de MP de la orden. `validation_error` se completa si monto, moneda o collector no coinciden; ese pago nunca aprueba la orden.
- `WebhookEvent`: auditoría de notificaciones. Se deduplican por `x-request-id`.

## Flujo

1. `domain.create_order(event, buyer, attendees)` (cada asistente con su `ticket_type`):
   - bloquea el evento y valida el cupo de cada tipo y el aforo del evento (pagadas + pendientes con reserva vigente; `domain.availability`);
   - crea la orden y la preferencia, y deja en `order.init_point` la URL de pago.
2. MP notifica a `POST /payments/mercadopago/webhook`:
   - se valida la firma y se guarda el `WebhookEvent`;
   - el pago se consulta en la API y se aplica con `domain.apply_payment`, en celery si `CELERY_ENABLED`, si no en la request.
   - `apply_payment` es idempotente y los estados solo avanzan.
3. El comprador vuelve a `/payments/order/<uuid>`, que se actualiza sola hasta ver el pago confirmado.
4. Si el pago llega después de vencida la reserva y no hay cupo, la orden queda en `approved_over_quota` para resolverla a mano. No se emite `order_paid`.

## Integración

- **Evento:** `Event.is_paid` y `ticket_quota` (aforo total opcional). `EventForm` no deja marcar un evento como pago sin una `SellerAccount` vinculada.
- **Tipos de entrada:** `TicketType` (nombre, precio > 0 y cupo opcional), cargados en la sección "Tickets" del formulario del evento. Un tipo con ventas no cambia de precio, y uno con órdenes no se puede borrar. Un evento pago sin tipos muestra "Entradas próximamente".
- **Compra:** `payments.views.purchase` (`/events/<slug>/purchase`, nombre `event_purchase`):
  - primero se elige cuántas entradas de cada tipo (hasta 10 en total, y hasta el cupo del tipo y el aforo);
  - después se cargan el comprador (con captcha) y los N asistentes (nombre, apellido, DNI y email opcional);
  - se rechazan los DNIs repetidos en la orden o que ya tienen entrada en el evento;
  - `create_order` y redirección a `order.init_point`.
- **Registro gratuito:** en un evento pago, `/registration` y los enlaces de registro llevan a la compra y el autoregistro con QR se desactiva. La carga por colaboradores sigue disponible (invitaciones).
- **Receivers** en `manager/receivers.py`; las dos señales se envían después del commit, con el argumento `order`:
  - `order_paid` crea un `Attendee` (con DNI y tipo de entrada) y su `Ticket` por `OrderItem`. Envía un mail al comprador con todas las entradas y el detalle por tipo, y a cada asistente con email propio la suya. Si un DNI ya tiene entrada, ese ítem no se emite y queda en el log para revisarlo a mano.
  - `order_refunded` anula los tickets (`Ticket.cancelled`). El escáner y la búsqueda de asistencia no registran el ingreso de un ticket anulado.
- **Unicidad de asistentes:** el DNI es único por evento (cuando existe). El email se valida en los formularios del registro gratuito.

## Tests

```
cd eventol && pytest payments -p no:xdist
```

El SDK se mockea con `mock.patch('payments.services._build_sdk')` o con las funciones de `payments.services`.
