# Caras de PRISM

Dos líneas de diseño, deliberadamente separadas:

- **`corporate/`** — la cara por defecto de PRISM, la que trae el instalador para cualquiera. Núcleo: una gema facetada e irregular (estilo Obsidian, colores del degradado PRISM cambiando por faceta según gira). `core.html` es el prototipo interactivo actual.
- **`personal/`** — variante personal de Rubén / su círculo cercano, sin ánimo de ser la opción por defecto. Tetraedro de líneas de neón (cian→magenta→violeta). Dos archivos, dos propósitos distintos:
  - **`shell.html`** — la cara completa de verdad: mismo armazón que `corporate/core.html` (modos mantener-para-hablar / conversación en vivo / escribir, chat con "ver cambios" colapsable), pero con el tetraedro como núcleo — reescrito en Canvas vanilla, tetraedro 3D real (4 vértices, 6 aristas, rotación de verdad, no una proyección falsa), con el rayo de plasma / líneas orgánicas / cascada de glifos recortados dentro de su silueta según el estado. **Este es el que se usa.**
  - **`core.dc.html`** + `support.js` — el export original de Claude Design, solo el logo animado (sin chat ni modos), guardado como referencia de diseño. Formato propio `.dc.html`, necesita `support.js` al lado siempre. **No abrir como archivo suelto (`file://`)** — hace un `fetch` de sí mismo, bloqueado por CORS sin servidor. Servir con `python3 -m http.server 8080` desde esta carpeta y abrir `http://localhost:8080/core.dc.html`.
