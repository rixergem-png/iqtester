import pytest

from iqtester import graficos


def _datos():
    rs = [{"categoria": "series", "dificultad": 1, "elegida": 0, "correcta": 0, "confianza": 0.9},
          {"categoria": "series", "dificultad": 2, "elegida": 1, "correcta": 0, "confianza": 0.3},
          {"categoria": "logica", "dificultad": 2, "elegida": None, "correcta": 0, "confianza": 0.0},
          {"categoria": "logica", "dificultad": 3, "elegida": 2, "correcta": 2, "confianza": 1.0}]
    return {"solver": "x", "resultados": rs}


def test_exactitud_por_con_wilson():
    from iqtester.metricas import wilson

    (p, err_bajo, err_alto), = graficos.exactitud_por(_datos(), "categoria", ["series"])
    bajo, alto = wilson(1, 2)
    assert p == 0.5 and err_bajo == pytest.approx(0.5 - bajo) and err_alto == pytest.approx(alto - 0.5)
    assert graficos.exactitud_por(_datos(), "categoria", ["verbal"]) == [(0.0, 0.0, 1.0)]


def test_curva_calibracion_ignora_abstenciones():
    puntos = graficos.curva_calibracion(_datos(), tramos=5)
    assert puntos == [(0.3, 0.0, 1), pytest.approx((0.95, 1.0, 2))]


def test_dibujar_crea_tres_png(tmp_path):
    import json

    ruta = tmp_path / "x.json"
    ruta.write_text(json.dumps(_datos()))
    creados = graficos.dibujar([ruta, ruta], tmp_path / "g")
    assert [c.name for c in creados] == ["exactitud_categorias.png", "calibracion.png", "exactitud_dificultad.png"]
    assert all(c.stat().st_size > 5_000 for c in creados)
