# Home general con Django y HTMX

La ruta `/` genera el encabezado, la portada y las listas de eventos mediante
plantillas Django. El buscador envía un GET a `/home/search/` al presionar Enter;
HTMX reemplaza únicamente el contenido de `#home-search-results` por HTML.
Sin HTMX, el formulario puede enviar la búsqueda a la home completa.

## Comportamientos conservados

- Listas de eventos propios, recientes, destacados, próximos, con cronograma
  confirmado y finalizados; mismos filtros, orden y límite de la API anterior.
  Los eventos propios siguen sin el límite de 20 de las demás listas.
- Búsqueda por nombre, slug, resumen y etiquetas, incluida la semántica de varias
  palabras del filtro de Django REST Framework. Los resultados vacíos mantienen
  su tarjeta informativa. Enviar una búsqueda vacía no borra la búsqueda anterior.
- Encabezado adaptable, menú móvil, foco del buscador, acceso y registro de
  usuarios, perfil y enlace para crear eventos cuando hay sesión.
- Selector de idiomas mediante el endpoint existente de Django, con CSRF.
  `home_trans` utiliza el catálogo `djangojs` que ya utilizaban los componentes
  React, para mantener las traducciones existentes. Hay que compilar los
  catálogos con `python eventol/manage.py compilemessages`, como en el despliegue.
- Logos, fondo y mensaje configurables de `EventolSetting`.
- Carruseles Slick con los mismos tamaños, flechas, puntos y desplazamiento por
  grupos; mapas Leaflet, imágenes, superposición al pasar el mouse, enlaces al
  evento y a sus etiquetas. El JavaScript se reinicializa después de cada
  reemplazo HTMX y destruye el carrusel anterior antes del reemplazo.
- Redirección de inscripción pendiente guardada en sesión.

La migración conserva los estilos de los componentes originales. No corrige el
contraste previo de las tarjetas sin imagen ni ubicación: eso corresponde a un
cambio visual posterior.

## Archivos y compilación

- `manager/home.py`: consultas de las listas y búsqueda.
- `manager/templates/index.html` y `manager/templates/home/`: HTML de la home.
- `front/src/libs/home.js`: interacciones de la home, sin renderizado React.
- `front/src/libs/home.scss`: adaptación del encabezado renderizado en servidor.
- Bundle `HomeTemplates`, registrado en las configuraciones de Webpack de
  desarrollo y producción. Se genera con los comandos existentes `yarn start`
  y `yarn build`. Es necesario recompilar el frontend al actualizar el servidor.
