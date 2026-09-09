# PRISM

**Personality, Reasoning, Interface, Speech, Memory.**

Un instalador conversacional: monta un asistente de IA personal completo — memoria persistente, voz, cara animada y personalidad propia — sobre Claude Code, en Windows, Linux o macOS, en una sola conversación.

No es un programa que detecta tu sistema operativo y ejecuta pasos por ti. Es un documento de instrucciones que Claude Code lee y ejecuta él mismo, usando sus propias herramientas de shell — por eso funciona igual en las tres plataformas sin código de instalación específico por sistema operativo.

## Piezas

Cada pieza es opcional; el usuario decide cuáles quiere durante la conversación de instalación:

- **Memoria** — una bóveda de notas en texto plano que la IA lee y escribe, para recordar entre sesiones.
- **Voz** — hablar con el asistente y que responda en voz alta.
- **Cara** — un visualizador animado en el navegador.
- **Skills** — capacidades adicionales, elegidas por el usuario.

## Instalación

```bash
mkdir -p ~/prism-agent && cd ~/prism-agent && git clone https://github.com/rubenfnano/prism && cd prism && claude "instálame"
```

## Licencia

MIT — ver [LICENSE](LICENSE). Software propio, escrito desde cero; ningún archivo de este repositorio proviene de terceros.
