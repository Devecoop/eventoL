# Jerarquía visual compartida

Actualizada el 28 de octubre de 2026. La tipografía y los espaciados usan Sass,
Bootstrap y Bootstrap Material Design existentes, sin dependencias nuevas.

## Escala

| Rol | Escritorio (desde 768 px) | Móvil | Uso |
| --- | --- | --- | --- |
| Título de página | 28 px | 24 px | Un `h1` por pantalla |
| Sección | 22 px | 20 px | `h2`, por ejemplo las secciones del perfil o el día del cronograma |
| Tarjeta | 18 px | 18 px | `h3` o clase `card-title`; instrucciones y encabezados de paneles |
| Cuerpo | 16 px | 16 px | Párrafos y campos |
| Etiqueta | 14 px | 14 px | Etiquetas de campos y subtítulos |
| Ayuda | 13 px | 13 px | Indicaciones y errores de formularios |

Los tamaños se expresan en `rem` respecto de una base de 16 px, para respetar el
escalado del navegador. Los títulos comparten Roboto, peso 600, interlineado 1.3 y
corte de palabras largas cuando es necesario. El cuerpo usa peso 400 e
interlineado 1.5. Los metadatos compactos de las tarjetas de la home conservan
sus tamaños específicos de 12/14 px.

## Configuración y estructura

- `front/src/styles/_design.scss`: tamaños de cada rol y de su variante móvil,
  familia, pesos, interlineado, separación entre bloques y ancho de contenido.
- `styles/_components.scss`: mixin `design-heading` para compartir la misma
  definición entre Bootstrap, la home y los componentes React existentes.
- `styles/_typography.scss`: aplica los roles, encabezados, subtítulos, ayudas,
  acciones de formularios y distribución común de tarjetas.
- `libs/base.scss`: configura los tamaños de Bootstrap **antes** de importarlo.
  Se retiró el bloque posterior que volvía a asignar otra familia y peso a todos
  los encabezados.
- `manager/templates/base.html`: ya no envuelve otros encabezados o bloques
  dentro de un `h2`. Cada pantalla declara su título; los encabezados vacíos no
  agregan un título ni espacio visible.

Las variables nuevas principales son `$design-font-page-title`,
`$design-font-page-title-mobile`, `$design-font-section-title-mobile`,
`$design-font-card-title-mobile`, `$design-font-label`, `$design-font-help`,
`$design-heading-line-height` y `$design-breakpoint-type`.

El ancho de las páginas internas se controla con `$design-page-width` (1120 px).
Los paneles usan `$design-panel-padding` (24 px),
`$design-panel-padding-mobile` (16 px) y `$design-page-gap` (24 px). Las listas de
la home mantienen su ancho específico. Los formularios conservan sus campos,
nombres, destinos y validaciones; los campos ocupan todo el ancho en móvil y
las acciones permanecen dentro del flujo del formulario.

## Cambios visibles

- Perfil: un título principal; conexiones y agregado de cuentas son secciones.
- Cronograma: título de página y día con importancia diferente. Si existen
  varias salas, el calendario se desplaza dentro de su contenedor y no ensancha
  el documento móvil.
- Formularios: títulos consistentes, ayudas legibles y botones agrupados. El
  envío del formulario de evento dejó de flotar sobre los campos.
- Creación/edición de eventos: secciones `h2`, espacios de Sass en lugar de
  saltos `<br>` repetidos y sin el margen negativo del selector de etiquetas.
- Actividades: las categorías son secciones y sus tarjetas son encabezados de
  tercer nivel. El título y la insignia de estado del detalle pueden acomodarse
  en líneas distintas en móvil.
- Home: un `h1`, secciones `h2` y nombres de eventos `h3`, usando la misma escala.
- Etiquetas e información de instancia: los componentes React conservan sus
  funciones, pero comparten los tamaños. La portada ya no combina una altura
  fija y un margen negativo con contenido desplazado; sus textos, buscador y
  listas dejan de superponerse.
- Acceso: el separador «o» es texto auxiliar, no un encabezado. El enlace de alta
  hereda el tamaño del párrafo. Se actualizaron y compilaron los siete catálogos
  que contienen ese mensaje para conservar sus traducciones.

## Verificación del 28 de octubre

- 226 pruebas de backend aprobadas con el adaptador temporal de Autofixture/Pillow
  ya documentado. Después de los últimos ajustes de plantillas, se repitieron
  las 18 pruebas de home y la comprobación Django, sin errores.
- 197 pruebas de frontend, 34 suites y 91 snapshots aprobados. Se revisaron y
  actualizaron los 11 snapshots afectados por los cambios intencionales de
  `h2` a `h1`, `h1` a `h2` y la separación de una instrucción en párrafo.
- Compilación de producción correcta, con las advertencias existentes de tamaño.
  Sass lint de los SCSS afectados y ESLint del JSX modificado sin incidencias.
- 50 pantallas/estados de la aplicación en Chrome a 1440 y 390 px: 100 capturas,
  un único título principal no vacío por documento y tamaños de página de
  28/24 px. Se revisaron capturas completas y se comprobaron dimensiones de texto.
- Perfil, cronograma y formulario de sala además a 320/768/1000 px: nueve
  comprobaciones, con títulos largos sin espacios, sin desbordamiento del
  documento. El calendario también se comprobó con varias salas.
- Envío real del formulario de sala con CSRF y búsqueda HTMX conservando el
  documento, con la jerarquía nueva de las tarjetas.
- Las pruebas utilizaron una base y un servidor temporales; no se agregaron datos
  de prueba a la base local. Los auxiliares se retiran al terminar.

Capturas, resultados y scripts temporales: `/tmp/eventol-hierarchy-validation/`.
Las capturas anteriores de comparación siguen en `/tmp/eventol-flow-audit/`.
Las carpetas de `/tmp` pueden eliminarse al reiniciar o limpiar el equipo.

Esta verificación se concentra en la jerarquía y distribución de la aplicación.
El administrador Django usa sus propios estilos y no se modificó. Siguen
pendientes los errores funcionales de CAPTCHA, sorteos, gráficos de reportes y
recorte sin ID registrados en `verificacion-flujos.md`; no se presentan como
resueltos. No se validaron todos los navegadores ni integraciones externas.
