# Verificación de pantallas y flujos — 27 de octubre de 2026

Se realizaron 125 comprobaciones de rutas y estados (123 direcciones distintas),
incluidos 66 casos del administrador de modelos de eventoL. Se revisaron los
122 casos HTML a 1440 y 390 px; los tres restantes son dos PDF y una exportación
CSV. Se guardaron 244 capturas HTML y capturas adicionales de interacciones.
Los 60 controles de acceso de la matriz cubrieron anónimo, usuario común,
organizador, colaborador, instalador y revisor; no produjeron errores 500.

La revisión **encontró problemas pendientes**. Que una página responda HTTP 200
no significa que todos sus recursos e interacciones funcionen.

## Hallazgos

| Prioridad | Pantalla o recurso | Resultado y reproducción |
| --- | --- | --- |
| Alta | CAPTCHA de propuestas y edición | `/captcha/image/<clave>/` devuelve 500: `FreeTypeFont` no tiene `getsize`. La dependencia instalada `django-simple-captcha==0.5.6` usa una API eliminada de Pillow. El usuario no puede leer la imagen para completar normalmente el formulario. |
| Alta | Sorteos | Faltan el JS y CSS de `manager/bower_components/jquery-slotmachine/dist/` (404). Pulsar «Shuffle!» produce `$(...).slotMachine is not a function`; no se inicia el sorteo. |
| Media | Reportes del evento | Una fecha sin asistencias omite su contenedor de gráfico, pero el JavaScript intenta crear `Morris.Line`: `Graph container element not found`. La página y algunos gráficos aparecen; la inicialización se interrumpe. |
| Media | Recorte de actividad sin ID | `/events/<evento>/activity/proposal/image-cropping/` devuelve 500 porque la vista exige `activity_id`. La variante con ID y la carga/recorte de imágenes sí funcionan. |
| Visual | Administración Django en móvil | Conserva un ancho de aproximadamente 980 px y requiere desplazamiento horizontal a 390 px. Usa los estilos propios del administrador antiguo. |
| Visual | Páginas heredadas de etiquetas e información de instancia | Conservan la portada React y el diseño anterior. En la etiqueta móvil se observan textos/controles superpuestos. No tienen todavía la estructura nueva de la home. |

Referencias de código:

- CAPTCHA: versión fijada en `requirements.txt`; la excepción se origina en la
  dependencia `captcha/views.py`. La prueba de imágenes se hizo con el servidor
  normal, sin el adaptador de Pillow que se utilizó anteriormente para las suites.
- Sorteos: `manager/templates/event/draw.html` referencia los dos recursos
  ausentes e invoca el plugin al pulsar el botón.
- Reportes: `manager/templates/reports/dashboard.html` crea el contenedor solo
  cuando existen asistencias de la fecha, pero su bucle de JavaScript no aplica
  la misma condición.
- Recorte: `manager/urls/event.py` registra ambas variantes y
  `manager/views.py:image_cropping` exige el identificador.

Los archivos anteriores de vistas, rutas y plantillas de reportes/sorteos no
fueron modificados por la reorganización del diseño. Estos hallazgos no se
corrigieron durante esta revisión. El administrador tampoco carga el tema de
Bootstrap de la aplicación. No se atribuye a las variables de diseño ninguno
de esos errores de backend, recursos o inicialización.

## Flujos comprobados

Se ejecutaron 16 comprobaciones de persistencia/validación con clientes Django:

- **Salas CRUD**: crear, editar y eliminar sala; datos persistidos y eliminados.
- **Creacion de evento**: /events/audit-created/image-cropping/.
- **Inscripcion de asistente y entrada**: inscripcion, confirmacion y PDF de entrada.
- **Registro como colaborador**: rol guardado.
- **Registro como instalador**: rol guardado.
- **Propuestas crear y editar**: crear y editar propuesta con CAPTCHA generado en la base temporal.
- **Revision y cronograma**: votos, rechazo, reenvio, aceptacion, confirmacion y HTML de calendario verificados.
- **Acreditacion por colaborador**: alta de asistente y acreditacion por codigo de entrada.
- **Autoacreditacion**: registro y presencia en fecha del evento.
- **Registro de instalacion**: hardware e instalacion guardados.
- **Errores de validacion de formularios**: ['add_room', 'activity_proposal', 'installation', 'attendee_registration_by_collaborator'].
- **Cronograma confirmado**: cronograma confirmado con sala y horarios persistidos.
- **Cuentas y acceso**: alta, verificacion de correo, cambio de clave, salida, ingreso y solicitud de recuperacion; correos solo en archivos temporales.
- **Contacto**: mensaje persistido y correo generado en archivo local.
- **Imagenes y recorte con identificador**: carga y recorte de portada y actividad; archivos solo en MEDIA_ROOT temporal.
- **Recuperacion de clave por enlace**: formulario de recuperacion y nueva clave verificada en la base temporal.

