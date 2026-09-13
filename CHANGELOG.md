# Changelog

Todos los cambios notables de este proyecto se documentan aquí.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.1.0/) y el
proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [1.1.0] - 2026-09-13

### Añadido
- Freno contra la fuerza bruta sobre el PIN: tras varios fallos seguidos, esa IP
  queda en espera y el castigo se dobla con cada intento. Sin esto, las 10 000
  combinaciones de un PIN de cuatro dígitos se recorrían en segundos.
- Avisos en consola cuando un jugador entra, sale o es rechazado, con la hora,
  su dirección y cuántos mandos quedan libres.

### Cambiado
- Se arranca con cuatro mandos por defecto en vez de dos: se conectan los
  jugadores que sean, sin configurar nada. Con `--players N` se baja el número.
- El arranque se dibuja en dos columnas al estilo neofetch: el fantasma a la
  izquierda con un degradado de turquesa a violeta, y los datos y el QR a la
  derecha. Se adapta al tamaño de la ventana y vuelve a una sola columna si es
  estrecha.
- La consola ya no vuelca el log de peticiones HTTP: solo el panel y los avisos
  de jugadores. `--verbose` devuelve el detalle completo.
- Todo lo que se imprime vive ahora en `banner.py`, no en `server.py`.

### Corregido
- Los mandos se perdían para siempre si un teléfono desaparecía justo entre que
  se le reservaba el slot y se le enviaba su número: la reserva quedaba fuera
  del `try/finally`. Con dos casos de mala suerte el servidor se declaraba lleno
  y solo se recuperaba reiniciándolo.
- Un frame con `{"b": 1e999}` echaba al jugador de la partida. JSON admite ese
  literal, Python lo lee como infinito y `int()` lanzaba `OverflowError`, que se
  escapaba de la validación del protocolo.
- Conectarse sin PIN contaba como intento fallido, así que recargar la página
  unas cuantas veces podía dejarte en espera a ti mismo. Ahora solo cuentan los
  intentos con un PIN escrito.
- El README describía el ping como «verde < 45 ms» cuando en el código el color
  normal es gris azulado, y no mencionaba el rojo por encima de 90 ms ni que la
  cifra es de ida y vuelta.
- El README anunciaba el botón de captura como parte del mando, pero el Xbox 360
  no tiene ese botón y Windows nunca lo recibe. Queda documentado.
- Las páginas y scripts se servían sin cabecera de caché: tras actualizar,
  un teléfono podía seguir ejecutando el mando de la versión anterior. Ahora
  revalida siempre y responde 304 cuando no ha cambiado nada.
- `start.bat` fijaba `--players 2`, así que los cuatro jugadores que prometía el
  README eran inalcanzables por el camino que el propio README documentaba.
  Ahora el `.bat` no fija nada y reenvía las opciones que le pases.
- Nada limitaba `--players` por arriba: pedir más de cuatro creaba mandos que
  ningún juego podía ver, porque XInput solo expone cuatro. Ahora se valida al
  arrancar con un mensaje claro.
- Desbordamiento al calcular la espera del PIN tras miles de intentos seguidos,
  justo en el escenario de fuerza bruta que el freno debe cubrir.

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
