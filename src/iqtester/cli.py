"""iqtester — banco de preguntas tipo test de CI y evaluación de resolvedores.

  python -m iqtester generar                       # crea datos/banco.json (reproducible)
  python -m iqtester evaluar --solver azar --solver reglas [--split test] [--umbrales umbrales.json]
  python -m iqtester jugar --n 10                  # haz tú el test en la terminal
  python -m iqtester errores docs/resultados/reglas.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from . import evaluar as ev
from .preguntas import LETRAS_OPCION, cargar, generar_banco, guardar
from .solvers import SolverAzar, SolverReglas, crear

RAIZ = Path(__file__).resolve().parents[2]
BANCO = RAIZ / "datos/banco.json"


def cmd_generar(args) -> int:
    banco = generar_banco(args.por_categoria, args.semilla, RAIZ / "datos/manuales.json")
    guardar(banco, args.salida, args.semilla)
    test = sum(p.split == "test" for p in banco)
    print(f"{len(banco)} preguntas guardadas en {args.salida} ({test} de test, {len(banco) - test} de dev)")
    return 0


def cmd_evaluar(args) -> int:
    preguntas = cargar(args.banco, args.split)
    if any(n == "claude" for n in args.solver) and len(preguntas) > args.max_ia:
        preguntas = random.Random(0).sample(preguntas, args.max_ia)  # control de gasto
        print(f"Con Claude se evalúa una muestra de {args.max_ia} preguntas.")
    umbrales = json.loads(args.umbrales.read_text(encoding="utf-8")) if args.umbrales else {}
    informe, fallos, exactitudes = [], [], {}
    for nombre in args.solver:
        resultados = ev.evaluar(crear(nombre), preguntas)
        res = ev.resumen(resultados)
        exactitudes[nombre] = res["global"]["exactitud"]
        tabla = ev.tabla_markdown(nombre, {**res, **ev.por_dificultad(resultados)})
        print(tabla + "\n")
        informe.append(tabla)
        fallos += [f"[{nombre}] {f}" for f in ev.comprobar_umbrales(res["global"], umbrales.get(nombre, {}))]
        if args.guardar:
            args.guardar.mkdir(parents=True, exist_ok=True)
            destino = args.guardar / f"{nombre.replace(':', '_').replace('/', '_')}.json"
            destino.write_text(json.dumps(ev.a_json(nombre, resultados), ensure_ascii=False, indent=1), encoding="utf-8")
    if args.baseline and args.baseline.exists():
        fallos += [f"[regresión] {f}" for f in ev.comprobar_regresion(
            exactitudes, json.loads(args.baseline.read_text(encoding="utf-8")), args.tolerancia)]
    if args.actualizar_baseline:
        args.actualizar_baseline.write_text(json.dumps(exactitudes, indent=1) + "\n", encoding="utf-8")
        print(f"Baseline guardado en {args.actualizar_baseline}")
    if args.informe:
        args.informe.parent.mkdir(parents=True, exist_ok=True)
        args.informe.write_text(f"# Resultados (split: {args.split or 'todo'}, n = {len(preguntas)})\n\n"
                                + "\n\n".join(informe) + "\n", encoding="utf-8")
    if fallos:
        print("UMBRALES INCUMPLIDOS:\n  " + "\n  ".join(fallos))
        return 1
    if umbrales:
        print("Todos los umbrales se cumplen.")
    return 0


def cmd_graficos(args) -> int:
    from .graficos import dibujar

    for ruta in dibujar(args.resultados, args.salida):
        print(f"Gráfico guardado en {ruta}")
    return 0


def cmd_informe(args) -> int:
    """Tablas Markdown a partir de resultados guardados (no hace falta volver a ejecutar los modelos)."""
    preguntas = {p.id: p for p in cargar(args.banco)}
    tablas = []
    for ruta in args.resultados:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        rs = [ev.Resultado(preguntas[r["id"]], r["elegida"], r["confianza"], r["latencia"]) for r in datos["resultados"]]
        tablas.append(ev.tabla_markdown(datos["solver"], {**ev.resumen(rs), **ev.por_dificultad(rs)}))
    texto = f"# Resultados por categoría y dificultad\n\n" + "\n\n".join(tablas) + "\n"
    args.salida.write_text(texto, encoding="utf-8")
    print(f"Informe de {len(tablas)} solvers en {args.salida}")
    return 0


def cmd_web(args) -> int:
    """Prepara docs/datos-web.json: preguntas de test + qué solver acertó cada una."""
    preguntas = cargar(args.banco, "test")
    solvers = {}
    for ruta in sorted(args.resultados.glob("*.json")):
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        solvers[datos["solver"]] = {r["id"]: r["elegida"] == r["correcta"] for r in datos["resultados"]}
    ids = {p.id for p in preguntas}
    solvers = {s: a for s, a in solvers.items() if ids <= set(a)}  # solo solvers evaluados en todo el test
    salida = {"preguntas": [{k: v for k, v in p.a_dict().items() if k != "split"} for p in preguntas],
              "solvers": solvers}
    args.salida.write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    print(f"{len(preguntas)} preguntas y {len(solvers)} solvers en {args.salida}")
    return 0


def cmd_errores(args) -> int:
    datos = json.loads(args.resultados.read_text(encoding="utf-8"))
    print(ev.errores(datos, {p.id: p for p in cargar(args.banco)}))
    return 0


def cmd_jugar(args, entrada=input) -> int:
    preguntas = random.Random(args.semilla).sample(cargar(args.banco), args.n)
    aciertos = 0
    for k, p in enumerate(preguntas, 1):
        print(f"\nPregunta {k}/{len(preguntas)} · {p.categoria}\n{p.enunciado}")
        for i, o in enumerate(p.opciones):
            print(f"  {LETRAS_OPCION[i]}) {o}")
        letra = entrada("Tu respuesta: ").strip().upper()[:1]
        if letra and LETRAS_OPCION.find(letra) == p.correcta:
            aciertos += 1
            print("✓ Correcto")
        else:
            print(f"✗ Era {LETRAS_OPCION[p.correcta]}) {p.respuesta}. {p.explicacion}")
    referencia = {s.nombre: ev.estadisticas(ev.evaluar(s, preguntas))["exactitud"] for s in (SolverAzar(), SolverReglas())}
    print(f"\nResultado: {aciertos}/{len(preguntas)} ({aciertos / len(preguntas):.0%})"
          f" · azar: {referencia['azar']:.0%} · reglas: {referencia['reglas']:.0%}")
    print("Esto es una práctica, no una medida de CI: un test de CI real está estandarizado con miles de personas.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="iqtester", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)

    g = sub.add_parser("generar", help="crear el banco de preguntas")
    g.add_argument("--por-categoria", type=int, default=30)
    g.add_argument("--semilla", type=int, default=2026)
    g.add_argument("--salida", type=Path, default=BANCO)

    e = sub.add_parser("evaluar", help="evaluar uno o varios solvers")
    e.add_argument("--solver", action="append", required=True,
                   help="azar | reglas | simulado | claude | ollama:<modelo> (se puede repetir)")
    e.add_argument("--banco", type=Path, default=BANCO)
    e.add_argument("--split", choices=["dev", "test"])
    e.add_argument("--umbrales", type=Path, help="JSON con umbrales por solver; si falla alguno, sale con código 1")
    e.add_argument("--informe", type=Path, help="guardar las tablas en Markdown")
    e.add_argument("--max-ia", type=int, default=40, help="máximo de preguntas con Claude (gasto)")
    e.add_argument("--guardar", type=Path, help="carpeta donde guardar los resultados pregunta a pregunta (JSON)")
    e.add_argument("--baseline", type=Path, help="JSON con la exactitud de referencia por solver (puerta de regresión)")
    e.add_argument("--tolerancia", type=float, default=0.02, help="caída máxima admitida frente al baseline")
    e.add_argument("--actualizar-baseline", type=Path, help="guardar la exactitud actual como nuevo baseline")

    gr = sub.add_parser("graficos", help="gráficos de exactitud, calibración y dificultad")
    gr.add_argument("resultados", type=Path, nargs="+")
    gr.add_argument("--salida", type=Path, default=RAIZ / "docs")

    inf = sub.add_parser("informe", help="tablas Markdown a partir de resultados guardados")
    inf.add_argument("resultados", type=Path, nargs="+")
    inf.add_argument("--salida", type=Path, default=RAIZ / "docs/resultados-test.md")
    inf.add_argument("--banco", type=Path, default=BANCO)

    w = sub.add_parser("web", help="preparar los datos de la página jugable (docs/index.html)")
    w.add_argument("--resultados", type=Path, default=RAIZ / "docs/resultados")
    w.add_argument("--salida", type=Path, default=RAIZ / "docs/datos-web.json")
    w.add_argument("--banco", type=Path, default=BANCO)

    r = sub.add_parser("errores", help="ver los fallos de un solver a partir de sus resultados guardados")
    r.add_argument("resultados", type=Path)
    r.add_argument("--banco", type=Path, default=BANCO)

    j = sub.add_parser("jugar", help="hacer el test tú mismo")
    j.add_argument("--n", type=int, default=10)
    j.add_argument("--semilla", type=int)
    j.add_argument("--banco", type=Path, default=BANCO)

    args = ap.parse_args(argv)
    return {"generar": cmd_generar, "evaluar": cmd_evaluar, "jugar": cmd_jugar, "errores": cmd_errores,
            "graficos": cmd_graficos, "web": cmd_web,
            "informe": cmd_informe}[args.comando](args)


if __name__ == "__main__":
    raise SystemExit(main())