Las pruebas de propuestas proporcionaron el CAPTCHA correcto desde la base
**temporal** para comprobar el guardado del formulario y su edición. Esto no
resuelve el error de la imagen CAPTCHA ni demuestra que una persona pueda
completar actualmente ese recorrido desde la interfaz.

También se ejercitaron en Chrome el ingreso con formulario y CSRF real, la
creación/edición/eliminación de salas en escritorio y móvil, y el calendario
confirmado renderizado por FullCalendar. El calendario con una sala no presentó
desbordamiento horizontal a 390 px. Se pulsó el botón de sorteo para confirmar
la falla del plugin; no se consideró suficiente que cargara la pantalla.

La lista de actividades anónima devuelve 403 por la configuración vigente
`PRIVATE_ACTIVITIES`; también se abrió con un revisor autorizado. Las
redirecciones por sesión, rol, inscripción cerrada o cronograma confirmado se
registran como tales, sin confundirlas con errores del servidor.

## Aislamiento y límites

- Se creó una copia temporal de la base local, con nombre
  `eventol_audit_3ab22f6aa4`, y un servidor separado en el puerto 8001 del
  contenedor. Las cuentas, eventos, asistencias, archivos y cambios de prueba
  pertenecieron exclusivamente a ese entorno.
- El correo de pruebas se escribió en archivos locales mediante el backend de
  Django; no se envió correo real ni se contactó a organizadores o asistentes.
- Se confirmó que la base local conserva un evento, cero eventos `audit-*` y
  cero usuarios `audit_*`. No se modificó su contenido para ejecutar los flujos.
- El QR se abrió además desde `localhost` mediante un proxy temporal: carga sin
  la excepción de contexto inseguro observada al acceder por una IP HTTP.
  No se validó la lectura física con cámara ni un QR real; requiere un dispositivo
  y permiso de cámara. El registro por código de entrada sí se comprobó.
- No se probó OAuth real con Google/GitHub/Twitter, entrega SMTP, proveedores de
  mapas externos, todas las combinaciones de campos ni otros navegadores.
- Se visitaron los listados y formularios de alta/cambio disponibles de los
  modelos registrados de `manager` y el índice del administrador. No se afirma
  haber ejercitado todas las acciones de administración de Django o de plugins
  externos, ni todas las combinaciones de estados posibles.
- Las capturas registran ventanas de 1000 px de alto. La detección de
  desbordamiento y de recursos fallidos abarca el documento; esto no equivale
  a una inspección manual de cada píxel de formularios extensos.

## Evidencia y reproducción

Los scripts, resultados JSON, capturas y hojas de revisión están en
`/tmp/eventol-flow-audit/` en este equipo. Los registros del servidor y de acciones
se guardaron como `/tmp/eventol-audit-*.log` y `/tmp/eventol-flow-server.log` en
`eventol-dev-worker-1`. Son archivos temporales, no parte del repositorio.
La base y los procesos auxiliares se retiran al terminar; las evidencias se
conservan en `/tmp`. Django y Webpack del desarrollo normal continúan disponibles.

Para repetir la revisión, crear otra base aislada antes de ejecutar los scripts;
`seed.py` y los scripts de acciones escriben datos. No ejecutarlos contra la base
local del usuario. El adaptador temporal de Pillow utilizado por las suites
anteriores no debe ocultar la falla real del endpoint CAPTCHA en esta revisión.

## Matriz de rutas y estados

Los códigos indican la respuesta inicial del servidor. Chrome siguió las
redirecciones al revisar las pantallas. Los PDF y CSV se verificaron como
descargas, no como HTML. Los recursos CAPTCHA, el botón de sorteo y los gráficos
se evalúan por separado en los hallazgos anteriores.

