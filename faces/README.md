# Caras de PRISM

Dos líneas de diseño, deliberadamente separadas:

- **`corporate/`** — la cara por defecto de PRISM, la que trae el instalador para cualquiera. Núcleo: una gema facetada e irregular (estilo Obsidian, colores del degradado PRISM cambiando por faceta según gira). `core.html` es el prototipo interactivo actual.
- **`personal/`** — variante personal de Rubén / su círculo cercano, sin ánimo de ser la opción por defecto. Tetraedro de líneas de neón (cian→magenta→violeta), diseñado en Claude Design. `core.dc.html` + `support.js` (el runtime que interpreta el formato `.dc.html` — tiene que viajar siempre junto al archivo). Estados: listening/thinking/speaking/rest, con controles `rotationSpeed` (0-1.6) y `glow` (0-2) editables como props del propio componente.

  **No abrir `core.dc.html` como archivo suelto (`file://`)** — hace un `fetch` de sí mismo para leer su propia plantilla, y eso lo bloquea CORS sin servidor. Servir con cualquier servidor HTTP simple, por ejemplo desde esta carpeta: `python3 -m http.server 8080` y abrir `http://localhost:8080/core.dc.html`.
