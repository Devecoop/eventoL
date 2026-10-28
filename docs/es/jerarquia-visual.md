# Resumen del diseño visual de eventoL

Estado al 28 de octubre de 2026.

La renovación visual unifica la home y las pantallas internas mediante una
paleta, una escala tipográfica y espaciados compartidos. La home se renderiza
con plantillas Django y usa HTMX para actualizar los resultados de búsqueda;
React continúa en las pantallas que lo utilizan. Los estilos mantienen Sass,
Bootstrap 4 y Bootstrap Material Design, sin incorporar otro framework de CSS.

La configuración del diseño se concentra en variables Sass para personalizar
colores, fuentes, tamaños, pesos, bordes, sombras y dimensiones. Se conserva el
fondo claro verdoso, las tarjetas oscuras de eventos y el acento verde, con
superficies claras para formularios y paneles internos.

## Apariencia y comportamiento actuales

La home comparte la jerarquía de títulos con el resto de la aplicación y tiene
estilos propios para portada, buscador, carruseles y tarjetas. Sus párrafos usan
el tamaño de cuerpo común. El menú móvil tiene fondo opaco, foco de teclado y
desplazamiento interno cuando no entra en pantalla. La navegación de escritorio
se activa desde 950 px.

Las pantallas de cuenta, eventos, actividades, inscripción, salas y reportes
usan roles de página, sección y tarjeta. Los títulos de tarjetas prevalecen
sobre los valores predeterminados de Material Design, y los párrafos de los
paneles heredan el cuerpo compartido. Las portadas de las vistas React de
etiquetas e instancia se adaptan al contenido para evitar superposiciones.

Los formularios organizan campos y acciones dentro del flujo de la página,
con campos de ancho completo en móvil. El cronograma permite desplazamiento
horizontal dentro de su contenedor cuando tiene varias salas. Los títulos
largos y sus estados pueden distribuirse en varias líneas.

Los cambios de HTML organizan encabezados, contenedores y clases de estilo;
conservan los campos, destinos y validaciones de formularios. Se mantienen los
contenidos, con el título de página «Sorteo» incorporado expresamente. Los
catálogos de traducción afectados por el marcado del acceso mantienen sus
traducciones. La migración de la home conserva las listas, búsqueda, carruseles,
mapas y enlaces existentes.

El buscador envía un GET a `/home/search/` y HTMX reemplaza únicamente el bloque
de resultados. Sin HTMX, la búsqueda funciona como una navegación a la home
completa. El JavaScript conserva las interacciones y reinicializa los carruseles
y mapas después de actualizar los resultados. Los logos y el mensaje de portada
siguen usando la configuración existente de `EventolSetting`.

## Escala y distribución

| Rol | Escritorio, desde 768 px | Móvil | Uso |
| --- | --- | --- | --- |
| Página | 28 px | 24 px | Título principal |
| Sección | 22 px | 20 px | Secciones de contenido |
| Tarjeta | 18 px | 18 px | Encabezados de paneles y tarjetas |
| Cuerpo | 16 px | 16 px | Párrafos y campos |
| Etiqueta | 14 px | 14 px | Etiquetas y texto secundario |
| Ayuda | 13 px | 13 px | Indicaciones y errores |

Los tamaños de la escala usan `rem` sobre una base de 16 px. Los títulos usan
Roboto, peso 600 e interlineado 1.3; el cuerpo, peso 400 e interlineado 1.5.
Las fechas, etiquetas y otros metadatos compactos mantienen sus tamaños
secundarios; el buscador conserva su fuente configurable.

El contenido interno tiene un ancho máximo de 1120 px, separación de 24 px entre
paneles y relleno de 24 px en escritorio o 16 px en móvil. Las listas de la home
mantienen sus dimensiones específicas.

## Dónde personalizar

| Archivo en `eventol/front/src/` | Responsabilidad |
| --- | --- |
| `styles/_design.scss` | Variables compartidas con `!default`: paleta, fuentes, escala, espaciados y dimensiones |
| `styles/variables.scss` | Conexión de los nombres históricos con las variables del diseño |
| `styles/_components.scss` | Mixins de encabezados, tarjetas, etiquetas, menú y foco |
| `styles/_typography.scss` | Aplicación de la escala y distribución común de las páginas internas |
| `libs/base.scss` | Configuración de Bootstrap y Material Design con las variables compartidas |
| `libs/home.scss` y `styles/home/` | Estilos de navegación, portada y tarjetas de la home |

Las variables de `_design.scss` se pueden editar allí o definir antes de importar
el tema. Por ejemplo:

```scss
$design-primary: #175c57 !default;
$design-background: #edf7f1 !default;
```

