"""Todo lo que GhostPad imprime en consola: el fantasma, el panel de arranque
y los avisos de jugadores que entran y salen.

El arranque se dibuja en dos columnas al estilo neofetch (fantasma a la
izquierda, datos y QR a la derecha) y cae a una sola columna si la ventana
es estrecha. Vive aparte de `server.py` para que el servidor solo sirva.
"""

from __future__ import annotations

import io
import shutil
import sys
import time
from typing import Final

# El fantasma completo. Solo se usa si la consola es lo bastante alta; si no,
# empujaría la dirección y el QR fuera de la pantalla.
GHOST_FULL: Final[str] = r"""
                      -----------------------------------------------------------
                  --------------------------------------------------------------------
                ------------------------------------------------------------------------
              ------+##############################################################-------
             -----###################################################################+-----
            -----#########################-------------------+#########################-----
           -----########################################################################-----
           ----#########################################################################+----
          -----##########################################################################----
          -----##################################++++++##################################----
          -----###########################-.....             -###########################----
          -----#######################-.......                   -#######################----
          -----####################-.......                         -####################----
          -----##################--.....                              .##################----
          -----################---...                                   +################------
          -----##############----...                                     .###############----+-
          -----#############----..                                         +#############----+-
          -----############---...                                          .+############----++
          -----###########----...                                           .############----++
          ----+##########----...                                             .###########----++
          ----+#########----...                                              ..##########----++
          ----+#########---....                                               .##########----
          ----+########----....      -####-                 .#####            .-#########----+
          ----+########---....     -########.              +#######+          ..#########----++
          +---+#######+--.....    -##########             +##########          .+########----++
          +---+#######---.....    ###########-            ###########+         .-########----++
          +---+#######---....    -###########+            ############         ..########----++
          +++++#######--....     -+##########-            ############         ..+#######----++
          +++++######---....     .+#########+             -+########++          .-#######----++
          +++++######--.....     .-++####+++-              -++####+++-          ..#######----++
          +++++#####---.....      .---++++--                --++++++-            .-######----
          +++++####+--......        .----.                   .----.              ..-#####----
          +++++####--......                                                       ..+####----
          +++++##+--.......                                                        ..-###----
          +++###--........                                                          ...###+--
          +###+-.........   ..---------.                        -----------           ..-###+
         ####.............----++######+---..                .---+########++---.        ...-####
       ####.............--+###############-------------------+###############+--.        ...-###
      ###.............--########################################################--          ..-###
    ###-.............--#########---+################################+---+########+-          ...+##
   ###.......    . .-+#########-----################################----+#########+-          ...-###
  ###.......    . .-+#######+++-----+++##########################++##+++##++#######++  .       ...-##
 ###.......       .+#######-------------#######################-----#####---++######-.         ....+##
 ##+......            +####-------------#######################+---+#####+++++###.             ....-###
 ##.......              +######-----################################+---#######.              .....-+##
##+......                ######-----################################--+++#####.               .....--##
##+.......              .+############+--#######-------+######+-+####+++######               ......--###
##+.........           ..##########+-+#+#+--####+++++++####+-+###+--##########+..           ......---###
###....................-##########+-#######+-##############-#######++###########.....  .........-----##
 ##-..+###+..........#############--########+#############--########-#############+.........+###----+##
 ###..######+--####################-#######++##############-#######++###################+++######---###
  ###.######--+#####################---+++-#################--+++++######################--+#####--###
   ###+####+--###############################+-----------+###############################+--####+-###
     ######---##################+++-++###+-.................-+####+++++##################+--########
        ###---################-----................................-----+################+--######
         ##+--+#############-----......................... ............---+##############---####
         ###----#########+-----....................            ...........---+#########+---###
          ###------++--------....................                  ........------+++-----+###
           ####+-------+######++-................                    ........-#+------+####
             #######################+............                       ......###########
                                 #######..........                       .....-#####
                                     #####+.......                        .....+####
                                        #####.......        ......         .....+###
                                          #####-.....   ............        .....+###
                                             ####+.................  ...    ......####
                                               #######+---+##########..... .......-###
                                                   #####################...........####
                                                                     #####.........+###
                                                                       ####-.......###
                                                                         ###......-###
                                                                         ###+....-###
                                                                         ###+...-###
                                                                         ###---####
                                                                         ##--+###
                                                                        ##+####
                                                                      ######
"""

