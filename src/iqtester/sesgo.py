"""Prueba de sesgo de posición: la misma pregunta con las opciones rotadas.

Si un sistema razona sobre el contenido, debe elegir la MISMA respuesta (el mismo texto)
en todas las rotaciones. Si cambia al mover las opciones, responde en parte por la posición.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from .preguntas import LETRAS_OPCION, Pregunta
from .solvers import Solver


def rotar(p: Pregunta, k: int) -> Pregunta:
    """Desplaza las opciones k posiciones; la respuesta correcta sigue siendo el mismo texto."""
    n = len(p.opciones)
    k %= n
    opciones = p.opciones[-k:] + p.opciones[:-k] if k else p.opciones
    return replace(p, id=f"{p.id}@r{k}", opciones=opciones, correcta=(p.correcta + k) % n)


def medir(solver: Solver, preguntas: list[Pregunta], rotaciones: int = 4) -> dict:
    """Responde cada pregunta en `rotaciones` órdenes distintos y resume la consistencia."""
    filas, posiciones = [], Counter()
    for p in preguntas:
        textos, aciertos = [], []
        for k in range(min(rotaciones, len(p.opciones))):
            q = rotar(p, k)
            r = solver.responder(q)
            textos.append(None if r.indice is None else q.opciones[r.indice])
            aciertos.append(r.indice == q.correcta)
            if r.indice is not None:
                posiciones[LETRAS_OPCION[r.indice]] += 1
        filas.append({"id": p.id, "categoria": p.categoria, "respuestas": textos, "aciertos": aciertos,
                      "consistente": len(set(textos)) == 1 and textos[0] is not None})
    n = len(filas)
    total = sum(len(f["aciertos"]) for f in filas)
    return {
        "solver": solver.nombre,
        "preguntas": n,
        "consistencia": sum(f["consistente"] for f in filas) / n if n else 0.0,
        "exactitud_media": sum(sum(f["aciertos"]) for f in filas) / total if total else 0.0,
        "siempre_bien": sum(all(f["aciertos"]) for f in filas) / n if n else 0.0,
        "posiciones": dict(sorted(posiciones.items())),
        "filas": filas,
    }