- HTMX 2.0.11 está incluido localmente en
  `manager/static/manager/vendor/htmx/`, junto con su licencia. No necesita un CDN
  para ejecutar las búsquedas. Su SHA-384 coincide con el publicado en la
  [documentación oficial](https://htmx.org/docs/#installing).

React y sus bundles siguen disponibles para las otras pantallas. La API REST,
los modelos y las rutas de eventos, inscripción y administración no cambian.

## Validación del 22 de octubre de 2026

- `python eventol/manage.py check`: sin errores.
- Compilación de producción de todos los bundles: correcta; advertencias
  existentes de tamaño de bundles.
- ESLint del JavaScript nuevo y Sass lint del SCSS nuevo: correctos.
- Frontend: 34 suites, 197 pruebas y 91 snapshots aprobados.
- Backend: 226 pruebas aprobadas, incluidas 18 pruebas nuevas de equivalencia de
  listas y búsqueda, sesión, branding, traducciones, escape de HTML, imágenes,
  ubicación y límites de resultados.

El entorno instalado tiene una incompatibilidad entre Autofixture 0.12 y Pillow:
la primera ejecución general tuvo 140 errores al generar imágenes porque Pillow
ya no proporciona `FreeTypeFont.getsize`. Para ejecutar la suite completa se
usó un adaptador temporal, fuera del repositorio, que calcula ese tamaño con
`getbbox`. No se modificaron dependencias ni código del producto para resolver
ese problema del entorno. El equivalente para reproducir esa ejecución, desde
`eventol/` y con las dependencias del proyecto instaladas, es:

```python
from PIL import ImageFont
import pytest

for font_class in (ImageFont.FreeTypeFont, ImageFont.ImageFont):
    if not hasattr(font_class, 'getsize'):
        font_class.getsize = lambda self, text: (
            self.getbbox(text)[2], self.getbbox(text)[3])
raise SystemExit(pytest.main(['manager/tests', '-q']))
```

Las pruebas usan la base de datos de prueba de Django. Las capturas de navegador
con datos sintéticos se generan sin agregar eventos a la base local del usuario.

La comparación visual se hizo en Chrome local, usando la versión React y la
versión Django con los mismos datos. Se verificaron tamaños de tarjetas y avance
del carrusel a 1440, 1000, 800 y 390 px de ancho, incluidos el inicio en la tercera
tarjeta entre 610 y 900 px y los grupos de 4/3/2/1 tarjetas. Con varios eventos,
se ajustó el margen extra que agrega Slick al mostrar puntos para mantener la
posición de las secciones.

Las capturas y registros de esta sesión están en
`/tmp/eventol-home-validation/`. Son artefactos locales temporales. Las pruebas
visuales usan imágenes y mapas sintéticos; las teselas del proveedor externo y
el rasterizado de fuentes pueden variar entre capturas. No se validaron en vivo
el envío de correos, los proveedores externos de autenticación ni todos los
navegadores. Las rutas y permisos del resto del proyecto están cubiertos por la
suite existente; esto no equivale a una prueba manual completa de cada pantalla.

Las comprobaciones funcionales de Chrome terminaron sin errores JavaScript:
resultado coincidente, resultado vacío, búsquedas consecutivas, envío vacío sin
borrar el resultado, conservación del documento durante las búsquedas, apertura
del menú móvil, foco del buscador, cambio a español mediante POST con CSRF y
navegación desde una tarjeta a la pantalla existente del evento.

Los tamaños y posiciones de las cinco secciones con ocho eventos sintéticos
coinciden entre ambas versiones en escritorio y móvil. En la captura de escritorio
con esos datos, las diferencias restantes están dentro del mapa externo; en móvil
quedaron pequeñas diferencias de rasterizado en el encabezado. No se afirma una
igualdad de píxeles para todos los estados, imágenes remotas y navegadores.


## Ajuste visual posterior solicitado por el usuario

Después de la migración, el usuario autorizó reemplazar la foto de portada por
un fondo liso y cambiar las tarjetas tomando como referencia una captura de
listados de eventos con imagen arriba y datos debajo.

- Fondo general muy claro `#f7fbf9` y encabezado verde oscuro `#175c57`.
- Tarjetas verde muy claro `#e9f5ef`, bordes suaves y texto oscuro siempre visible.
- Imagen o mapa en la parte superior; logo de respaldo si faltan ambos.
- Nombre, fecha del evento, nombre de ubicación cuando existe, descripción,
  asistentes y etiquetas debajo de la imagen.
- Los ajustes están limitados a `.home-page`, sin modificar los SCSS compartidos
  con otras pantallas. Los carruseles, enlaces y el buscador HTMX se conservan.
- La configuración de imagen de fondo sigue guardada, pero esta home ya no la
  utiliza. Se mantienen los logos y el mensaje configurables.

Se revisó en Chrome a 1440 y 390 px, sin desbordamiento horizontal, y se comprobó
la búsqueda HTMX con las nuevas tarjetas en ambos tamaños. Las 18 pruebas de la
home pasan; se ajustó la expectativa de la portada para el fondo liso solicitado.
La compilación de producción y Sass lint también se verificaron.


### Refinamiento de colores y menú

El usuario pidió conservar el menú original y reservar el verde para el fondo y
los acentos. El estado actual usa fondo verde muy claro `#edf7f1`, tarjetas negras
`#111`, textos claros y acentos verde oscuro `#175c57` en etiquetas, fechas y
estados de foco. Se retiraron los cambios de fondo sólido y espaciado del menú;
se aplica nuevamente su degradado original. Estos ajustes se concentran en
`front/src/libs/home.scss`.
