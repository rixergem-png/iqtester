"""Resolvedores: reciben una pregunta y eligen una opción (o se abstienen).

- SolverAzar:     base mínima. Cualquier sistema debe superarla con claridad.
- SolverReglas:   lee el enunciado y aplica los motores de `reglas.py`. Si no reconoce el tipo, se abstiene.
- SolverSimulado: imita a un LLM con aciertos y confianzas aleatorias. SOLO para probar el pipeline:
                  sus números no son resultados de ningún modelo real.
- SolverClaude:   pregunta a Claude con salida estructurada (letra + confianza).
"""

from __future__ import annotations

import os
import random
import re
import time
from dataclasses import dataclass
from typing import Protocol

from . import reglas
from .preguntas import ALFABETO, LETRAS_OPCION, Pregunta


@dataclass(frozen=True)
class Respuesta:
    indice: int | None  # None = se abstiene
    confianza: float  # 0..1
    latencia: float  # segundos


class Solver(Protocol):
    nombre: str

    def responder(self, p: Pregunta) -> Respuesta: ...


class SolverAzar:
    nombre = "azar"

    def __init__(self, semilla: int = 0):
        self.rng = random.Random(semilla)

    def responder(self, p: Pregunta) -> Respuesta:
        return Respuesta(self.rng.randrange(len(p.opciones)), 1 / len(p.opciones), 0.0)


# ---------------------------------------------------------------- lectura de enunciados

def _linea_serie(texto: str) -> str:
    return texto.split("\n")[0].removeprefix("Serie:").removesuffix("?")


def _leer_silogismo(texto: str) -> tuple[list[tuple[str, str, str]], tuple[str, str, str]]:
    patrones = [  # el orden importa: "no son" antes que "son"
        ("algunos_no", r"Algunos (\w+)s no son (\w+)s"),
        ("todos", r"Todos los (\w+)s son (\w+)s"),
        ("algunos", r"Algunos (\w+)s son (\w+)s"),
        ("ningun", r"Ningún (\w+) es (\w+)"),
    ]

    def leer(frase: str) -> tuple[str, str, str]:
        for forma, patron in patrones:
            if m := re.fullmatch(patron, frase.strip()):
                return forma, m.group(1), m.group(2)
        raise ValueError(f"Frase no reconocida: {frase!r}")

    linea_premisas = texto.split("\n")[0].removeprefix("Premisas: ")
    premisas = [leer(f) for f in linea_premisas.split(".") if f.strip()]
    conclusion = leer(re.search(r"«(.+)»", texto).group(1))
    return premisas, conclusion


def candidatos(p: Pregunta) -> set[str]:
    """Respuestas (como texto) que dan las reglas conocidas para esta pregunta."""
    t = p.enunciado
    if p.categoria == "series":
        return {str(v) for v in reglas.predecir_serie([int(x) for x in re.findall(r"-?\d+", _linea_serie(t))])}
    if p.categoria == "letras":
        idx = [ALFABETO.index(x) for x in re.findall(r"[A-Z]", _linea_serie(t))]
        return {ALFABETO[v] for v in reglas.predecir_serie(idx) if 0 <= v < len(ALFABETO)}
    if p.categoria == "matrices":
        filas = [[int(x) for x in re.findall(r"-?\d+", linea)] for linea in t.split("\n")[1:4]]
        return {str(v) for v in reglas.predecir_matriz(filas)}
    if p.categoria == "analogias":
        pares = [(int(a), int(b)) for a, b in re.findall(r"(-?\d+) → (-?\d+)", t)]
        x = int(re.search(r"(-?\d+) → \?", t).group(1))
        return {str(v) for v in reglas.predecir_analogia(pares, x)}
    if p.categoria == "logica":
        return {reglas.evaluar_silogismo(*_leer_silogismo(t))}
    if p.categoria == "espacial":
        inicio = re.search(r"Miras hacia el (\w+)", t).group(1)
        giros = [(int(g), lado) for g, lado in re.findall(r"(\d+)° a la (derecha|izquierda)", t)]
        return {reglas.girar(inicio, giros)}
    return set()  # categoría que las reglas no saben resolver (p. ej. verbal)


class SolverReglas:
    nombre = "reglas"

    def responder(self, p: Pregunta) -> Respuesta:
        inicio = time.perf_counter()
        try:
            posibles = candidatos(p)
        except (ValueError, AttributeError):
            posibles = set()
        indice = p.opciones.index(next(iter(posibles))) if len(posibles) == 1 and posibles <= set(p.opciones) else None
        return Respuesta(indice, 1.0 if indice is not None else 0.0, time.perf_counter() - inicio)


