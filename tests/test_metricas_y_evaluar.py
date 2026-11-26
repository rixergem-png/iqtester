import pytest

from iqtester import evaluar as ev
from iqtester.metricas import ece, percentil, wilson
from iqtester.preguntas import Pregunta


def test_wilson_valores_conocidos():
    assert wilson(8, 10) == pytest.approx((0.4902, 0.9433), abs=1e-4)
    assert wilson(0, 0) == (0.0, 1.0)
    assert wilson(10, 10)[1] == 1.0 and wilson(10, 10)[0] == pytest.approx(0.7225, abs=1e-4)
    assert wilson(0, 10)[0] == 0.0


def test_ece():
    assert ece([], []) == 0.0
    assert ece([1.0, 1.0], [True, True]) == 0.0
    assert ece([0.9, 0.9], [True, False]) == pytest.approx(0.4)
    assert ece([0.25, 0.75], [False, True]) == pytest.approx(0.25)


def test_percentil():
    assert percentil([], 0.5) == 0.0
    datos = [5, 1, 4, 2, 3]
    assert percentil(datos, 0.5) == 3 and percentil(datos, 0.95) == 5 and percentil(datos, 0) == 1


def _p(cat="series", correcta=0):
    return Pregunta("id", cat, 1, "e", ("a", "b", "c", "d"), correcta, "x")


def test_estadisticas_exactas():
    rs = [ev.Resultado(_p(), 0, 1.0, 1.0), ev.Resultado(_p(), 1, 0.5, 2.0),
          ev.Resultado(_p(), None, 0.0, 3.0), ev.Resultado(_p(), 0, 1.0, 4.0)]
    s = ev.estadisticas(rs)
    assert (s["n"], s["respondidas"], s["aciertos"]) == (4, 3, 2)
    assert s["exactitud"] == 0.5 and s["cobertura"] == 0.75 and s["precision"] == pytest.approx(2 / 3)
    assert (s["ic95_bajo"], s["ic95_alto"]) == pytest.approx(wilson(2, 4))
    assert s["ece"] == pytest.approx(ece([1.0, 0.5, 1.0], [True, False, True]))
    assert s["p50_s"] == 2.0 and s["p95_s"] == 4.0


def test_estadisticas_vacias():
    s = ev.estadisticas([])
    assert s["exactitud"] == s["cobertura"] == s["precision"] == 0.0


def test_resumen_por_categoria():
    rs = [ev.Resultado(_p("series"), 0, 1, 0), ev.Resultado(_p("verbal"), 1, 1, 0)]
    res = ev.resumen(rs)
    assert list(res) == ["global", "series", "verbal"]
    assert res["series"]["exactitud"] == 1.0 and res["verbal"]["exactitud"] == 0.0


def test_umbrales():
    s = {"precision": 0.95, "cobertura": 0.5, "exactitud": 0.3}
    assert ev.comprobar_umbrales(s, {"precision_min": 0.95, "exactitud_max": 0.3}) == []
    fallos = ev.comprobar_umbrales(s, {"precision_min": 0.99, "cobertura_min": 0.4, "exactitud_max": 0.2})
    assert len(fallos) == 2 and "precision" in fallos[0] and "máximo" in fallos[1]


def test_tabla_markdown():
    t = ev.tabla_markdown("x", ev.resumen([ev.Resultado(_p(), 0, 1.0, 0.5)]))
    assert "### x" in t and "| global | 1 | 100% (" in t


def test_ece_cada_confianza_en_un_solo_tramo():
    assert ece([0.2], [False]) == pytest.approx(0.2)
    assert ece([0.95, 1.0], [True, False]) == pytest.approx(abs(0.5 - 0.975))  # 1.0 cae en el último tramo


def test_umbrales_con_metricas_que_llevan_guion_bajo():
    fallos = ev.comprobar_umbrales({"p95_s": 3.0}, {"p95_s_max": 2.0})
    assert fallos == ["p95_s = 3.000 (máximo 2.0)"]
    assert ev.comprobar_umbrales({"precision": 0.5}, {"precision_min": 0.9}) == ["precision = 0.500 (mínimo 0.9)"]
