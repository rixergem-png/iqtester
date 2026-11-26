"""Gráficos a partir de los resultados guardados (necesita matplotlib: pip install -e ".[graficos]")."""

from __future__ import annotations

import json
from pathlib import Path

from .metricas import wilson
from .preguntas import CATEGORIAS

COLORES = ["#9aa5b1", "#2f6fdf", "#e8833a", "#3aa76d", "#b04fc9", "#d64545"]


def _cargar(rutas: list[Path]) -> list[dict]:
    return [json.loads(r.read_text(encoding="utf-8")) for r in rutas]


def exactitud_por(datos: dict, clave: str, valores) -> list[tuple[float, float, float]]:
    """(exactitud, error inferior, error superior) para cada valor de `clave`, con IC de Wilson."""
    salida = []
    for v in valores:
        rs = [r for r in datos["resultados"] if r[clave] == v]
        k = sum(r["elegida"] == r["correcta"] for r in rs)
        p = k / len(rs) if rs else 0.0
        bajo, alto = wilson(k, len(rs))
        salida.append((p, p - bajo, alto - p))
    return salida


def curva_calibracion(datos: dict, tramos: int = 5) -> list[tuple[float, float, int]]:
    """(confianza media, acierto real, n) por tramo de confianza; solo respuestas dadas."""
    rs = [r for r in datos["resultados"] if r["elegida"] is not None]
    puntos = []
    for t in range(tramos):
        bajo, alto = t / tramos, (t + 1) / tramos
        grupo = [r for r in rs if bajo <= r["confianza"] < alto or (t == tramos - 1 and r["confianza"] == 1.0)]
        if grupo:
            puntos.append((sum(r["confianza"] for r in grupo) / len(grupo),
                           sum(r["elegida"] == r["correcta"] for r in grupo) / len(grupo), len(grupo)))
    return puntos


def dibujar(rutas: list[Path], carpeta: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    datos = _cargar(rutas)
    carpeta.mkdir(parents=True, exist_ok=True)
    categorias = [c for c in (*CATEGORIAS, "verbal") if any(r["categoria"] == c for d in datos for r in d["resultados"])]
    creados = []

    # 1) exactitud por categoría con IC 95 %
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ancho = 0.8 / len(datos)
    for i, d in enumerate(datos):
        valores = exactitud_por(d, "categoria", categorias)
        xs = [j + (i - (len(datos) - 1) / 2) * ancho for j in range(len(categorias))]
        ax.bar(xs, [v[0] for v in valores], ancho, yerr=[[v[1] for v in valores], [v[2] for v in valores]],
               capsize=3, label=d["solver"], color=COLORES[i % len(COLORES)])
    ax.set_xticks(range(len(categorias)), categorias)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Exactitud (IC 95 %)")
    ax.set_title("Exactitud por categoría")
    ax.legend(ncol=min(len(datos), 6), fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    creados.append(carpeta / "exactitud_categorias.png")
    fig.savefig(creados[-1], dpi=120)
    plt.close(fig)

    # 2) calibración: ¿la confianza declarada coincide con el acierto real?
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.plot([0, 1], [0, 1], "--", color="#888", label="calibración perfecta")
    for i, d in enumerate(datos):
        if d["solver"] in ("azar", "reglas"):  # su "confianza" es fija por construcción
            continue
        puntos = curva_calibracion(d)
        color = COLORES[i % len(COLORES)]
        ax.plot([p[0] for p in puntos], [p[1] for p in puntos], "-", color=color, alpha=0.5)
        ax.scatter([p[0] for p in puntos], [p[1] for p in puntos], s=[30 + 8 * p[2] for p in puntos],
                   color=color, label=d["solver"], alpha=0.85)
        for x, y, n in puntos:
            ax.annotate(str(n), (x, y), textcoords="offset points", xytext=(6, 6), fontsize=7, color=color)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Confianza declarada")
    ax.set_ylabel("Acierto real")
    ax.set_title("Calibración (tamaño = nº de respuestas)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    creados.append(carpeta / "calibracion.png")
    fig.savefig(creados[-1], dpi=120)
    plt.close(fig)

    # 3) exactitud por dificultad
    fig, ax = plt.subplots(figsize=(6, 4))
    for i, d in enumerate(datos):
        valores = exactitud_por(d, "dificultad", [1, 2, 3])
        ax.errorbar([1, 2, 3], [v[0] for v in valores], yerr=[[v[1] for v in valores], [v[2] for v in valores]],
                    marker="o", capsize=3, label=d["solver"], color=COLORES[i % len(COLORES)])
    ax.set_xticks([1, 2, 3], ["fácil", "media", "difícil"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Exactitud (IC 95 %)")
    ax.set_title("Exactitud por dificultad")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    creados.append(carpeta / "exactitud_dificultad.png")
    fig.savefig(creados[-1], dpi=120)
    plt.close(fig)
    return creados