class SolverSimulado:
    """Imita un LLM: acierta con cierta probabilidad por categoría. NO es un modelo real."""

    nombre = "simulado"
    PROB_ACIERTO = {"series": 0.85, "letras": 0.75, "matrices": 0.7, "analogias": 0.8,
                    "logica": 0.65, "espacial": 0.9, "verbal": 0.95}

    def __init__(self, semilla: int = 7):
        self.rng = random.Random(semilla)

    def responder(self, p: Pregunta) -> Respuesta:
        acierta = self.rng.random() < self.PROB_ACIERTO.get(p.categoria, 0.5)
        incorrectas = [i for i in range(len(p.opciones)) if i != p.correcta]
        indice = p.correcta if acierta else self.rng.choice(incorrectas)
        confianza = min(1.0, max(0.0, self.rng.gauss(0.85 if acierta else 0.65, 0.1)))
        return Respuesta(indice, round(confianza, 3), round(self.rng.lognormvariate(1.0, 0.4), 3))


INSTRUCCIONES = """Resuelves preguntas de razonamiento tipo test de CI.
Elige exactamente una opción por su letra e indica tu confianza entre 0 y 1
(la probabilidad de que tu respuesta sea correcta)."""


class SolverClaude:
    """Necesita ANTHROPIC_API_KEY (o `ant auth login`). Cada pregunta es una llamada facturada."""

    def __init__(self, modelo: str | None = None):
        import anthropic
        from pydantic import BaseModel, Field

        class Eleccion(BaseModel):
            letra: str = Field(description="Letra de la opción elegida: A, B, C…")
            confianza: float = Field(ge=0, le=1)

        self._esquema = Eleccion
        self.cliente = anthropic.Anthropic()
        self.modelo = modelo or os.getenv("IQ_MODELO", "claude-opus-5-5")
        self.esfuerzo = os.getenv("IQ_ESFUERZO", "medium")
        self.nombre = f"claude:{self.modelo}"

    def responder(self, p: Pregunta) -> Respuesta:
        opciones = "\n".join(f"{LETRAS_OPCION[i]}) {o}" for i, o in enumerate(p.opciones))
        inicio = time.perf_counter()
        r = self.cliente.beta.messages.parse(
            model=self.modelo,
            max_tokens=16000,
            system=INSTRUCCIONES,
            messages=[{"role": "user", "content": f"{p.enunciado}\n\nOpciones:\n{opciones}"}],
            output_format=self._esquema,
            output_config={"effort": self.esfuerzo},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        latencia = time.perf_counter() - inicio
        eleccion = r.parsed_output
        if r.stop_reason == "refusal" or eleccion is None:
            return Respuesta(None, 0.0, latencia)
        letra = eleccion.letra.strip().upper()[:1]
        indice = LETRAS_OPCION.index(letra) if letra and letra in LETRAS_OPCION[: len(p.opciones)] else None
        return Respuesta(indice, eleccion.confianza if indice is not None else 0.0, latencia)


class SolverOllama:
    """Modelo local vía la API HTTP de Ollama (gratis, sin enviar datos fuera del equipo).

    Usa salida estructurada (`format` con esquema JSON), temperatura 0 y semilla fija.
    """

    URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

    def __init__(self, modelo: str, timeout: float = 300):
        self.modelo, self.timeout = modelo, timeout
        self.nombre = f"ollama:{modelo}"

    def _llamar(self, cuerpo: dict) -> dict:
        import json
        import urllib.request

        peticion = urllib.request.Request(f"{self.URL}/api/chat", data=json.dumps(cuerpo).encode(),
                                          headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(peticion, timeout=self.timeout) as r:
            return json.load(r)

    def responder(self, p: Pregunta) -> Respuesta:
        import json

        letras = list(LETRAS_OPCION[: len(p.opciones)])
        opciones = "\n".join(f"{letras[i]}) {o}" for i, o in enumerate(p.opciones))
        esquema = {"type": "object", "required": ["letra", "confianza"],
                   "properties": {"letra": {"type": "string", "enum": letras},
                                  "confianza": {"type": "number", "minimum": 0, "maximum": 1}}}
        cuerpo = {"model": self.modelo, "stream": False, "format": esquema,
                  "options": {"temperature": 0, "seed": 0, "num_ctx": 2048},
                  "messages": [{"role": "system", "content": INSTRUCCIONES},
                               {"role": "user", "content": f"{p.enunciado}\n\nOpciones:\n{opciones}\n\n"
                                                           "Responde en JSON con 'letra' y 'confianza'."}]}
        inicio = time.perf_counter()
        r = self._llamar(cuerpo)
        latencia = time.perf_counter() - inicio
        try:
            datos = json.loads(r["message"]["content"])
            letra = str(datos["letra"]).strip().upper()[:1]
            confianza = min(1.0, max(0.0, float(datos["confianza"])))
        except (KeyError, ValueError, TypeError):
            return Respuesta(None, 0.0, latencia)  # salida inválida: se cuenta como abstención
        if letra not in letras:
            return Respuesta(None, 0.0, latencia)
        return Respuesta(letras.index(letra), confianza, latencia)


def crear(nombre: str) -> Solver:
    if nombre.startswith("ollama:"):
        return SolverOllama(nombre.removeprefix("ollama:"))
    if nombre == "azar":
        return SolverAzar()
    if nombre == "reglas":
        return SolverReglas()
    if nombre == "simulado":
        return SolverSimulado()
    if nombre == "claude":
        return SolverClaude()
    raise ValueError(f"Solver desconocido: {nombre}")
