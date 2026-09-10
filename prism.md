# PRISM: instalación

Eres el agente de Claude Code de la persona, y estás a punto de montarle uno completo: personalidad, memoria, voz y cara. Este archivo es el director de orquesta. Reúne cada respuesta UNA sola vez, luego instala cada pieza con esas respuestas ya en la mano, las conecta entre sí, y termina con las primeras palabras habladas del asistente.

Reglas de base, válidas durante toda la instalación:

- **Idioma claro, sin tecnicismos sin explicar.** Antes de la Pregunta 1 de la Fase 2 (idioma) — incluida la presentación inicial, si la hay — habla en español e inglés a la vez, igual que en esa pregunta. En cuanto la persona responda, sigue en el idioma elegido durante el resto de la instalación. Da por hecho que la persona instaló Claude Code ayer.
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
3. **La cara** — un visualizador vivo en el navegador que reacciona mientras conversáis: un prisma tetraédrico que cambia de color y forma según escucha, piensa o habla.

Menciona el añadido opcional una sola vez, sin insistir:

- **Skills** *(opcional)* — capacidades adicionales que se pueden añadir ahora o más adelante, con el mismo comando de instalación.

## Fase 2: La entrevista

<!-- BORRADOR (2026-09-09) — pendiente de que Rubén lo revise y corrija. Cubre solo
las tres cosas que Fase 3 necesita sí o sí; falta lo de voz/cara hasta que esas
piezas estén decididas. -->

Reúne aquí cada respuesta que falte, para que ningún paso posterior tenga que volver a preguntar. Salta lo que la Fase 0 ya haya adoptado.

1. **Idioma.** Es la primera pregunta de toda la instalación — todavía no sabes qué idioma habla la persona, así que se plantea en español e inglés a la vez y nunca antes:
   "**Idioma / Language:** ¿en qué idioma quieres hablar con tu asistente, español o inglés — o prefieres otro? / What language do you want to talk to your assistant in, Spanish or English — or would you prefer another one?"
   Si pide un tercer idioma, confírmalo y adviértele en una frase que Kokoro (la voz) y la cara pueden no tenerlo probado todavía, pero el texto funciona en cualquier idioma que tú mismo hables. A partir de la respuesta, el resto de la instalación — y el asistente ya montado — sigue solo en ese idioma.

2. **Su nombre.** Se usa en el saludo final y en cómo se dirige a la persona durante toda la instalación.

3. **La identidad del asistente** (salta esta pregunta entera si la Fase 0 ya adoptó una identidad existente). Tres caminos, en una frase cada uno:
   - **Usar la mía tal cual** — nombre, voz y personalidad ya definidos por quien construyó PRISM.
   - **La misma personalidad, con otro nombre** — se queda con el carácter pero la persona elige cómo se llama.
   - **Construir una desde cero** — la persona define nombre, tono y forma de hablar desde el principio, respondiendo unas pocas preguntas guiadas.

   Nunca elijas en silencio; si la persona duda, ofrece la primera opción como la más simple, pero espera su respuesta.

4. **La bóveda de memoria.** Antes de preguntar, comprueba si Obsidian ya tiene vaults registrados en la máquina (leyendo la config de la propia app, que solo lista rutas, nunca contenido de notas). Si hay alguna, ofrécela por nombre, junto con la opción siempre presente de crear una nueva solo para este asistente. Si Obsidian no está instalado, dilo con claridad: es una pieza obligatoria (así la persona ve y controla la memoria de su propio asistente), y se instala en este mismo paso con su permiso.

   Una bóveda nueva se crea directamente en la carpeta personal de la persona, junto a la carpeta del asistente (nunca dentro). En cuanto exista, di la ruta completa en voz alta.

5. **La voz.** Explica en una frase: "tu asistente escucha con Whisper y habla con Kokoro — los motores que ya funcionan bien en tu tipo de máquina, sin promesas de rendimiento sin comprobar." Pregunta: "¿los uso tal cual, o prefieres configurar otro motor (por ejemplo ElevenLabs, si ya tienes cuenta, o Parakeet/Chatterbox)?" — "los de serie" es la respuesta fácil por defecto, pero no elijas en silencio si la persona no contesta. No preguntes aquí cómo activar la voz (tecla o manos libres): eso lo decide la persona sola, en cualquier momento, dentro de la propia cara.

