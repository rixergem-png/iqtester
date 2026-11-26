from pathlib import Path

from iqtester import cli
from iqtester.preguntas import Pregunta, cargar
from iqtester.sesgo import medir, rotar
from iqtester.solvers import Respuesta, SolverReglas

RAIZ = Path(__file__).resolve().parents[1]
P = Pregunta("p", "series", 1, "e", ("a", "b", "c", "d"), 1, "x")


def test_rotar_mantiene_la_respuesta_correcta():
    for k in range(6):
        q = rotar(P, k)
        assert q.respuesta == "b" and sorted(q.opciones) == ["a", "b", "c", "d"] and q.id == f"p@r{k % 4}"
    assert rotar(P, 1).opciones == ("d", "a", "b", "c") and rotar(P, 0).opciones == P.opciones


class SiempreA:
    nombre = "siempre-a"

    def responder(self, p):
        return Respuesta(0, 1.0, 0.0)


class Abstiene:
    nombre = "abstiene"

    def responder(self, p):
        return Respuesta(None, 0.0, 0.0)


def test_sesgo_detecta_al_que_responde_por_posicion():
    r = medir(SiempreA(), [P], rotaciones=4)
    assert r["consistencia"] == 0.0 and r["posiciones"] == {"A": 4}
    assert r["exactitud_media"] == 0.25 and r["siempre_bien"] == 0.0
    assert r["filas"][0]["respuestas"] == ["a", "d", "c", "b"]


def test_sesgo_reglas_consistentes_y_abstencion_no_cuenta():
    banco = [p for p in cargar(RAIZ / "datos/banco.json", "test") if p.categoria in ("series", "logica")]
    r = medir(SolverReglas(), banco)
    assert r["consistencia"] == 1.0 and r["siempre_bien"] == 1.0
    assert medir(Abstiene(), [P])["consistencia"] == 0.0
    assert medir(SiempreA(), [])["consistencia"] == 0.0


def test_cli_sesgo(tmp_path, capsys):
    assert cli.main(["sesgo", "--solver", "reglas", "--guardar", str(tmp_path)]) == 0
    assert (tmp_path / "reglas.json").exists() and "consistencia 96%" in capsys.readouterr().out
