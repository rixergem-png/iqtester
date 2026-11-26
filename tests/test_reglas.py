import pytest

from iqtester import reglas
from iqtester.reglas import NO, NO_SE, SI


@pytest.mark.parametrize("serie, esperado", [
    ([2, 5, 8, 11, 14], {17}),                 # aritmética
    ([3, 6, 12, 24, 48], {96}),                # geométrica
    ([1, 2, 4, 7, 11], {16}),                  # diferencias crecientes
    ([1, 1, 2, 3, 5, 8], {13}),                # Fibonacci
    ([1, 50, 3, 47, 5, 44, 7], {41}),          # intercalada: sigue la de posiciones pares
    ([1, 50, 3, 47, 5, 44], {7}),              # intercalada (6 términos): el 7.º es de la serie 1, 3, 5
    ([1, 50, 3, 47, 5], set()),                # intercalada con solo 5 términos: no hay pruebas suficientes
    ([5, 1, 4, 1, 5, 9], set()),               # sin regla conocida
])
def test_predecir_serie(serie, esperado):
    assert reglas.predecir_serie(serie) == esperado


def test_serie_constante_no_es_geometrica_de_razon_1():
    assert reglas.predecir_serie([4, 4, 4, 4]) == {4}


@pytest.mark.parametrize("filas, esperado", [
    ([[2, 3, 5], [4, 2, 6], [6, 2, 0]], {8}),          # suma
    ([[9, 3, 6], [7, 2, 5], [8, 1, 0]], {7}),          # resta
    ([[2, 3, 6], [4, 5, 20], [3, 3, 0]], {9}),         # producto
    ([[1, 3, 5], [2, 6, 10], [4, 5, 0]], {6}),         # progresión aritmética
    ([[3, 5, 12], [7, 6, 7], [10, 1, 0]], {9}),        # todas suman 20
])
def test_predecir_matriz(filas, esperado):
    assert reglas.predecir_matriz(filas) == esperado


def test_matriz_ambigua_devuelve_varias_respuestas():
    # a + b encaja, y además las dos filas suman 10: el generador descartaría esta pregunta
    assert reglas.predecir_matriz([[2, 3, 5], [4, 1, 5], [6, 2, 0]]) == {8, 2}


@pytest.mark.parametrize("pares, x, esperado", [
    ([(2, 7), (3, 10), (5, 16)], 7, {22}),             # 3x + 1
    ([(2, 5), (3, 10), (4, 17)], 6, {37}),             # x² + 1
    ([(2, 8), (3, 27), (4, 64)], 5, {125}),            # x³
    ([(2, 3), (3, 9), (4, 1)], 5, set()),              # nada encaja
])
def test_predecir_analogia(pares, x, esperado):
    assert reglas.predecir_analogia(pares, x) == esperado


@pytest.mark.parametrize("premisas, conclusion, esperado", [
    ([("todos", "a", "b"), ("todos", "b", "c")], ("todos", "a", "c"), SI),       # Barbara
    ([("todos", "a", "b"), ("ningun", "b", "c")], ("algunos", "a", "c"), NO),
    ([("todos", "a", "b"), ("algunos", "b", "c")], ("algunos", "a", "c"), NO_SE),
    ([("ningun", "a", "b"), ("todos", "b", "c")], ("algunos_no", "c", "a"), SI),  # existe un b que es c y no es a
    ([("algunos", "a", "b"), ("todos", "b", "c")], ("algunos", "a", "c"), SI),    # Darii
])
def test_silogismos_conocidos(premisas, conclusion, esperado):
    assert reglas.evaluar_silogismo(premisas, conclusion) == esperado


def test_premisas_contradictorias():
    with pytest.raises(ValueError, match="contradictorias"):
        reglas.evaluar_silogismo([("todos", "a", "b"), ("ningun", "a", "b")], ("todos", "a", "a"))


def test_forma_desconocida():
    with pytest.raises(ValueError, match="Forma"):
        reglas._cumple("casi_todos", "a", "b", (frozenset("a"),))


@pytest.mark.parametrize("inicio, giros, final", [
    ("Norte", [(90, "derecha")], "Este"),
    ("Norte", [(90, "izquierda")], "Oeste"),
    ("Este", [(180, "derecha"), (270, "izquierda")], "Norte"),
    ("Sur", [(270, "derecha"), (90, "derecha"), (90, "izquierda")], "Este"),
])
def test_girar(inicio, giros, final):
    assert reglas.girar(inicio, giros) == final


@pytest.mark.parametrize("serie, esperado", [
    ([3, 6, 12], {24}),                        # geométrica con solo 3 términos
    ([1, 2, 4, 7], {11}),                      # diferencias crecientes con 4 términos
    ([1, 2, 3, 5], {8}),                       # Fibonacci con 4 términos
    ([2, 3, 5, 8], {12, 13}),                  # ambigua: Fibonacci (13) o diferencias +1, +2, +3 (12)
    ([1, 50, 3, 47, 5, 44, 7, 41], {9}),       # intercalada con 8 términos: sigue la de posiciones pares
    ([1, 50, 3, 47, 5, 44, 8, 41], set()),     # una de las dos series intercaladas no es aritmética
    ([5, 10, 5, 10], set()),                   # razones distintas (2 y 1/2): no es geométrica
])
def test_predecir_serie_bordes(serie, esperado):
    assert reglas.predecir_serie(serie) == esperado


def test_geometrica_con_cero_no_se_considera():
    assert reglas.predecir_serie([0, 0, 0, 0]) == {0}  # solo aritmética (d = 0)


def test_analogia_suma_constante():
    assert reglas.predecir_analogia([(2, 5), (4, 7), (6, 9)], 10) == {13}  # y = x + 3


def test_analogia_no_lineal_entera():
    # los dos primeros pares darían pendiente 3/2: no es una regla lineal entera
    assert reglas.predecir_analogia([(2, 1), (4, 4), (6, 7)], 8) == set()
