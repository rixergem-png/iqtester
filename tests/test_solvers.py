from pathlib import Path
from types import SimpleNamespace

import pytest

from iqtester import solvers
from iqtester.preguntas import Pregunta, cargar

RAIZ = Path(__file__).resolve().parents[1]
BANCO = cargar(RAIZ / "datos/banco.json")


def test_reglas_aciertan_lo_conocido_y_se_abstienen_en_verbal():
    s = solvers.SolverReglas()
    for p in BANCO:
        r = s.responder(p)
        if p.categoria == "verbal":
            assert r.indice is None and r.confianza == 0.0
        else:
            assert r.indice == p.correcta and r.confianza == 1.0, p.id


def test_reglas_se_abstienen_si_no_entienden():
    rara = Pregunta("x", "logica", 1, "Premisas: Casi todos los zorbos son flimes.\n¿«Algo»?", ("a", "b", "c"), 0, "")
    assert solvers.SolverReglas().responder(rara).indice is None


def test_azar_reproducible_y_confianza_uniforme():
    a = [solvers.SolverAzar(3).responder(p).indice for p in BANCO[:20]]
    b = [solvers.SolverAzar(3).responder(p).indice for p in BANCO[:20]]
    assert a == b
    p = BANCO[0]
    assert solvers.SolverAzar().responder(p).confianza == pytest.approx(1 / len(p.opciones))


def test_simulado_reproducible_y_en_rango():
    a = [solvers.SolverSimulado().responder(p) for p in BANCO]
    assert a == [solvers.SolverSimulado().responder(p) for p in BANCO]
    assert all(0 <= r.confianza <= 1 and 0 <= r.indice < 4 for r in a)


def test_crear():
    assert solvers.crear("azar").nombre == "azar" and solvers.crear("reglas").nombre == "reglas"
    assert solvers.crear("simulado").nombre == "simulado"
    with pytest.raises(ValueError):
        solvers.crear("otro")


class ClienteFalso:
    def __init__(self, respuesta):
        self.kwargs = None
        self._r = respuesta
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kw):
        self.kwargs = kw
        return self._r


def _claude(monkeypatch, respuesta):
    import anthropic

    cliente = ClienteFalso(respuesta)
    monkeypatch.setattr(anthropic, "Anthropic", lambda: cliente)
    return solvers.SolverClaude(modelo="m"), cliente


@pytest.mark.parametrize("letra, confianza, indice", [("B", 0.8, 1), (" c ", 0.6, 2), ("Z", 0.9, None), ("", 0.9, None)])
def test_claude_interpreta_la_letra(monkeypatch, letra, confianza, indice):
    s, cliente = _claude(monkeypatch, SimpleNamespace(stop_reason="end_turn",
                                                    parsed_output=SimpleNamespace(letra=letra, confianza=confianza)))
    p = BANCO[0]
    r = s.responder(p)
    assert r.indice == indice and r.confianza == (confianza if indice is not None else 0.0)
    k = cliente.kwargs
    assert k["model"] == "m" and k["fallbacks"] == "default" and "A) " in k["messages"][0]["content"]
    assert s.nombre == "claude:m"


def test_claude_rechazo_es_abstencion(monkeypatch):
    s, _ = _claude(monkeypatch, SimpleNamespace(stop_reason="refusal", parsed_output=None))
    assert s.responder(BANCO[0]).indice is None


def test_claude_no_acepta_letra_fuera_de_las_opciones(monkeypatch):
    logica = next(p for p in BANCO if p.categoria == "logica")  # solo A-C
    s, _ = _claude(monkeypatch, SimpleNamespace(stop_reason="end_turn",
                                              parsed_output=SimpleNamespace(letra="D", confianza=0.9)))
    assert s.responder(logica).indice is None
