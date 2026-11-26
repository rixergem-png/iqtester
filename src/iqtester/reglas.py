"""Motores de razonamiento por reglas.

Los usa el generador (para descartar preguntas ambiguas) y el SolverReglas (para responder).
Cada función devuelve el CONJUNTO de respuestas que dan todos los modelos que encajan:
- un solo valor  -> la pregunta tiene respuesta única para estas reglas;
- varios valores -> ambigua (el generador la descarta);
- vacío          -> ninguna regla conocida encaja (el solver se abstiene).
"""

from __future__ import annotations

import itertools
from fractions import Fraction

# ---------------------------------------------------------------- series numéricas


def predecir_serie(xs: list[int]) -> set[int]:
    """Siguiente término según cada modelo que encaja con todos los términos dados."""
    n = len(xs)
    preds: set[int] = set()
    difs = [b - a for a, b in zip(xs, xs[1:])]

    if len(set(difs)) == 1:  # aritmética
        preds.add(xs[-1] + difs[0])

    if n >= 3 and all(x != 0 for x in xs[:-1]):  # geométrica de razón entera
        razones = {Fraction(xs[i + 1], xs[i]) for i in range(n - 1)}
        if len(razones) == 1:
            r = razones.pop()
            if r.denominator == 1 and r not in (0, 1):
                preds.add(xs[-1] * int(r))

    segundas = [b - a for a, b in zip(difs, difs[1:])]
    if n >= 4 and len(set(segundas)) == 1 and segundas[0] != 0:  # diferencias crecientes
        preds.add(xs[-1] + difs[-1] + segundas[0])

    if n >= 4 and all(xs[i] == xs[i - 1] + xs[i - 2] for i in range(2, n)):  # tipo Fibonacci
        preds.add(xs[-1] + xs[-2])

    if n >= 6 and len(set(difs)) > 1:  # dos series aritméticas intercaladas
        pares, impares = xs[0::2], xs[1::2]
        dp = {b - a for a, b in zip(pares, pares[1:])}
        di = {b - a for a, b in zip(impares, impares[1:])}
        if len(dp) == 1 and len(di) == 1:
            sigue = pares if n % 2 == 0 else impares
            preds.add(sigue[-1] + (dp if n % 2 == 0 else di).pop())

    return preds


# ---------------------------------------------------------------- matrices 3x3

REGLAS_FILA = {
    "suma": lambda a, b: a + b,
    "resta": lambda a, b: a - b,
    "producto": lambda a, b: a * b,
    "progresion": lambda a, b: 2 * b - a,
}


def predecir_matriz(filas: list[list[int]]) -> set[int]:
    """Filas 1 y 2 completas; fila 3 con dos números. Devuelve el tercero según cada regla que encaja."""
    completas, (a3, b3) = filas[:2], filas[2][:2]
    preds = {f(a3, b3) for f in REGLAS_FILA.values() if all(f(a, b) == c for a, b, c in completas)}
    sumas = {sum(f) for f in completas}
    if len(sumas) == 1:  # todas las filas suman lo mismo
        preds.add(sumas.pop() - a3 - b3)
    return preds


# ---------------------------------------------------------------- analogías numéricas


def predecir_analogia(pares: list[tuple[int, int]], x: int) -> set[int]:
    """Pares (x, f(x)); predice f(x) para lineal (a·x+b enteros), x²+k y x³."""
    preds: set[int] = set()
    (x1, y1), (x2, y2) = pares[0], pares[1]
    if x2 != x1 and (y2 - y1) % (x2 - x1) == 0:
        a = (y2 - y1) // (x2 - x1)
        b = y1 - a * x1
        if a != 0 and all(a * px + b == py for px, py in pares):
            preds.add(a * x + b)
    k = y1 - x1 * x1
    if all(px * px + k == py for px, py in pares):
        preds.add(x * x + k)
    if all(px**3 == py for px, py in pares):
        preds.add(x**3)
    return preds


# ---------------------------------------------------------------- lógica (silogismos)

FORMAS = ("todos", "algunos", "ningun", "algunos_no")
SI, NO, NO_SE = "Sí, siempre", "No, nunca", "No se puede saber"
INDIVIDUOS = 6  # basta para encontrar un contraejemplo en silogismos de 3 términos


def _cumple(forma: str, x: str, y: str, mundo: tuple[frozenset, ...]) -> bool:
    if forma == "todos":
        return all(y in ind for ind in mundo if x in ind)
    if forma == "algunos":
        return any(x in ind and y in ind for ind in mundo)
    if forma == "ningun":
        return not any(x in ind and y in ind for ind in mundo)
    if forma == "algunos_no":
        return any(x in ind and y not in ind for ind in mundo)
    raise ValueError(f"Forma desconocida: {forma}")


def evaluar_silogismo(premisas: list[tuple[str, str, str]], conclusion: tuple[str, str, str]) -> str:
    """Revisa todos los mundos posibles (con al menos un individuo de cada término).

    Sí, siempre       -> la conclusión es verdadera en todos los mundos donde las premisas lo son
    No, nunca         -> es falsa en todos ellos
    No se puede saber -> hay mundos de los dos tipos
    """
    terminos = sorted({t for _, x, y in [*premisas, conclusion] for t in (x, y)})
    tipos = [frozenset(c) for r in range(len(terminos) + 1) for c in itertools.combinations(terminos, r)]
    valores: set[bool] = set()
    for mundo in itertools.combinations_with_replacement(tipos, INDIVIDUOS):
        if not all(any(t in ind for ind in mundo) for t in terminos):
            continue
        if all(_cumple(f, x, y, mundo) for f, x, y in premisas):
            valores.add(_cumple(*conclusion, mundo))
            if len(valores) == 2:
                return NO_SE
    if not valores:
        raise ValueError("Las premisas son contradictorias")
    return SI if valores == {True} else NO


# ---------------------------------------------------------------- orientación espacial

DIRECCIONES = ("Norte", "Este", "Sur", "Oeste")


def girar(inicio: str, giros: list[tuple[int, str]]) -> str:
    """giros: [(grados múltiplo de 90, 'derecha'|'izquierda'), ...]"""
    pos = DIRECCIONES.index(inicio)
    for grados, lado in giros:
        pasos = grados // 90
        pos = (pos + (pasos if lado == "derecha" else -pasos)) % 4
    return DIRECCIONES[pos]