# Mismo dibujo reducido, para consolas de tamaño normal.
GHOST_COMPACT: Final[str] = r"""
       +-----------------++++++++++--+#
      --+##########++++++++##########+--
     --################################--
    +.+############+++--+++############+-
    +.+########+-.          .-+########+-
    +-+######+..               .+######+-+
    +-+####+-.                   -#####+-+
    +-+###+-.                     -####+-+
    #-+###-.    -+-.      .--.     +###+-+
    #-+##+..  .+###+     .####-    -###+-+
    #++##+.   .+###+.    .####+    .+##+-+
    #++##-.    .-+-.      .-++.     -##+-#
    #+##-.                          .-#+-
    #+-.    ..--..          .---..    .++#
  ##-.   .-+######+++++++++#######+-.   .-#
 #-.    .+###+--+#############++####+.    .+#
#-.     .-+#--..-+##########++##++#+-.    ..+#
#-.        +##-+######++######++##+       ..-#
#-.-..  ..+####++#++######+##++####-.....--.+#
 ++##-+########+##########+############++##+#
  ##+-#######++-----......---+++#######+-###
    #--+++++-.....            ..-++##++-+#
     #+++++++++--.               .-++++#
                ##+..             .+#
                   ##-.........    .+#
                      #########+-.  .#
                                #+..-#
                                #+-+#
                                ###
"""

# Filas que ocupan el panel y el QR cuando van debajo del dibujo.
_RESERVADO: Final[int] = 28
# Separación entre las dos columnas y ancho mínimo del panel de datos.
_HUECO: Final[int] = 4
_ANCHO_PANEL_MIN: Final[int] = 52

# Degradado del fantasma, del turquesa de la marca al violeta, como el logo.
_GRADIENTE: Final[tuple[tuple[int, int, int], ...]] = (
    (62, 224, 200),
    (56, 189, 248),
    (99, 140, 255),
    (124, 92, 255),
)


class _Ansi:
    """Códigos de color; se vacían si la consola no los soporta."""

    def __init__(self, enabled: bool) -> None:
        pick = (lambda code: code) if enabled else (lambda _: "")
        self.reset = pick("\033[0m")
        self.bold = pick("\033[1m")
        self.dim = pick("\033[2m")
        self.cyan = pick("\033[36m")
        self.bright_cyan = pick("\033[96m")
        self.green = pick("\033[92m")
        self.yellow = pick("\033[93m")
        self.white = pick("\033[97m")


def _mezcla(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))  # type: ignore[return-value]


def _tono(fila: int, total: int) -> tuple[int, int, int]:
    """Color de una fila del fantasma dentro del degradado."""
    if total < 2:
        return _GRADIENTE[0]
    pos = fila / (total - 1) * (len(_GRADIENTE) - 1)
    i = min(int(pos), len(_GRADIENTE) - 2)
    return _mezcla(_GRADIENTE[i], _GRADIENTE[i + 1], pos - i)


def _ansi_console() -> _Ansi:
    """Activa ANSI en consolas Windows antiguas vía colorama, si está disponible."""
    if not sys.stdout.isatty():
        return _Ansi(False)
    try:
        import colorama  # type: ignore[import-not-found]

        colorama.just_fix_windows_console()
    except Exception:  # noqa: BLE001 - Windows Terminal y *nix ya soportan ANSI
        pass
    return _Ansi(True)


_C: Final[_Ansi] = _ansi_console()


def _cabe(art: str, ancho_panel: int, cols: int, filas: int) -> tuple[bool, bool]:
    """(cabe, en dos columnas) para un dibujo dado en esta consola."""
    lineas = art.splitlines()
    ancho = max(len(l) for l in lineas)
    dos_col = cols >= ancho + _HUECO + ancho_panel
    # Al lado del panel el dibujo no compite con él por el alto.
    reserva = 2 if dos_col else _RESERVADO
    return filas >= len(lineas) + reserva, dos_col


def elegir_disposicion(ancho_panel: int) -> tuple[str, bool]:
    """Escoge el dibujo más grande que quepa y si va al lado del panel.

    Devuelve (dibujo, dos_columnas). Una sola decisión para que el tamaño
    elegido y la disposición nunca se contradigan.
    """
    cols, filas = shutil.get_terminal_size(fallback=(80, 24))
    for art in (GHOST_FULL.strip("\n"), GHOST_COMPACT.strip("\n")):
        cabe, dos_col = _cabe(art, ancho_panel, cols, filas)
        if cabe:
            return art, dos_col
    # Ni el compacto cabe a lo alto: se muestra igual, la consola hará scroll.
    compacto = GHOST_COMPACT.strip("\n")
    _, dos_col = _cabe(compacto, ancho_panel, cols, filas)
    return compacto, dos_col


def ghost_art() -> str:
    """El dibujo solo, sin decidir disposición."""
    return elegir_disposicion(_ANCHO_PANEL_MIN)[0]


