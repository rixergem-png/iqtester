"""Banco de preguntas tipo test de CI con respuesta única garantizada.

Cada generador crea preguntas con una regla conocida y descarta las ambiguas
(las que admiten otra respuesta con alguna regla de `reglas.py`).
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from . import reglas

CATEGORIAS = ("series", "letras", "matrices", "analogias", "logica", "espacial")
ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LETRAS_OPCION = "ABCDE"


@dataclass(frozen=True)
class Pregunta:
    id: str
    categoria: str
    dificultad: int  # 1 fácil · 2 media · 3 difícil
    enunciado: str
    opciones: tuple[str, ...]
    correcta: int  # índice dentro de opciones
    explicacion: str
    split: str = "dev"

    @property
    def respuesta(self) -> str:
        return self.opciones[self.correcta]

    def a_dict(self) -> dict:
        d = asdict(self)
        d["opciones"] = list(self.opciones)
        return d

    @classmethod
    def desde_dict(cls, d: dict) -> "Pregunta":
        return cls(**{**d, "opciones": tuple(d["opciones"])})


def split_de(id_: str, fraccion_test: float = 0.3) -> str:
    """Asignación estable a dev/test según el hash del id (no depende del orden)."""
    return "test" if int(hashlib.sha256(id_.encode()).hexdigest()[:8], 16) % 100 < fraccion_test * 100 else "dev"


def _opciones(rng: random.Random, correcta: str, distractores: list[str], n: int = 4) -> tuple[tuple[str, ...], int]:
    unicos = list(dict.fromkeys(d for d in distractores if d != correcta))
    if len(unicos) < n - 1:
        raise ValueError("No hay suficientes distractores distintos")
    elegidas = rng.sample(unicos, n - 1) + [correcta]
    rng.shuffle(elegidas)
    return tuple(elegidas), elegidas.index(correcta)


def _distractores_numericos(rng: random.Random, correcta: int, extra: list[int]) -> list[str]:
    cerca = [correcta + d for d in (-2, -1, 1, 2, 3, -3)]
    return [str(v) for v in extra + rng.sample(cerca, len(cerca))]


# ---------------------------------------------------------------- generadores


def _serie(rng: random.Random) -> tuple[int, str, list[int], int, str]:
    tipo = rng.choice(["aritmetica", "geometrica", "cuadratica", "fibonacci", "intercalada"])
    if tipo == "aritmetica":
        a, d = rng.randint(1, 30), rng.choice([x for x in range(-9, 13) if x != 0])
        xs = [a + d * i for i in range(6)]
        return 1, f"aritmética: se suma {d}", xs[:5], xs[5], tipo
    if tipo == "geometrica":
        a, r = rng.randint(1, 5), rng.randint(2, 4)
        xs = [a * r**i for i in range(6)]
        return 1, f"geométrica: se multiplica por {r}", xs[:5], xs[5], tipo
    if tipo == "cuadratica":
        a, d, k = rng.randint(1, 10), rng.randint(1, 5), rng.randint(1, 4)
        xs = [a + d * i + k * i * (i - 1) // 2 for i in range(6)]
        return 2, f"las diferencias crecen de {k} en {k}", xs[:5], xs[5], tipo
    if tipo == "fibonacci":
        xs = [rng.randint(1, 9), rng.randint(1, 9)]
        while len(xs) < 7:
            xs.append(xs[-1] + xs[-2])
        return 2, "cada término es la suma de los dos anteriores", xs[:6], xs[6], tipo
    a, d1, b, d2 = rng.randint(1, 20), rng.randint(1, 6), rng.randint(20, 60), rng.choice([-5, -4, -3, 3, 4, 5])
    xs = [a + d1 * (i // 2) if i % 2 == 0 else b + d2 * (i // 2) for i in range(8)]
    return 3, f"dos series intercaladas: posiciones impares {d1:+}, pares {d2:+}", xs[:7], xs[7], tipo


def generar_series(rng: random.Random, i: int) -> Pregunta:
    while True:
        dif, regla, xs, sig, _ = _serie(rng)
        if reglas.predecir_serie(xs) == {sig}:
            break
    opciones, correcta = _opciones(rng, str(sig), _distractores_numericos(rng, sig, [xs[-1] * 2, sig + xs[-1] - xs[-2]]))
    enunciado = f"Serie: {', '.join(map(str, xs))}, ?\n¿Qué número sigue?"
    return Pregunta(f"series-{i:03d}", "series", dif, enunciado, opciones, correcta, f"Serie {regla}.")


def generar_letras(rng: random.Random, i: int) -> Pregunta:
    while True:
        tipo = rng.choice(["aritmetica", "creciente", "intercalada"])
        if tipo == "aritmetica":
            d = rng.randint(1, 4)
            idx = [rng.randint(0, 25 - 5 * d) + d * k for k in range(6)]
            dif, regla, mostrados = 1, f"se avanza {d} letra(s)", 5
        elif tipo == "creciente":
            a = rng.randint(0, 5)
            idx = [a + k * (k + 1) // 2 for k in range(6)]
            dif, regla, mostrados = 2, "los saltos crecen: +1, +2, +3…", 5
        else:
            a, b = rng.randint(0, 6), rng.randint(12, 18)
            idx = [a + 2 * (k // 2) if k % 2 == 0 else b + (k // 2) for k in range(8)]
            dif, regla, mostrados = 3, "dos series intercaladas", 7
        if max(idx) <= 25 and reglas.predecir_serie(idx[:mostrados]) == {idx[mostrados]}:
            break
    serie = [ALFABETO[j] for j in idx[: mostrados + 1]]
    sig = serie[-1]
    cerca = [ALFABETO[j] for j in {idx[mostrados] + d for d in (-2, -1, 1, 2)} if 0 <= j <= 25]
    opciones, correcta = _opciones(rng, sig, cerca + [serie[-2]] + list(rng.sample(ALFABETO, 4)))
    enunciado = f"Serie: {', '.join(serie[:-1])}, ?\n¿Qué letra sigue?"
    return Pregunta(f"letras-{i:03d}", "letras", dif, enunciado, opciones, correcta, f"En el alfabeto, {regla}.")


def generar_matrices(rng: random.Random, i: int) -> Pregunta:
    while True:
        regla = rng.choice(["suma", "resta", "producto", "progresion", "suma_constante"])
        if regla == "suma_constante":
            total = rng.randint(12, 30)
            filas = []
            for _ in range(3):
                a, b = rng.randint(1, total // 2), rng.randint(1, total // 2)
                filas.append([a, b, total - a - b])
            texto, dif = f"todas las filas suman {total}", 2
        else:
            f = reglas.REGLAS_FILA[regla]
            maximo = 9 if regla == "producto" else 20
            filas = [[a, b, f(a, b)] for a, b in ((rng.randint(2, maximo), rng.randint(1, maximo)) for _ in range(3))]
            texto = {"suma": "tercera = primera + segunda", "resta": "tercera = primera − segunda",
                     "producto": "tercera = primera × segunda", "progresion": "cada fila es una progresión aritmética"}[regla]
            dif = 1 if regla in ("suma", "resta") else 2
        if reglas.predecir_matriz(filas) == {filas[2][2]}:
            break
    sig = filas[2][2]
    opciones, correcta = _opciones(rng, str(sig), _distractores_numericos(rng, sig, [filas[2][0] + filas[2][1], filas[1][2]]))
    cuerpo = "\n".join(" ".join(f"{v:>4}" for v in fila) for fila in filas[:2])
    cuerpo += "\n" + f"{filas[2][0]:>4} {filas[2][1]:>4}    ?"
    enunciado = f"Completa la matriz (todas las filas siguen la misma regla):\n{cuerpo}"
    return Pregunta(f"matrices-{i:03d}", "matrices", dif, enunciado, opciones, correcta, f"Regla por filas: {texto}.")


def generar_analogias(rng: random.Random, i: int) -> Pregunta:
    while True:
        tipo = rng.choice(["lineal", "cuadrado", "cubo"])
        xs = rng.sample(range(2, 10), 4)
        if tipo == "lineal":
            a, b = rng.randint(2, 4), rng.randint(-3, 5)
            f, texto, dif = (lambda x, a=a, b=b: a * x + b), f"y = {a}·x {b:+}", 1 if b == 0 else 2
        elif tipo == "cuadrado":
            k = rng.randint(-2, 3)
            f, texto, dif = (lambda x, k=k: x * x + k), f"y = x² {k:+}", 2
        else:
            xs = rng.sample(range(2, 6), 4)
            f, texto, dif = (lambda x: x**3), "y = x³", 3
        pares = [(x, f(x)) for x in xs[:3]]
        if reglas.predecir_analogia(pares, xs[3]) == {f(xs[3])}:
            break
    sig = f(xs[3])
    opciones, correcta = _opciones(rng, str(sig), _distractores_numericos(rng, sig, [xs[3] * 2, xs[3] ** 2, sig + xs[3]]))
    enunciado = "Cada número se transforma con la misma regla:\n" + ", ".join(f"{x} → {y}" for x, y in pares) + f", {xs[3]} → ?"
    return Pregunta(f"analogias-{i:03d}", "analogias", dif, enunciado, opciones, correcta, f"Regla: {texto}.")


NOMBRES = ("zorbo", "flime", "drupo", "valko", "crisle", "mupo", "tarbe", "quelo")
PLANTILLAS = {
    "todos": "Todos los {xp} son {yp}",
    "algunos": "Algunos {xp} son {yp}",
    "ningun": "Ningún {x} es {y}",
    "algunos_no": "Algunos {xp} no son {yp}",
}


def frase(forma: str, x: str, y: str) -> str:
    return PLANTILLAS[forma].format(x=x, y=y, xp=x + "s", yp=y + "s")


def generar_logica(rng: random.Random, i: int) -> Pregunta:
    objetivo = (reglas.SI, reglas.NO, reglas.NO_SE)[i % 3]  # respuestas equilibradas
    while True:
        a, b, c = rng.sample(NOMBRES, 3)
        premisas = [(rng.choice(reglas.FORMAS), a, b), (rng.choice(reglas.FORMAS), b, c)]
        conclusion = (rng.choice(reglas.FORMAS), a, c)
        try:
            respuesta = reglas.evaluar_silogismo(premisas, conclusion)
        except ValueError:
            continue
        if respuesta == objetivo:
            break
    opciones = (reglas.SI, reglas.NO, reglas.NO_SE)
    enunciado = (f"Premisas: {frase(*premisas[0])}. {frase(*premisas[1])}.\n"
                 f"Si las premisas son ciertas y existe al menos un {a}, un {b} y un {c}, "
                 f"¿se cumple que «{frase(*conclusion)}»?")
    return Pregunta(f"logica-{i:03d}", "logica", 2 if objetivo == reglas.SI else 3, enunciado, opciones,
                    opciones.index(respuesta), "Comprobado en todos los mundos posibles que cumplen las premisas.")


def generar_espacial(rng: random.Random, i: int) -> Pregunta:
    inicio = rng.choice(reglas.DIRECCIONES)
    giros = [(rng.choice([90, 180, 270]), rng.choice(["derecha", "izquierda"])) for _ in range(rng.randint(2, 4))]
    final = reglas.girar(inicio, giros)
    textos = [f"{g}° a la {lado}" for g, lado in giros]
    enunciado = (f"Miras hacia el {inicio}. Giras {', después '.join(textos)}.\n¿Hacia dónde miras ahora?")
    opciones = tuple(rng.sample(reglas.DIRECCIONES, 4))
    return Pregunta(f"espacial-{i:03d}", "espacial", len(giros) - 1, enunciado, opciones, opciones.index(final),
                    "Cada 90° a la derecha avanza un punto cardinal en sentido horario.")


GENERADORES = {
    "series": generar_series,
    "letras": generar_letras,
    "matrices": generar_matrices,
    "analogias": generar_analogias,
    "logica": generar_logica,
    "espacial": generar_espacial,
}


def generar_banco(por_categoria: int = 30, semilla: int = 2026, manuales: Path | None = None) -> list[Pregunta]:
    rng = random.Random(semilla)
    banco = [GENERADORES[c](rng, i) for c in CATEGORIAS for i in range(por_categoria)]
    if manuales:
        banco += [Pregunta.desde_dict(d) for d in json.loads(manuales.read_text(encoding="utf-8"))]
    return [Pregunta(**{**p.a_dict(), "opciones": p.opciones, "split": split_de(p.id)}) for p in banco]


def guardar(banco: list[Pregunta], ruta: Path, semilla: int) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    datos = {"version": 1, "semilla": semilla, "preguntas": [p.a_dict() for p in banco]}
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def cargar(ruta: Path, split: str | None = None) -> list[Pregunta]:
    preguntas = [Pregunta.desde_dict(d) for d in json.loads(ruta.read_text(encoding="utf-8"))["preguntas"]]
    return [p for p in preguntas if split in (None, p.split)]
