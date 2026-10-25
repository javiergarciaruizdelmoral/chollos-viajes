"""Agente tasador: puntúa cada precio de 0 a 100, como la etiqueta de precio de
un portal de coches, y explica de dónde sale cada punto.

Criterios (máximo de puntos):
  Descuento    45  cuánto más barato es que el precio típico de esa ruta y fechas
  Rango        30  dónde cae dentro del rango de precios habitual (bajo el rango = máximo)
  Mínimo 60d   15  si iguala o mejora el precio más bajo de los últimos 60 días
  Vuelo        10  directo / pocas escalas (en vuelos largos se exige menos)

Ejemplos: Roma a 72 € (típico 148 €, habitual 105-240 €, directo) = 85, excelente.
Palma a 37 € (típico 37 €, directo) = 25, normal.

El precio típico, el rango y el mínimo de 60 días los calcula Google Flights
para cada búsqueda concreta. Si no los da, se usa el precio de referencia del
destino (config.py) con un rango aproximado.
"""

VALORACIONES = [  # (puntuación mínima, clave, texto)
    (80, "excelente", "Precio excelente"),
    (65, "muy_bueno", "Muy buen precio"),
    (45, "bueno", "Buen precio"),
    (20, "normal", "Precio normal"),
    (0, "caro", "Precio alto"),
]


def valoracion(puntuacion):
    for minimo, clave, _ in VALORACIONES:
        if puntuacion >= minimo:
            return clave


def referencias(r):
    """Precio típico, rango y mínimo de 60 días con los que comparar, y de dónde salen."""
    if r.get("google_tipico") and r.get("google_rango"):
        bajo, alto = r["google_rango"]
        return r["google_tipico"], bajo, alto, r.get("google_min_60d"), "google"
    tipico = r["precio_ref"]
    return tipico, round(tipico * 0.85), round(tipico * 1.25), None, "referencia"


def puntuar(r, largo_radio=False):
    """Devuelve (puntuación 0-100, desglose por criterio, referencias usadas)."""
    precio = r["precio_persona"]
    tipico, bajo, alto, min60, base = referencias(r)

    ahorro_pct = (tipico - precio) / tipico * 100
    # 40 % o más de descuento = puntuación máxima en este criterio
    descuento = round(max(0.0, min(45.0, ahorro_pct * 45 / 40)))

    if precio < bajo:
        # bajo el rango: 22 puntos de entrada y hasta 8 más según lo lejos que quede
        rango = round(22 + min(8.0, (bajo - precio) / bajo * 100 * 0.8))
    elif precio <= tipico:
        rango = round(15 + 7 * (tipico - precio) / max(1, tipico - bajo))
    elif precio <= alto:
        rango = round(15 * (alto - precio) / max(1, alto - tipico))
    else:
        rango = 0

    if min60 and precio <= min60:
        minimo = 15
    elif min60 and precio <= min60 * 1.05:
        minimo = 8
    else:
        minimo = 0

    escalas = r.get("escalas", 0)
    if largo_radio:
        vuelo = {0: 10, 1: 8, 2: 3}.get(escalas, 0)
    else:
        vuelo = {0: 10, 1: 3}.get(escalas, 0)

    desglose = {"descuento": descuento, "rango": rango, "minimo_60d": minimo, "vuelo": vuelo}
    refs = {
        "tipico": round(tipico), "rango_bajo": round(bajo), "rango_alto": round(alto),
        "min60": min60, "base_comparacion": base, "ahorro_pct": round(ahorro_pct),
    }
    return sum(desglose.values()), desglose, refs
