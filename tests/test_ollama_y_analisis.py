import json
from pathlib import Path

import pytest

from iqtester import cli, solvers
from iqtester import evaluar as ev
from iqtester.preguntas import cargar

RAIZ = Path(__file__).resolve().parents[1]
BANCO = cargar(RAIZ / "datos/banco.json")
LOGICA = next(p for p in BANCO if p.categoria == "logica")


def _ollama(monkeypatch, contenido):
    s = solvers.SolverOllama("modelo:1b")
    enviado = {}

    def falso(cuerpo):
        enviado.update(cuerpo)
        return {"message": {"content": contenido}}

    monkeypatch.setattr(s, "_llamar", falso)
    return s, enviado


def test_ollama_pide_json_con_esquema_y_temperatura_cero(monkeypatch):
    s, enviado = _ollama(monkeypatch, '{"letra": "b", "confianza": 0.7}')
    r = s.responder(LOGICA)
    assert r.indice == 1 and r.confianza == 0.7 and s.nombre == "ollama:modelo:1b"
    assert enviado["format"]["properties"]["letra"]["enum"] == ["A", "B", "C"]  # solo las letras válidas
    assert enviado["options"] == {"temperature": 0, "seed": 0, "num_ctx": 2048} and enviado["stream"] is False


@pytest.mark.parametrize("contenido", ['no es json', '{"letra": "D", "confianza": 0.9}', '{"confianza": 0.9}',
                                       '{"letra": "A", "confianza": "mucha"}'])
def test_ollama_salida_invalida_es_abstencion(monkeypatch, contenido):
    s, _ = _ollama(monkeypatch, contenido)
    r = s.responder(LOGICA)
    assert r.indice is None and r.confianza == 0.0


def test_ollama_recorta_confianza(monkeypatch):
    s, _ = _ollama(monkeypatch, '{"letra": "A", "confianza": 7}')
    assert s.responder(LOGICA).confianza == 1.0


def test_ollama_llamada_http(monkeypatch):
    import io
    import urllib.request

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    vistos = {}

    def urlopen(peticion, timeout):
        vistos["url"], vistos["cuerpo"] = peticion.full_url, json.loads(peticion.data)
        return R(b'{"message": {"content": "{}"}}')

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    assert solvers.SolverOllama("m")._llamar({"x": 1}) == {"message": {"content": "{}"}}
    assert vistos["url"].endswith("/api/chat") and vistos["cuerpo"] == {"x": 1}


def test_crear_ollama():
    assert solvers.crear("ollama:qwen2.5:1.5b").nombre == "ollama:qwen2.5:1.5b"


def test_por_dificultad_y_json():
    rs = ev.evaluar(solvers.SolverReglas(), BANCO[:40])
    dif = ev.por_dificultad(rs)
    assert list(dif) == sorted(dif) and sum(s["n"] for s in dif.values()) == 40
    datos = ev.a_json("reglas", rs)
    assert datos["solver"] == "reglas" and len(datos["resultados"]) == 40
    assert set(datos["resultados"][0]) == {"id", "categoria", "dificultad", "elegida", "correcta", "confianza", "latencia"}


def test_errores_lista_fallos_y_abstenciones():
    preguntas = {p.id: p for p in BANCO}
    p = BANCO[0]
    mal = 0 if p.correcta != 0 else 1
    datos = {"solver": "x", "resultados": [
        {"id": p.id, "categoria": p.categoria, "dificultad": 1, "elegida": mal, "correcta": p.correcta, "confianza": 0.8},
        {"id": BANCO[1].id, "categoria": "series", "dificultad": 2, "elegida": None, "correcta": 0, "confianza": 0.0},
        {"id": BANCO[2].id, "categoria": "series", "dificultad": 2, "elegida": 3, "correcta": 3, "confianza": 1.0}]}
    texto = ev.errores(datos, preguntas)
    assert "## series (2 fallos)" in texto and "se abstuvo" in texto and "(80%)" in texto
    assert BANCO[2].id not in texto
    assert ev.errores({"solver": "y", "resultados": []}, preguntas) == "Errores de y: ninguno."


def test_regresion():
    assert ev.comprobar_regresion({"a": 0.80}, {"a": 0.81}) == []                 # dentro de la tolerancia
    fallos = ev.comprobar_regresion({"a": 0.70, "b": 0.9}, {"a": 0.80, "c": 0.5})
    assert len(fallos) == 1 and fallos[0].startswith("a:")


def test_cli_guardar_baseline_y_regresion(tmp_path, capsys):
    base = tmp_path / "baseline.json"
    args = ["evaluar", "--solver", "reglas", "--split", "test", "--guardar", str(tmp_path / "res")]
    assert cli.main(args + ["--actualizar-baseline", str(base)]) == 0
    assert (tmp_path / "res" / "reglas.json").exists()
    assert cli.main(args + ["--baseline", str(base)]) == 0                       # igual que el baseline
    base.write_text(json.dumps({"reglas": 1.5}))                                   # baseline imposible
    assert cli.main(args + ["--baseline", str(base)]) == 1
    assert "[regresión]" in capsys.readouterr().out
    assert cli.main(["errores", str(tmp_path / "res" / "reglas.json")]) == 0
    assert "Errores de reglas" in capsys.readouterr().out


def test_cli_web_solo_incluye_solvers_completos(tmp_path, capsys):
    res = tmp_path / "res"
    assert cli.main(["evaluar", "--solver", "azar", "--solver", "reglas", "--split", "test", "--guardar", str(res)]) == 0
    (res / "parcial.json").write_text(json.dumps({"solver": "parcial", "resultados": []}))  # sin todas las preguntas
    salida = tmp_path / "web.json"
    assert cli.main(["web", "--resultados", str(res), "--salida", str(salida)]) == 0
    datos = json.loads(salida.read_text())
    test = [p for p in BANCO if p.split == "test"]
    assert len(datos["preguntas"]) == len(test) and "split" not in datos["preguntas"][0]
    assert set(datos["solvers"]) == {"azar", "reglas"}
    assert all(isinstance(v, bool) for v in datos["solvers"]["reglas"].values())


def test_cli_informe_desde_resultados_guardados(tmp_path):
    res = tmp_path / "res"
    cli.main(["evaluar", "--solver", "reglas", "--split", "test", "--guardar", str(res)])
    salida = tmp_path / "inf.md"
    assert cli.main(["informe", str(res / "reglas.json"), "--salida", str(salida)]) == 0
    texto = salida.read_text()
    assert "### reglas" in texto and "| global | 56 | 96%" in texto and "| dificultad 3 |" in texto