def _qr_lines(url: str) -> list[str]:
    """El QR como lista de líneas, para poder colocarlo en una columna."""
    try:
        import qrcode  # type: ignore[import-not-found]
    except ImportError:
        return []
    buf = io.StringIO()
    code = qrcode.QRCode(border=1)
    code.add_data(url)
    code.print_ascii(out=buf, invert=True)
    return buf.getvalue().rstrip("\n").split("\n")


def _info_lines(url: str, port: int, players: int, pin: str | None, version: str) -> list[str]:
    """Panel de datos, al estilo neofetch: etiqueta en color, valor en blanco."""
    c = _C
    regla = "─" * 46

    def fila(label: str, value: str, color: str) -> str:
        return f"{c.cyan}{c.bold}{label:<14}{c.reset}{color}{value}{c.reset}"

    return [
        f"{c.bright_cyan}{c.bold}GhostPad{c.reset}{c.dim} v{version}{c.reset}",
        f"{c.dim}{regla}{c.reset}",
        fila("Dirección", url, c.white),
        fila("PIN", pin or "desactivado", c.yellow if pin else c.dim),
        fila("Jugadores", str(players), c.green),
        fila("Puerto", str(port), c.white),
        f"{c.dim}{regla}{c.reset}",
        f"{c.dim}Escanea el QR con cada teléfono, en la misma Wi-Fi.{c.reset}",
        f"{c.dim}Ctrl+C para salir.{c.reset}",
        "",
    ]


def _ghost_lines(art: str) -> tuple[list[str], list[str]]:
    """Devuelve (líneas sin color, líneas coloreadas con el degradado)."""
    planas = art.split("\n")
    total = len(planas)
    if not _C.reset:  # consola sin color
        return planas, planas
    pintadas = []
    for i, linea in enumerate(planas):
        r, g, b = _tono(i, total)
        pintadas.append(f"\033[38;2;{r};{g};{b}m{linea}\033[0m")
    return planas, pintadas


def print_banner(url: str, port: int, players: int, pin: str | None, version: str) -> None:
    # El panel se mide sin códigos de color: lo más ancho es la dirección.
    ancho_der = max(_ANCHO_PANEL_MIN, len(url) + 16)
    art, dos_columnas = elegir_disposicion(ancho_der)
    planas, pintadas = _ghost_lines(art)
    derecha = _info_lines(url, port, players, pin, version) + _qr_lines(url)
    ancho_izq = max(len(l) for l in planas)

    print()
    if dos_columnas:
        for i in range(max(len(pintadas), len(derecha))):
            izq_plana = planas[i] if i < len(planas) else ""
            izq = pintadas[i] if i < len(pintadas) else ""
            relleno = " " * (ancho_izq - len(izq_plana) + _HUECO)
            der = derecha[i] if i < len(derecha) else ""
            print(f"  {izq}{relleno}{der}".rstrip())
    else:
        # Ventana estrecha: una columna, el dibujo arriba y los datos debajo.
        for linea in pintadas:
            print(f"  {linea}")
        print()
        for linea in derecha:
            print(f"  {linea}" if linea else "")
    print()


# --------------------------------------------------------------------------- #
# Avisos de jugadores
# --------------------------------------------------------------------------- #
def _evento(marca: str, color: str, texto: str, detalle: str) -> None:
    c = _C
    hora = time.strftime("%H:%M:%S")
    print(f"  {c.dim}{hora}{c.reset}  {color}{marca}{c.reset} {color}{c.bold}{texto}{c.reset}"
          f"  {c.dim}{detalle}{c.reset}", flush=True)


def player_connected(slot: int, peer: str, en_uso: int, capacidad: int) -> None:
    _evento("▶", _C.green, f"P{slot} conectado",
            f"desde {peer} · {en_uso} de {capacidad} mandos en uso")


def player_disconnected(slot: int, en_uso: int, capacidad: int) -> None:
    libres = capacidad - en_uso
    if libres == capacidad:
        detalle = "no queda nadie jugando"
    elif libres == 1:
        detalle = "queda 1 mando libre"
    else:
        detalle = f"quedan {libres} mandos libres"
    _evento("■", _C.yellow, f"P{slot} desconectado", detalle)


def player_rejected(reason: str, peer: str, espera: float = 0.0) -> None:
    motivo = {
        "pin": "PIN incorrecto",
        "full": "no quedan mandos libres",
        "cooldown": "demasiados intentos seguidos",
    }.get(reason, reason)
    if espera > 0:
        motivo += f" · en espera {espera:.0f} s"
    _evento("✕", _C.yellow, "Conexión rechazada", f"{peer} · {motivo}")
