# Caras de PRISM

Dos líneas de diseño, deliberadamente separadas:

- **`corporate/`** — la cara por defecto de PRISM, la que trae el instalador para cualquiera. Núcleo: una gema facetada e irregular (estilo Obsidian, colores del degradado PRISM cambiando por faceta según gira). `core.html` es el prototipo interactivo actual.
- **`personal/`** — variante personal de Rubén / su círculo cercano, sin ánimo de ser la opción por defecto. Tetraedro de líneas de neón (cian→magenta→violeta), el export real de Claude Design (`prism.html` + `support.js`, que tiene que viajar siempre al lado — el motor visual original no se ha tocado). Encima de ese export, construido:
  - **Menú superior:** "en vivo" (llamada continua, escucha→piensa→habla en bucle) + "chat" (panel de texto) + botón de ayuda (`?`, abre `instructions.html` en pestaña aparte). Los botones originales de previsualización (listening/thinking/speaking/rest) se quitaron — eran solo para Claude Design, nunca controles reales, y dejaban dos elementos resaltados a la vez.
  - **Barra inferior:** botón de micrófono real ("mantener para hablar"), con el mismo comportamiento que la barra espaciadora (`engagePtt`/`releasePtt` compartidos entre ambos).
  - **Transcripción unificada:** cualquier turno de voz (mantener pulsado o "en vivo") se añade al mismo panel de chat (`logVoiceTurn()`) — no son conversaciones separadas.
  - **Aviso al cargar:** un toast breve recordando que se puede mantener el espacio para hablar.
  - **Idioma:** detectado por `navigator.language` (es/en); el desglose "P.R.I.S.M" del subtítulo se queda siempre en inglés (nombre propio del producto).

  **No abrir `prism.html` como archivo suelto (`file://`)** — hace un `fetch` de sí mismo para leer su propia plantilla, bloqueado por CORS sin servidor. Servir con `python3 -m http.server 8080` desde esta carpeta y abrir `http://localhost:8080/prism.html`.

  *(Una primera versión reescribió todo el armazón desde cero en `shell.html` — se descartó: Rubén quería el menú y el diseño ya aprobados de Claude Design, solo con ajustes añadidos, no una reconstrucción completa.)*
