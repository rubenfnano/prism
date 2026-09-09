# PRISM: instalación

Eres el agente de Claude Code de la persona, y estás a punto de montarle uno completo: personalidad, memoria, voz y cara. Este archivo es el director de orquesta. Reúne cada respuesta UNA sola vez, luego instala cada pieza con esas respuestas ya en la mano, las conecta entre sí, y termina con las primeras palabras habladas del asistente.

Reglas de base, válidas durante toda la instalación:

- **Español claro.** Da por hecho que la persona instaló Claude Code ayer. Cualquier cosa técnica lleva una línea de explicación antes de tener nombre.
- **Una pregunta a la vez.** Espera cada respuesta.
- **Nunca borres, sobrescribas ni muevas nada que la persona ya construyera.** Sustituir algo significa que la pieza nueva toma el mando y la vieja se queda intacta en el disco — y lo dices en voz alta.
- **Tú haces el trabajo.** Ejecuta los comandos, escribe las configuraciones, haz las modificaciones. La persona solo actúa cuando el paso de verdad necesita sus manos (dar permiso de cámara o micrófono, escribir una contraseña).

## Fase 0: Encontrar el hogar, y ver qué existe ya

**Comprobación previa: git.** Compruébalo con `git --version`. Si falta, pregunta primero, nunca en silencio: "Antes de nada necesito una herramienta: git, el programa gratuito que descarga y actualiza cada pieza. ¿Lo instalo ahora?". Con un sí claro, instálalo con el gestor de paquetes de cada sistema (winget en Windows, el que ya tenga Mac/Linux) y verifica que quedó instalado. Un aviso que te afecta a TI (la IA), no solo a git: una terminal que ya estaba abierta no ve programas recién instalados — llama a cualquier cosa que instales hoy por su ruta completa durante el resto de esta instalación. Escribe siempre las rutas con barras `/`, funcionan en los tres sistemas y sobreviven mejor al paso por bash y JSON.

**Si este repo no tiene carpeta `.git` dentro** (llegó como zip): conviértelo en un clon real en el sitio, para que las actualizaciones futuras funcionen. Hazlo en silencio y sigue adelante.

El hogar del asistente es la carpeta que CONTIENE este repo. Confírmalo con la persona en términos llanos: "todo lo de tu asistente va a vivir en [ruta], y esta carpeta de herramientas está dentro." Si clonó este repo en un sitio accidental (su carpeta de Descargas, por ejemplo), pregunta dónde debería vivir el asistente, crea esa carpeta, y mueve este repo dentro antes de continuar.

Después, mira alrededor de la carpeta hogar y determina en qué situación estás:

- **Ya existe un `CLAUDE.md` en el hogar** (o la persona te dice que ya tiene un asistente montado en otro sitio): léelo. Si define un asistente con nombre y personalidad, estás ADOPTANDO, no creando. Dilo así: "encontrado [nombre], lo dejo exactamente como está" — y salta cada pregunta de identidad de la Fase 2.
- **No hay nada:** arranque limpio. Todas las preguntas aplican.

**Si su asistente vive en otro sitio, ESA carpeta es el hogar.** Mueve este repo de herramientas dentro, borra la carpeta vacía que dejó el comando de instalación, y sigue como una adopción.

Tres reglas de escaneo válidas durante toda la instalación:

1. **La memoria de proyectos antiguos de Claude Code es terreno legítimo.** Si la pieza de memoria migra memoria antigua, pregunta cuál se debe adoptar. Migrar copia; nunca borra el original.
2. **Las bóvedas de Obsidian existentes son terreno vedado en el camino de bóveda nueva.** Si la persona elige usar su bóveda existente, trabajas solo con esa. Si elige una nueva, nunca miras ninguna otra que tenga, ni siquiera sus nombres de carpeta.
3. **En cualquier otro sitio del disco: pregunta antes de mirar.** La carpeta hogar y las rutas que la persona señale expresamente son las únicas donde trabajas sin pedir permiso cada vez.

## Fase 1: El menú

Ofrece el paquete PRISM, cada pieza en una frase sencilla. Empieza con la respuesta fácil: "el paquete completo" es la primera opción y la que se recomienda por defecto.

1. **La memoria** — un archivador de notas en texto plano que tu IA lee y escribe de verdad, para que te recuerde a ti, tu trabajo, y cada lección aprendida, sesión tras sesión.
2. **La voz** — mantén pulsada una tecla, habla, y tu asistente te responde por los altavoces.
3. **La cara** — un visualizador vivo en el navegador que reacciona mientras conversáis.

Menciona el añadido opcional una sola vez, sin insistir:

- **Skills** *(opcional)* — capacidades adicionales que se pueden añadir ahora o más adelante, con el mismo comando de instalación.

<!--
TODO (Rubén, 2026-09-09): esta fase depende de qué piezas existan de verdad y de sus
nombres de repo. Ahora mismo solo la pieza de memoria (bóveda + plantilla de identidad)
tiene claro qué instala. Voz y cara están pendientes de diseño (cara: diseño propio de
Rubén; voz: por decidir si es una pieza propia o una dependencia externa, ver nota en
Instalador Jarvis Propio de la bóveda). No avanzar aquí sin que Rubén confirme cada pieza.
-->

## Fase 2: La entrevista

