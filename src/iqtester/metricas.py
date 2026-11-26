"""Métricas con incertidumbre. Solo librería estándar."""

from __future__ import annotations

import math


def wilson(aciertos: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confianza de Wilson (95 % por defecto) para una proporción.

    Es mejor que p ± z·√(p(1-p)/n) con muestras pequeñas o proporciones cerca de 0 o 1.
    """
    if n == 0:
        return (0.0, 1.0)
    p = aciertos / n
    denominador = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denominador
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominador
    return (max(0.0, centro - margen), min(1.0, centro + margen))


def ece(confianzas: list[float], aciertos: list[bool], bins: int = 10) -> float:
    """Error de calibración esperado: cuánto se aleja la confianza declarada del acierto real."""
    if not confianzas:
        return 0.0
    total, n = 0.0, len(confianzas)
    for b in range(bins):
        bajo, alto = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(confianzas) if bajo <= c < alto or (b == bins - 1 and c == 1.0)]
        if idx:
            conf = sum(confianzas[i] for i in idx) / len(idx)
            acc = sum(aciertos[i] for i in idx) / len(idx)
            total += abs(acc - conf) * len(idx) / n
    return total


def percentil(valores: list[float], q: float) -> float:
    """Percentil por rango más cercano (q entre 0 y 1)."""
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    k = max(0, math.ceil(q * len(ordenados)) - 1)
    return ordenados[k]