| Aspecto | Variables principales |
| --- | --- |
| Paleta y superficies | `$design-primary`, `$design-background`, `$design-surface`, `$design-text`, `$design-border` |
| Tarjetas de eventos | `$design-card-background`, `$design-card-text`, `$design-card-muted`, `$design-media-height` |
| Fuentes y tamaños | `$design-font-body`, `$design-font-heading`, `$design-font-search`, `$design-font-body-size`, `$design-font-page-title`, `$design-font-section-title`, `$design-font-card-title` |
| Menú | `$design-menu-background`, `$design-menu-opacity`, `$design-breakpoint-navigation` |
| Espaciados y distribución | `$design-space-*`, `$design-panel-padding`, `$design-panel-padding-mobile`, `$design-page-width`, `$design-page-gap` |
| Estados y efectos | `$design-success`, `$design-danger`, `$design-focus-shadow`, `$design-card-shadow`, `$design-radius-*` |

Los valores derivados se calculan al compilar; una familia tipográfica nueva
requiere cargar también su fuente. Las variables no agregan un selector de temas
en tiempo de ejecución ni una configuración de estilos desde el administrador.
Los widgets externos y estilos heredados conservan reglas particulares que deben
revisarse cuando se personalizan. El número de tarjetas y los puntos de cambio
de los carruseles siguen definidos en `front/src/utils/constants.js`.

La home se organiza en `manager/home.py`, `manager/templates/index.html`,
`manager/templates/home/` y `front/src/libs/home.js`. El bundle `HomeTemplates`
contiene sus interacciones y estilos; HTMX se sirve desde
`manager/static/manager/vendor/htmx/`. La API REST y los bundles React de las
demás pantallas siguen disponibles.

## Compilar y comprobar

Desde `eventol/front/`, usar los comandos existentes:

```sh
yarn start    # desarrollo con recompilación
yarn build    # generar los bundles de producción
yarn sasslint
yarn eslint
yarn test --runInBand
```

Los cambios de variables Sass requieren recompilar. Al modificar colores,
revisar contraste, foco y estados; al modificar dimensiones, revisar menús,
formularios y carruseles en escritorio y móvil. Los catálogos de traducción se
compilan con `python eventol/manage.py compilemessages` desde la raíz del proyecto,
como parte del proceso habitual de despliegue.

## Verificación y límites

El trabajo incluye pruebas de backend y frontend, comprobaciones de Django,
compilación y revisión visual. Las suites ejecutadas durante el desarrollo
registraron 226 pruebas de backend y 197 de frontend aprobadas. El backend
requirió un adaptador temporal de compatibilidad entre Autofixture y Pillow;
no se modificaron las dependencias del producto para esa ejecución.

La comprobación más reciente de estilos pasó Sass lint y compilación de
producción, con las advertencias existentes de tamaño de bundles. Se guardaron
23 capturas: ocho pantallas a 1440/390 px, el menú a 320/390/768/949 px, el cambio
a escritorio desde 950 px y una vista de 320×400 para comprobar scroll y teclado.
Los títulos de reportes midieron 18 px y peso 600, y los párrafos revisados,
16 px. No hubo desbordamiento horizontal de documento en ese recorrido.

La evidencia y las comparaciones antes/después están en
`/tmp/eventol-ajustes-qa-20261028/index.html`. Son archivos temporales y pueden
eliminarse al limpiar `/tmp`.

La última revisión fue anónima: las pantallas que requieren sesión quedan
pendientes de verificación con sus permisos reales. No se enviaron formularios
ni se verificaron todos los navegadores o servicios externos. El administrador
Django conserva sus estilos propios. Siguen pendientes estas fallas funcionales,
que no se presentan como resueltas por el cambio visual:

| Área | Problema registrado |
| --- | --- |
| CAPTCHA | La imagen devuelve HTTP 500 por el uso de `getsize` de Pillow en la dependencia instalada. Impide leer el desafío del formulario. |
| Sorteos | Faltan los archivos JS/CSS de `jquery-slotmachine`; el botón de inicio falla porque el plugin no está disponible. |
| Reportes | Una fecha sin asistencias puede omitir el contenedor que el script de gráficos intenta inicializar. |
| Recorte de actividad | La ruta sin identificador devuelve HTTP 500 porque la vista requiere `activity_id`. |

Para repetir pruebas que guarden datos, usar una base, archivos y correo de
prueba aislados. El adaptador temporal de Pillow usado para las suites no debe
ocultar la falla real del CAPTCHA al revisar la interfaz. No se validaron cámara
y lectura física de QR, acceso OAuth real ni entrega SMTP.
