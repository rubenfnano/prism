# Caras de PRISM

Dos líneas de diseño, deliberadamente separadas:

- **`corporate/`** — la cara por defecto de PRISM, la que trae el instalador para cualquiera. Núcleo: una gema facetada e irregular (estilo Obsidian, colores del degradado PRISM cambiando por faceta según gira). `core.html` es el prototipo interactivo actual.
- **`personal/`** — variante personal de Rubén / su círculo cercano, sin ánimo de ser la opción por defecto. Tetraedro de líneas de neón (cian→magenta→violeta), el export real de Claude Design (`core.dc.html` + `support.js`, que tiene que viajar siempre al lado), con un botón "chat" añadido a su menú original (listening/thinking/speaking/rest) — panel de mensajes con la misma tarjeta "ver cambios" colapsable que la corporativa, sin tocar nada del motor visual del export original.

  **No abrir `core.dc.html` como archivo suelto (`file://`)** — hace un `fetch` de sí mismo para leer su propia plantilla, bloqueado por CORS sin servidor. Servir con `python3 -m http.server 8080` desde esta carpeta y abrir `http://localhost:8080/core.dc.html`.

  *(Una primera versión reescribió todo el armazón desde cero en `shell.html` — se descartó: Rubén quería el menú y el diseño ya aprobados de Claude Design, solo con un botón de chat añadido, no una reconstrucción completa.)*