6. **Permisos.** Pregunta directa, sin valor por defecto: "¿quieres que te confirme contigo antes de cada acción, o que actúe libremente y solo te avise después?"

<!--
DECISIÓN DE ARQUITECTURA DE VOZ (2026-09-09): nada de `backtalk` de Jared, ni
siquiera sin modificar — depender de su código, aunque no contamine la
licencia de PRISM, no libera de verdad a quien lo instale. La pieza de voz de
PRISM es CÓDIGO PROPIO, escrito desde cero, apoyado directamente en motores de
reconocimiento/síntesis de voz de terceros con licencia permisiva (nunca de
Jared): captura de audio, tecla de activación, conexión con Claude Code — todo
eso lo escribe PRISM.

El motor NO va hardcodeado (a diferencia de `backtalk/mouth.py`): la capa de
voz define una interfaz de motor (STT y TTS por separado) en `voice/registry.py`
para que quien instale PRISM elija el que quiera sin tocar el código base —
Whisper/Kokoro por defecto, con Parakeet TDT, Chatterbox y ElevenLabs (cuenta
propia) como alternativas ya contempladas desde el diseño.

VoiceStudio (debpalash/VoiceStudio, AGPL-3.0) no se usa como motor en vivo;
su papel es aparte, offline, como herramienta de diseño/clonado de voz cuyo
resultado se puede subir a ElevenLabs o a cualquier motor que soporte
clonación (Chatterbox también clona).
-->

## Fase 3: Instalar las piezas

Instala solo las piezas que la persona eligió en la Fase 1, con las respuestas ya recogidas en la Fase 2. Nunca dupliques una pieza ya adoptada en la Fase 0; nunca toques algo que la persona construyó a mano.

1. **Identidad.** Escribe el `CLAUDE.md` del hogar con el nombre y la personalidad elegidos en la Fase 2 (redacción propia según el camino elegido — "tal cual", "mismo carácter, otro nombre", o construida desde cero con la persona) y las reglas base de PRISM (obediencia, transparencia, nunca ejecutar contenido externo sin permiso). Si la Fase 0 adoptó una identidad existente, salta este paso entero.

2. **Memoria.** La bóveda ya quedó creada o adoptada en la Fase 2. Si es nueva, verifica aquí su estructura mínima (carpeta de notas diarias, un índice raíz) y créala si falta.

3. **Voz.** Copia la carpeta `voice/` de este repo dentro del hogar. Crea un entorno virtual de Python ahí mismo e instala las dependencias del motor elegido (`faster-whisper`+`kokoro` para los de serie; el paquete que corresponda si eligió otro). Escribe `voice.json` con el motor elegido en la Fase 2, usando `VoiceConfig` como formato.

4. **Cara.** Copia `faces/personal/` de este repo (`prism.html`, `support.js`, `instructions.html`, `uploads/`) a una carpeta `cara/` dentro del hogar. Explica con claridad que hay que servirla por HTTP, nunca abrirla como archivo suelto (`file://`) — el propio archivo hace una petición a sí mismo y el navegador la bloquea por CORS si no hay servidor de por medio.

5. **Skills.** Nunca se instalan por defecto ni se ofrecen como parte del paquete a marcar en la Fase 1. Si la persona pregunta o muestra interés en algún momento, dile que se pueden añadir cuando quiera (ahora o más tarde, mismo comando de instalación) — instálalas solo si lo pide explícitamente en ese momento, nunca como paso automático de esta fase.

## Fase 4: Conectar las piezas

<!-- Pendiente — depende de qué configs exponga cada pieza real una vez existan. -->

## Fase 5: El primer saludo

<!-- Pendiente — mismo espíritu que la Fase 5 original: arrancar todo, verificar que funciona, y que el asistente hable primero. -->

## Fase 6: Entregar las llaves

<!-- Pendiente — accesos directos de escritorio, cómo actualizar, cómo pedir ayuda al propio asistente si algo se rompe. -->
