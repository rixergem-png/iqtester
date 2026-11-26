"""Evaluación de un solver sobre el banco: resultados, resumen por categoría, umbrales e informe."""

from __future__ import annotations

from dataclasses import dataclass

from .metricas import ece, percentil, wilson
from .preguntas import CATEGORIAS, Pregunta
from .solvers import Solver


@dataclass(frozen=True)
class Resultado:
    pregunta: Pregunta
    indice: int | None
    confianza: float
    latencia: float

    @property
    def respondida(self) -> bool:
        return self.indice is not None

    @property
    def acierto(self) -> bool:
        return self.indice == self.pregunta.correcta


def evaluar(solver: Solver, preguntas: list[Pregunta]) -> list[Resultado]:
    resultados = []
    for p in preguntas:
        r = solver.responder(p)
        resultados.append(Resultado(p, r.indice, r.confianza, r.latencia))
    return resultados


def estadisticas(rs: list[Resultado]) -> dict[str, float]:
    n = len(rs)
    respondidas = [r for r in rs if r.respondida]
    aciertos = sum(r.acierto for r in rs)
    bajo, alto = wilson(aciertos, n)
    latencias = [r.latencia for r in rs]
    return {
        "n": n,
        "respondidas": len(respondidas),
        "aciertos": aciertos,
        "exactitud": aciertos / n if n else 0.0,  # sobre todas (abstenerse cuenta como fallo)
        "ic95_bajo": bajo,
        "ic95_alto": alto,
        "cobertura": len(respondidas) / n if n else 0.0,
        "precision": aciertos / len(respondidas) if respondidas else 0.0,  # sobre las respondidas
        "ece": ece([r.confianza for r in respondidas], [r.acierto for r in respondidas]),
        "p50_s": percentil(latencias, 0.5),
        "p95_s": percentil(latencias, 0.95),
    }


def resumen(resultados: list[Resultado]) -> dict[str, dict[str, float]]:
    categorias = [c for c in (*CATEGORIAS, "verbal") if any(r.pregunta.categoria == c for r in resultados)]
    salida = {"global": estadisticas(resultados)}
    for c in categorias:
        salida[c] = estadisticas([r for r in resultados if r.pregunta.categoria == c])
    return salida


def comprobar_umbrales(stats: dict[str, float], umbrales: dict[str, float]) -> list[str]:
    """Devuelve los umbrales incumplidos. Claves: <métrica>_min o <métrica>_max."""
    fallos = []
    for clave, limite in umbrales.items():
        metrica, tipo = clave.rsplit("_", 1)
        valor = stats[metrica]
        if (tipo == "min" and valor < limite) or (tipo == "max" and valor > limite):
            fallos.append(f"{metrica} = {valor:.3f} ({'mínimo' if tipo == 'min' else 'máximo'} {limite})")
    return fallos


def tabla_markdown(nombre: str, res: dict[str, dict[str, float]]) -> str:
    filas = [f"### {nombre}", "",
             "| Categoría | n | Exactitud (IC 95 %) | Cobertura | Precisión | ECE | p50 s | p95 s |",
             "|---|---:|---|---:|---:|---:|---:|---:|"]
    for cat, s in res.items():
        filas.append(
            f"| {cat} | {s['n']} | {s['exactitud']:.0%} ({s['ic95_bajo']:.0%}–{s['ic95_alto']:.0%}) | "
            f"{s['cobertura']:.0%} | {s['precision']:.0%} | {s['ece']:.2f} | {s['p50_s']:.3f} | {s['p95_s']:.3f} |")
    return "\n".join(filas)


def por_dificultad(resultados: list[Resultado]) -> dict[str, dict[str, float]]:
    niveles = sorted({r.pregunta.dificultad for r in resultados})
    return {f"dificultad {d}": estadisticas([r for r in resultados if r.pregunta.dificultad == d]) for d in niveles}


def a_json(solver: str, resultados: list[Resultado]) -> dict:
    """Resultados pregunta a pregunta: base para el análisis de errores, los gráficos y la web."""
    return {"solver": solver, "resultados": [
        {"id": r.pregunta.id, "categoria": r.pregunta.categoria, "dificultad": r.pregunta.dificultad,
         "elegida": r.indice, "correcta": r.pregunta.correcta, "confianza": round(r.confianza, 4),
         "latencia": round(r.latencia, 4)} for r in resultados]}


def errores(datos: dict, preguntas: dict[str, Pregunta]) -> str:
    """Lista los fallos agrupados por categoría, con lo que eligió y lo correcto."""
    lineas, por_cat = [f"Errores de {datos['solver']}:"], {}
    for r in datos["resultados"]:
        if r["elegida"] != r["correcta"]:
            por_cat.setdefault(r["categoria"], []).append(r)
    if not por_cat:
        return lineas[0] + " ninguno."
    for cat, rs in por_cat.items():
        lineas.append(f"\n## {cat} ({len(rs)} fallos)")
        for r in rs:
            p = preguntas[r["id"]]
            elegida = "se abstuvo" if r["elegida"] is None else f"eligió «{p.opciones[r['elegida']]}» ({r['confianza']:.0%})"
            lineas.append(f"- {r['id']} (dificultad {r['dificultad']}): {elegida}; correcta «{p.respuesta}». {p.explicacion}")
    return "\n".join(lineas)


def comprobar_regresion(actual: dict[str, float], baseline: dict[str, float], tolerancia: float = 0.02) -> list[str]:
    """Falla si la exactitud de un solver cae más de `tolerancia` respecto al baseline guardado."""
    return [f"{s}: exactitud {actual[s]:.3f} < baseline {b:.3f} − {tolerancia}"
            for s, b in baseline.items() if s in actual and actual[s] < b - tolerancia]
