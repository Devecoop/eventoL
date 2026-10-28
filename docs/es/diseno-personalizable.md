# Diseño personalizable de eventoL

El diseño utiliza Sass/SCSS, Bootstrap 4 y Bootstrap Material Design existentes.
No se incorporaron frameworks, dependencias ni un sistema de temas adicional.

La escala de títulos, cuerpo, ayudas y espaciados aplicada el 28 de octubre está
explicada en [Jerarquía visual compartida](jerarquia-visual.md).

## Dónde personalizar

La fuente de los valores compartidos es
`eventol/front/src/styles/_design.scss`. Todas sus variables tienen `!default`:
se pueden editar allí o definir antes de importar el tema. Es un archivo de
configuración Sass; no genera CSS por sí solo.

| Aspecto | Variables principales |
| --- | --- |
| Identidad | `$design-primary`, `$design-background`, `$design-text` |
| Superficies y campos | `$design-surface`, `$design-border` |
| Estados | `$design-success`, `$design-danger`, `$design-focus-shadow` |
| Tarjetas de eventos | `$design-card-background`, `$design-card-text`, `$design-card-muted`, `$design-card-border` |
| Imágenes | `$design-media-background`, `$design-media-height` |
| Menú de la home | `$design-header-background`, `$design-header-text`, `$design-menu-background` |
| Fuentes | `$design-font-body`, `$design-font-heading`, `$design-font-search` (buscador) |
| Tamaños de texto | `$design-font-body-size`, `$design-font-base`, `$design-font-small`, `$design-font-card-title`, `$design-font-section-title`, `$design-font-hero-title` |
| Pesos y lectura | `$design-weight-*`, `$design-line-height`, `$design-description-lines` |
| Espaciados | `$design-space-1` a `$design-space-8`, `$design-card-padding`, `$design-panel-padding` |
| Bordes y efectos | `$design-radius-*`, `$design-card-shadow`, `$design-transition` |
| Distribución | `$design-content-width`, `$design-breakpoint-navigation`, `$design-hero-padding-*` |
| Logo y buscador | `$design-logo-width`, `$design-search-*` |

Por ejemplo, para cambiar el acento y el fondo, editar únicamente:

```scss
$design-primary: #175c57 !default;
$design-background: #edf7f1 !default;
```

El acento se propaga a Bootstrap, formularios, navegación y tarjetas. Los colores
semánticos de error, advertencia e información siguen teniendo significado propio.
El fondo de las tarjetas de eventos se configura aparte de las superficies claras
de formularios y paneles: ambos pertenecen a la misma paleta, con contrastes
apropiados para sus contenidos. Cambiar `$design-success` permite diferenciar el
estado de éxito del color principal.

Los valores derivados (por ejemplo, sombras calculadas desde el color principal)
se calculan durante la compilación. Para cambiar la familia tipográfica por una
que no esté cargada, también hay que proporcionar su fuente; editar la variable
no descarga una nueva fuente.

## Organización

- `styles/_design.scss`: valores compartidos, sin selectores.
- `styles/variables.scss`: conecta los nombres históricos con el diseño nuevo;
  conserva los valores específicos de integraciones y componentes antiguos.
- `styles/_components.scss`: mixins reutilizables de tarjeta, etiqueta, foco e
  ítem de menú; no genera selectores globales.
- `styles/_typography.scss`: aplica la escala de página, sección y tarjeta,
  sus variantes móviles y los espaciados de contenido y formularios.
- `libs/base.scss`: configura las variables reales de Bootstrap y Material Design
  antes de importarlos. Botones y campos conservan sus estados nativos; la barra
  de navegación interna, etiquetas de formularios y bordes usan la paleta común.
- `libs/home.scss`: entrada de los estilos de la home, limitada a `.home-page`.
- `styles/home/_navigation.scss`: encabezado, menús y usuario.
- `styles/home/_layout.scss`: portada, buscador, secciones y flechas del carrusel.
- `styles/home/_cards.scss`: tarjetas, imágenes, metadatos y etiquetas.

La home dejó de importar los estilos de los componentes React y de sobrescribir
sus reglas de portada, tarjetas y búsqueda. Se retiraron de sus plantillas la
clase antigua `item` y la superposición de portada que ya no se mostraba. Las
flechas ahora reciben su presentación del SCSS, sin colores en línea.
Los componentes React siguen disponibles para las pantallas que los utilizan.

Se conserva la disposición aprobada, el menú con degradado y el fondo claro con
tarjetas negras. El punto de cambio del menú es 950 px: las reglas móviles llegan
hasta 949 px, evitando mezclar ambos diseños. Los focos de teclado, el acceso al
selector de idiomas mediante foco y el foco del buscador se incluyen en las reglas
correspondientes, sin añadir `!important`.

## Compilar y comprobar

Desde `eventol/front/`, usar los comandos existentes:

```sh
yarn start    # desarrollo con recompilación
yarn build    # generar todos los bundles de producción
yarn sasslint
yarn eslint
yarn test --runInBand
```

Los cambios de variables Sass requieren recompilar. No hay personalización desde
el administrador de Django ni cambio de tema en tiempo de ejecución.
Al cambiar colores, revisar el contraste de texto y los estados de foco, hover,
error y deshabilitado. Al modificar dimensiones, revisar el menú y los carruseles
en escritorio y móvil. Los puntos de cambio y el número de tarjetas de Slick
siguen definidos en `src/utils/constants.js`; cambiar el menú no los modifica.

Las variables compartidas alcanzan las pantallas que cargan `base` y los bundles
que importan `styles/variables.scss`. Esto no convierte todos los estilos antiguos
ni los widgets externos en componentes nuevos: sus reglas particulares se
conservan y deben revisarse cuando se rediseñe cada pantalla.
