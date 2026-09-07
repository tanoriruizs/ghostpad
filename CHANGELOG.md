# Changelog

Todos los cambios notables de este proyecto se documentan aquí.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.1.0/) y el
proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [1.0.0] - 2026-09-07

Primera versión pública.

### Añadido
- Mando Pro Controller completo desde el navegador: ABXY, cruceta con diagonales,
  dos sticks analógicos con clic, L/R/ZL/ZR, +/−, Home y captura.
- Un mando de Xbox 360 virtual por teléfono mediante ViGEmBus (`--players N`).
- Rumble del juego reenviado al teléfono como vibración.
- PIN de acceso (aleatorio por defecto, `--pin off` para desactivarlo), incluido
  en el QR para que entrar sea un solo escaneo.
- Pantalla siempre encendida sin HTTPS (Wake Lock con respaldo de vídeo mudo).
- Pantalla guía de orientación y pantalla completa al abrir en vertical o al
  volver de otra app.
- Indicador de ping, reconexión automática y liberación de botones al cambiar
  de app.
- Ajustes por teléfono: idioma (es/en), sensibilidad, zona muerta, tamaño de los
  botones, vibración con prueba y fuerza (suave/media/fuerte), mapeo A/B/X/Y y
  stick derecho.
- Consola con logo en ASCII y colores al arrancar.
- Suite de tests (`pytest`) para protocolo, mapeo y servidor, con CI en GitHub
  Actions.
