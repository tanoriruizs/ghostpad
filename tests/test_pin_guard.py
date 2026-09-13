"""El freno contra la fuerza bruta sobre el PIN."""

import pytest

from server import PinGuard


class FakeClock:
    """Reloj manual: los tests no deben depender del tiempo real."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def guard(clock: FakeClock) -> PinGuard:
    return PinGuard(clock=clock)


def test_una_ip_nueva_no_espera(guard: PinGuard):
    assert guard.retry_after("10.0.0.5") == 0


def test_los_primeros_fallos_no_castigan(guard: PinGuard):
    """Equivocarse un par de veces tecleando el PIN es normal."""
    for _ in range(PinGuard.MAX_FAILS - 1):
        assert guard.record_failure("10.0.0.5") == 0
    assert guard.retry_after("10.0.0.5") == 0


def test_al_pasarse_de_fallos_empieza_la_espera(guard: PinGuard):
    for _ in range(PinGuard.MAX_FAILS):
        guard.record_failure("10.0.0.5")
    assert guard.retry_after("10.0.0.5") == pytest.approx(PinGuard.BASE_COOLDOWN)


def test_la_espera_se_dobla_con_cada_intento(guard: PinGuard):
    for _ in range(PinGuard.MAX_FAILS):
        guard.record_failure("10.0.0.5")
    primera = guard.retry_after("10.0.0.5")
    segunda = guard.record_failure("10.0.0.5")
    assert segunda == pytest.approx(primera * 2)


def test_la_espera_tiene_techo(guard: PinGuard):
    for _ in range(60):
        espera = guard.record_failure("10.0.0.5")
    assert espera == PinGuard.MAX_COOLDOWN


def test_la_espera_se_agota_con_el_tiempo(guard: PinGuard, clock: FakeClock):
    for _ in range(PinGuard.MAX_FAILS):
        guard.record_failure("10.0.0.5")
    clock.advance(PinGuard.BASE_COOLDOWN + 0.1)
    assert guard.retry_after("10.0.0.5") == 0


def test_acertar_borra_el_historial(guard: PinGuard):
    for _ in range(PinGuard.MAX_FAILS + 2):
        guard.record_failure("10.0.0.5")
    guard.record_success("10.0.0.5")
    assert guard.retry_after("10.0.0.5") == 0
    assert guard.record_failure("10.0.0.5") == 0


def test_el_castigo_es_por_ip(guard: PinGuard):
    """Un vecino torpe no debe dejar fuera al resto de la casa."""
    for _ in range(PinGuard.MAX_FAILS):
        guard.record_failure("10.0.0.5")
    assert guard.retry_after("10.0.0.5") > 0
    assert guard.retry_after("10.0.0.9") == 0


def test_las_ips_inactivas_se_olvidan(guard: PinGuard, clock: FakeClock):
    """Sin esto el diccionario crecería indefinidamente."""
    guard.record_failure("10.0.0.5")
    clock.advance(PinGuard.FORGET_AFTER + 1)
    guard.retry_after("otra-ip")  # cualquier consulta dispara la limpieza
    assert "10.0.0.5" not in guard._fails


def test_diez_mil_intentos_ya_no_caben_en_una_tarde(guard: PinGuard, clock: FakeClock):
    """Recorrer las 10 000 combinaciones debe costar horas, no segundos."""
    total = 0.0
    for _ in range(10_000):
        espera = guard.record_failure("10.0.0.5")
        total += espera
        clock.advance(espera)
    assert total > 3600
