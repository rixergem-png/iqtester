import random
from collections import Counter
from pathlib import Path

import pytest

from iqtester import preguntas as pq
from iqtester.solvers import candidatos

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def banco():
    return pq.generar_banco(por_categoria=20, semilla=11, manuales=RAIZ / "datos/manuales.json")


def test_reproducible(banco):
    assert pq.generar_banco(20, 11, RAIZ / "datos/manuales.json") == banco
    assert pq.generar_banco(20, 12) != pq.generar_banco(20, 11)


def test_estructura_de_cada_pregunta(banco):
    assert len(banco) == 6 * 20 + 12
    assert len({p.id for p in banco}) == len(banco)
    for p in banco:
        assert len(set(p.opciones)) == len(p.opciones), p.id
        assert len(p.opciones) == (3 if p.categoria == "logica" else 4), p.id
        assert 0 <= p.correcta < len(p.opciones) and p.respuesta == p.opciones[p.correcta]
        assert p.dificultad in (1, 2, 3) and p.split in ("dev", "test") and p.explicacion


def test_respuesta_unica_para_las_reglas(banco):
    for p in banco:
        if p.categoria != "verbal":
            assert candidatos(p) == {p.respuesta}, p.id


def test_logica_equilibrada(banco):
    conteo = Counter(p.respuesta for p in banco if p.categoria == "logica")
    assert set(conteo.values()) == {20 // 3, 20 // 3 + 1} or max(conteo.values()) - min(conteo.values()) <= 1


def test_split_estable_y_aproximado():
    assert pq.split_de("series-001") == pq.split_de("series-001")
    ids = [f"x-{i}" for i in range(2000)]
    proporcion = sum(pq.split_de(i) == "test" for i in ids) / len(ids)
    assert 0.25 < proporcion < 0.35
    assert pq.split_de("x", fraccion_test=0) == "dev" and pq.split_de("x", fraccion_test=1) == "test"


def test_guardar_y_cargar(tmp_path, banco):
    ruta = tmp_path / "b.json"
    pq.guardar(banco, ruta, semilla=11)
    assert pq.cargar(ruta) == banco
    test = pq.cargar(ruta, "test")
    assert test and all(p.split == "test" for p in test)
    assert len(test) + len(pq.cargar(ruta, "dev")) == len(banco)


def test_opciones_sin_distractores_suficientes():
    with pytest.raises(ValueError):
        pq._opciones(random.Random(0), "5", ["5", "6"])


def test_frases_de_logica():
    assert pq.frase("todos", "zorbo", "flime") == "Todos los zorbos son flimes"
    assert pq.frase("ningun", "zorbo", "flime") == "Ningún zorbo es flime"
    assert pq.frase("algunos_no", "zorbo", "flime") == "Algunos zorbos no son flimes"