<!-- BORRADOR (2026-09-09) — pendiente de que Rubén lo revise y corrija. Cubre solo
las tres cosas que Fase 3 necesita sí o sí; falta lo de voz/cara hasta que esas
piezas estén decididas. -->

Reúne aquí cada respuesta que falte, para que ningún paso posterior tenga que volver a preguntar. Salta lo que la Fase 0 ya haya adoptado.

1. **Su nombre.** Se usa en el saludo final y en cómo se dirige a la persona durante toda la instalación.

2. **La identidad del asistente** (salta esta pregunta entera si la Fase 0 ya adoptó una identidad existente). Tres caminos, en una frase cada uno:
   - **Usar la mía tal cual** — nombre, voz y personalidad ya definidos por quien construyó PRISM.
   - **La misma personalidad, con otro nombre** — se queda con el carácter pero la persona elige cómo se llama.
   - **Construir una desde cero** — la persona define nombre, tono y forma de hablar desde el principio, respondiendo unas pocas preguntas guiadas.

   Nunca elijas en silencio; si la persona duda, ofrece la primera opción como la más simple, pero espera su respuesta.

3. **La bóveda de memoria.** Antes de preguntar, comprueba si Obsidian ya tiene vaults registrados en la máquina (leyendo la config de la propia app, que solo lista rutas, nunca contenido de notas). Si hay alguna, ofrécela por nombre, junto con la opción siempre presente de crear una nueva solo para este asistente. Si Obsidian no está instalado, dilo con claridad: es una pieza obligatoria (así la persona ve y controla la memoria de su propio asistente), y se instala en este mismo paso con su permiso.

   Una bóveda nueva se crea directamente en la carpeta personal de la persona, junto a la carpeta del asistente (nunca dentro). En cuanto exista, di la ruta completa en voz alta.

<!--
DECIDIDO (2026-09-09), revisado: nada de `backtalk` de Jared, ni siquiera sin
modificar — depender de su código, aunque no contamine la licencia de PRISM,
no libera de verdad a quien lo instale. La pieza de voz de PRISM es CÓDIGO
PROPIO, escrito desde cero, apoyado directamente en los motores de
reconocimiento/síntesis de voz (esos sí son de terceros con licencia permisiva,
nunca de Jared): captura de audio, tecla de activación, conexión con Claude
Code — todo eso lo escribe PRISM, no Jared.

**Motores por defecto: Whisper (STT) + Kokoro (TTS).** Elegidos por ser los que
ya están probados y funcionando de verdad en la máquina de Rubén — no una
promesa de rendimiento sin verificar. Comparé Parakeet TDT v3 como alternativa
más rápida (arquitectura transductor) y no hay ningún benchmark real en
Raspberry Pi que lo respalde; los datos de RTFx que circulan son de Apple
Silicon o servidores x86, no comparables. Queda como opción, no como default.

**Decisión de arquitectura clave: el motor NO va hardcodeado.** A diferencia
de `backtalk/mouth.py` (cada motor escrito a mano, sin punto de extensión),
la capa de voz de PRISM define una interfaz de motor (STT y TTS por separado)
para que quien instale PRISM pueda elegir el que quiera sin tocar el código
base: Whisper/Kokoro por defecto, con Parakeet TDT, Chatterbox y ElevenLabs
(cuenta propia) como alternativas ya contempladas desde el diseño. Es SU
Jarvis — que se lo pueda hacer a su medida.

**VoiceStudio** (debpalash/VoiceStudio, AGPL-3.0) sigue sin usarse como motor
en vivo (evita meter su AGPL en el bucle de ejecución); su papel sigue siendo
aparte, offline, como herramienta de diseño/clonado de voz cuyo resultado se
puede subir a ElevenLabs o a cualquier motor que soporte clonación (Chatterbox
también clona).

**Verificación pendiente antes de fijar ningún motor "recomendado" en el
instalador:** medir consumo real (RAM, CPU, latencia) de cada motor candidato
en la propia Raspberry Pi de Rubén con `vcgencmd`/`htop`, no fiarse de cifras
de marketing de otro hardware.

Pendiente aún, y sí entra en esta Fase 2 cuando se escriba:
4. Preguntas de voz — qué motor de STT y de TTS (con Whisper+Kokoro como
   respuesta fácil por defecto), tecla de activación o modo manos libres.
5. Preguntas de cara — elegir entre las caras propias de Rubén, cuando existan.
6. Permisos — si el asistente pide confirmación antes de actuar, o actúa sin preguntar.
-->

## Fase 3: Instalar las piezas

<!--
Pendiente de las piezas reales. Estructura esperada (a confirmar):
cada pieza clonada como hermana de este repo dentro del hogar, desde el repo propio
de Rubén (no de Jared). Reglas de adopción (no duplicar una pieza ya instalada,
no tocar nunca algo hecho a mano por la persona) se mantienen igual que en Fase 0.
-->

## Fase 4: Conectar las piezas

<!-- Pendiente — depende de qué configs exponga cada pieza real una vez existan. -->

## Fase 5: El primer saludo

<!-- Pendiente — mismo espíritu que la Fase 5 original: arrancar todo, verificar que funciona, y que el asistente hable primero. -->

## Fase 6: Entregar las llaves

<!-- Pendiente — accesos directos de escritorio, cómo actualizar, cómo pedir ayuda al propio asistente si algo se rompe. -->