| Comprobación | Perfil | Ruta | HTTP |
| --- | --- | --- | --- |
| `home` | Anónimo | `/` | 200 |
| `tag_index` | Anónimo | `/tags/audit-flow` | 200 |
| `generic_report` | Anónimo | `/report` | 200 |
| `instance_details` | Anónimo | `/instance_details` | 200 |
| `create_event` | Usuario | `/create-event/` | 200 |
| `account_login` | Anónimo | `/accounts/login/` | 200 |
| `account_signup` | Anónimo | `/accounts/signup/` | 200 |
| `account_reset_password` | Anónimo | `/accounts/password/reset/` | 200 |
| `user_profile` | Usuario | `/accounts/profile/` | 200 |
| `account_email` | Usuario | `/accounts/email/` | 200 |
| `account_change_password` | Usuario | `/accounts/password/change/` | 200 |
| `account_logout` | Usuario | `/accounts/logout/` | 200 |
| `admin:index` | Administrador | `/admin/` | 200 |
| `index_closed` | Usuario | `/events/audit-closed/` | 200 |
| `attendee_registration_closed` | Usuario | `/events/audit-closed/registration` | 200 |
| `activity_proposal_closed` | Usuario | `/events/audit-closed/activity/proposal/` | 302 |
| `schedule_closed` | Usuario | `/events/audit-closed/schedule` | 200 |
| `admin:manager_activity_changelist` | Administrador | `/admin/manager/activity/` | 200 |
| `admin:manager_activity_add` | Administrador | `/admin/manager/activity/add/` | 200 |
| `admin:manager_activity_change` | Administrador | `/admin/manager/activity/3/change/` | 200 |
| `admin:manager_activitytype_changelist` | Administrador | `/admin/manager/activitytype/` | 200 |
| `admin:manager_activitytype_add` | Administrador | `/admin/manager/activitytype/add/` | 200 |
| `admin:manager_activitytype_change` | Administrador | `/admin/manager/activitytype/1/change/` | 200 |
| `admin:manager_attendee_changelist` | Administrador | `/admin/manager/attendee/` | 200 |
| `admin:manager_attendee_add` | Administrador | `/admin/manager/attendee/add/` | 200 |
| `admin:manager_attendee_change` | Administrador | `/admin/manager/attendee/2/change/` | 200 |
| `admin:manager_attendeeattendancedate_changelist` | Administrador | `/admin/manager/attendeeattendancedate/` | 200 |
| `admin:manager_attendeeattendancedate_add` | Administrador | `/admin/manager/attendeeattendancedate/add/` | 200 |
| `admin:manager_collaborator_changelist` | Administrador | `/admin/manager/collaborator/` | 200 |
| `admin:manager_collaborator_add` | Administrador | `/admin/manager/collaborator/add/` | 200 |
| `admin:manager_collaborator_change` | Administrador | `/admin/manager/collaborator/2/change/` | 200 |
| `admin:manager_contact_changelist` | Administrador | `/admin/manager/contact/` | 200 |
| `admin:manager_contact_add` | Administrador | `/admin/manager/contact/add/` | 200 |
| `admin:manager_contact_change` | Administrador | `/admin/manager/contact/1/change/` | 200 |
| `admin:manager_contactmessage_changelist` | Administrador | `/admin/manager/contactmessage/` | 200 |
| `admin:manager_contactmessage_add` | Administrador | `/admin/manager/contactmessage/add/` | 200 |
| `admin:manager_contacttype_changelist` | Administrador | `/admin/manager/contacttype/` | 200 |
| `admin:manager_contacttype_add` | Administrador | `/admin/manager/contacttype/add/` | 200 |
| `admin:manager_contacttype_change` | Administrador | `/admin/manager/contacttype/1/change/` | 200 |
| `admin:manager_customform_changelist` | Administrador | `/admin/manager/customform/` | 200 |
| `admin:manager_customform_add` | Administrador | `/admin/manager/customform/add/` | 200 |
| `admin:manager_event_changelist` | Administrador | `/admin/manager/event/` | 200 |
| `admin:manager_event_add` | Administrador | `/admin/manager/event/add/` | 200 |
| `admin:manager_event_change` | Administrador | `/admin/manager/event/4/change/` | 200 |
| `admin:manager_eventdate_changelist` | Administrador | `/admin/manager/eventdate/` | 200 |
| `admin:manager_eventdate_add` | Administrador | `/admin/manager/eventdate/add/` | 200 |
| `admin:manager_eventdate_change` | Administrador | `/admin/manager/eventdate/1/change/` | 200 |
| `admin:manager_eventolsetting_changelist` | Administrador | `/admin/manager/eventolsetting/` | 200 |
| `admin:manager_eventolsetting_add` | Administrador | `/admin/manager/eventolsetting/add/` | 200 |
| `admin:manager_eventolsetting_change` | Administrador | `/admin/manager/eventolsetting/1/change/` | 200 |
| `admin:manager_eventtag_changelist` | Administrador | `/admin/manager/eventtag/` | 200 |
| `admin:manager_eventtag_add` | Administrador | `/admin/manager/eventtag/add/` | 200 |
| `admin:manager_eventtag_change` | Administrador | `/admin/manager/eventtag/2/change/` | 200 |
| `admin:manager_eventuser_changelist` | Administrador | `/admin/manager/eventuser/` | 200 |
| `admin:manager_eventuser_add` | Administrador | `/admin/manager/eventuser/add/` | 200 |
| `admin:manager_eventuser_change` | Administrador | `/admin/manager/eventuser/1/change/` | 200 |
| `admin:manager_eventuserattendancedate_changelist` | Administrador | `/admin/manager/eventuserattendancedate/` | 200 |
| `admin:manager_eventuserattendancedate_add` | Administrador | `/admin/manager/eventuserattendancedate/add/` | 200 |
| `admin:manager_hardware_changelist` | Administrador | `/admin/manager/hardware/` | 200 |
| `admin:manager_hardware_add` | Administrador | `/admin/manager/hardware/add/` | 200 |
| `admin:manager_installation_changelist` | Administrador | `/admin/manager/installation/` | 200 |
| `admin:manager_installation_add` | Administrador | `/admin/manager/installation/add/` | 200 |
| `admin:manager_installationmessage_changelist` | Administrador | `/admin/manager/installationmessage/` | 200 |
| `admin:manager_installationmessage_add` | Administrador | `/admin/manager/installationmessage/add/` | 200 |
| `admin:manager_installer_changelist` | Administrador | `/admin/manager/installer/` | 200 |
| `admin:manager_installer_add` | Administrador | `/admin/manager/installer/add/` | 200 |
| `admin:manager_installer_change` | Administrador | `/admin/manager/installer/2/change/` | 200 |
| `admin:manager_organizer_changelist` | Administrador | `/admin/manager/organizer/` | 200 |
| `admin:manager_organizer_add` | Administrador | `/admin/manager/organizer/add/` | 200 |
| `admin:manager_organizer_change` | Administrador | `/admin/manager/organizer/1/change/` | 200 |
| `admin:manager_reviewer_changelist` | Administrador | `/admin/manager/reviewer/` | 200 |
| `admin:manager_reviewer_add` | Administrador | `/admin/manager/reviewer/add/` | 200 |
| `admin:manager_reviewer_change` | Administrador | `/admin/manager/reviewer/2/change/` | 200 |
| `admin:manager_room_changelist` | Administrador | `/admin/manager/room/` | 200 |
| `admin:manager_room_add` | Administrador | `/admin/manager/room/add/` | 200 |
| `admin:manager_room_change` | Administrador | `/admin/manager/room/2/change/` | 200 |
| `admin:manager_software_changelist` | Administrador | `/admin/manager/software/` | 200 |
| `admin:manager_software_add` | Administrador | `/admin/manager/software/add/` | 200 |
| `admin:manager_software_change` | Administrador | `/admin/manager/software/1/change/` | 200 |
| `admin:manager_ticket_changelist` | Administrador | `/admin/manager/ticket/` | 200 |
| `admin:manager_ticket_add` | Administrador | `/admin/manager/ticket/add/` | 200 |
| `admin:manager_ticket_change` | Administrador | `/admin/manager/ticket/1/change/` | 200 |
| `index` | Anónimo | `/events/audit-flow/` | 200 |
| `FAQ` | Anónimo | `/events/audit-flow/FAQ` | 200 |
| `edit_event` | Organizador | `/events/audit-flow/edit` | 200 |
| `event_add_image` | Organizador | `/events/audit-flow/image-cropping/` | 200 |
| `draw` | Organizador | `/events/audit-flow/draw` | 200 |
| `rooms_list` | Organizador | `/events/audit-flow/rooms/list/` | 200 |
| `add_room` | Organizador | `/events/audit-flow/rooms/add/` | 200 |
| `edit_room` | Organizador | `/events/audit-flow/rooms/edit/2/` | 200 |
| `attendee_registration` | Usuario | `/events/audit-flow/registration` | 200 |
| `attendee_email_sent` | Anónimo | `/events/audit-flow/registration/attendee/email-sent` | 200 |
| `manage_attendance` | Colaborador | `/events/audit-flow/registration/attendee/search` | 200 |
| `attendee_registration_by_collaborator` | Colaborador | `/events/audit-flow/registration/attendee/by-collaborator` | 200 |
| `attendee_registration_from_installation` | Instalador | `/events/audit-flow/registration/attendee/from-installation` | 200 |
| `attendee_registration_by_self` | Anónimo | `/events/audit-flow/registration/attendee/by-self/1d9ed8e6-f164-4dc0-be03-a47357c8ad60` | 200 |
| `attendance_by_autoreadqr` | Anónimo | `/events/audit-flow/registration/attendee/by-self/autoreadqr` | 302 |
| `attendee_registration_print_code` | Colaborador | `/events/audit-flow/registration/print-code` | 200 |
| `collaborator_registration` | Usuario | `/events/audit-flow/registration/collaborator` | 200 |
| `installer_registration` | Usuario | `/events/audit-flow/registration/installer` | 200 |
| `installation` | Instalador | `/events/audit-flow/installation` | 200 |
| `activities` | Anónimo | `/events/audit-flow/activities` | 403 |
| `my_proposals` | Ponente | `/events/audit-flow/my_proposals` | 200 |
| `activity_detail` | Anónimo | `/events/audit-flow/activity/3/` | 200 |
| `activity_dummy` | Revisor | `/events/audit-flow/activity/dummy/` | 200 |
| `activity_proposal` | Ponente | `/events/audit-flow/activity/proposal/` | 200 |
| `edit_activity_proposal` | Ponente | `/events/audit-flow/activity/proposal/3/edit/` | 302 |
| `image_cropping` | Ponente | `/events/audit-flow/activity/proposal/image-cropping/3/` | 200 |
| `image_cropping_without_id` | Ponente | `/events/audit-flow/activity/proposal/image-cropping/` | 500 |
| `talk_registration` | Organizador | `/events/audit-flow/activity/registration/4` | 200 |
| `activities_csv` | Organizador | `/events/audit-flow/activity/csv/` | 200 |
| `reject_activity` | Organizador | `/events/audit-flow/activity/reject_activity/3/` | 302 |
| `schedule` | Anónimo | `/events/audit-flow/schedule` | 200 |
| `contact` | Anónimo | `/events/audit-flow/contact` | 200 |
| `reports` | Organizador | `/events/audit-flow/reports` | 200 |
| `add_organizer` | Organizador | `/events/audit-flow/organizers` | 200 |
| `add_registration_people` | Organizador | `/events/audit-flow/registration_people` | 200 |
| `add_reviewer` | Organizador | `/events/audit-flow/reviewers` | 200 |
| `view_ticket` | Organizador | `/events/audit-flow/ticket` | 200 |
| `activities_reviewer` | Revisor | `/events/audit-flow/activities` | 200 |
| `scanner_qr` | Colaborador | `/events/audit-flow/registration/attendee/by-self/autoreadqr?event_registration_code=1d9ed8e6-f164-4dc0-be03-a47357c8ad60` | 200 |
| `schedule_confirmed` | Anónimo | `/events/audit-flow/schedule` | 200 |
| `edit_activity_proposal_open` | Ponente | `/events/audit-actions/activity/proposal/6/edit/` | 200 |
| `account_reset_done` | Anónimo | `/accounts/password/reset/done/` | 200 |
| `account_verification_sent` | Anónimo | `/accounts/confirm-email/` | 200 |
