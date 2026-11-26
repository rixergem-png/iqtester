import json
from pathlib import Path

from iqtester import cli
from iqtester.preguntas import LETRAS_OPCION, cargar

RAIZ = Path(__file__).resolve().parents[1]


def test_banco_versionado_coincide_con_el_generador(tmp_path, capsys):
    """El banco del repo debe poder regenerarse idéntico (dataset reproducible)."""
    ruta = tmp_path / "b.json"
    assert cli.main(["generar", "--salida", str(ruta)]) == 0
    assert json.loads(ruta.read_text()) == json.loads((RAIZ / "datos/banco.json").read_text())
    assert "192 preguntas" in capsys.readouterr().out


def test_evaluar_con_umbrales_e_informe(tmp_path, capsys):
    informe = tmp_path / "r.md"
    assert cli.main(["evaluar", "--solver", "azar", "--solver", "reglas", "--split", "test",
                     "--umbrales", str(RAIZ / "umbrales.json"), "--informe", str(informe)]) == 0
    texto = informe.read_text()
    assert "### azar" in texto and "### reglas" in texto and "split: test" in texto
    assert "Todos los umbrales se cumplen" in capsys.readouterr().out


def test_evaluar_falla_si_no_cumple_umbral(tmp_path, capsys):
    u = tmp_path / "u.json"
    u.write_text(json.dumps({"reglas": {"cobertura_min": 1.0}}))
    assert cli.main(["evaluar", "--solver", "reglas", "--umbrales", str(u)]) == 1
    assert "UMBRALES INCUMPLIDOS" in capsys.readouterr().out


def test_evaluar_sin_umbrales(capsys):
    assert cli.main(["evaluar", "--solver", "simulado", "--split", "dev"]) == 0
    assert "umbrales" not in capsys.readouterr().out.lower()


def test_evaluar_claude_limita_gasto(monkeypatch, capsys):
    vistas = []

    class Falso:
        nombre = "claude"

        def responder(self, p):
            from iqtester.solvers import Respuesta
            vistas.append(p)
            return Respuesta(p.correcta, 0.9, 0.1)

    monkeypatch.setattr(cli, "crear", lambda nombre: Falso())
    assert cli.main(["evaluar", "--solver", "claude", "--max-ia", "5"]) == 0
    assert len(vistas) == 5 and "muestra de 5" in capsys.readouterr().out


def test_jugar(capsys):
    preguntas = __import__("random").Random(1).sample(cargar(RAIZ / "datos/banco.json"), 3)
    respuestas = iter([LETRAS_OPCION[preguntas[0].correcta], LETRAS_OPCION[preguntas[1].correcta], ""])
    args = cli.argparse.Namespace(n=3, semilla=1, banco=RAIZ / "datos/banco.json")
    assert cli.cmd_jugar(args, entrada=lambda _: next(respuestas)) == 0
    salida = capsys.readouterr().out
    assert "Resultado: 2/3 (67%)" in salida and "reglas:" in salida and "no una medida de CI" in salida
