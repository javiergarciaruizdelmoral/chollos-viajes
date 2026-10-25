"""Diagnóstico rápido del explorador: unas pocas búsquedas sin tocar la base de datos,
probando variantes de la petición a Google Flights.

    python diagnostico.py
"""

import time
from datetime import date, timedelta

from fast_flights import FlightQuery, Passengers, create_query
from fast_flights.parser import parse_js
from primp import Client
from selectolax.lexbor import LexborHTMLParser

from agentes import vuelos

PRUEBAS = [("FCO", 47, 3), ("DUB", 32, 3), ("SVQ", 39, 3), ("BKK", 261, 15)]

VARIANTES = {
    "google.com": dict(url="https://www.google.com/travel/flights", headers={}),
    "google.es + es-ES": dict(
        url="https://www.google.es/travel/flights",
        headers={"Accept-Language": "es-ES,es;q=0.9"},
    ),
}


def probar(nombre, url, headers):
    cliente = Client(impersonate="chrome_145", impersonate_os="windows", referer=True, cookie_store=True)
    print(f"--- {nombre}")
    for destino, dias, noches in PRUEBAS:
        ida = date.today() + timedelta(days=dias)
        q = create_query(
            flights=[FlightQuery(date=ida.isoformat(), from_airport="MAD", to_airport=destino),
                     FlightQuery(date=(ida + timedelta(days=noches)).isoformat(), from_airport=destino, to_airport="MAD")],
            trip="round-trip", passengers=Passengers(adults=1), language="es", currency="EUR", max_stops=2,
        )
        res = cliente.get(url, params={**q.params(), "gl": "es"}, headers=headers, cookies=vuelos.COOKIES)
        try:
            js = LexborHTMLParser(res.text).css_first(r"script.ds\:1").text()
            precios = sorted(v.price for v in parse_js(js) if v.price)
            print(f"OK  {destino} {ida}: {precios[0]} € ({len(precios)} vuelos)")
        except Exception:
            print(f"MAL {destino} {ida}: {vuelos.motivo_fallo(res)}")
        time.sleep(3)


for nombre, v in VARIANTES.items():
    probar(nombre, **v)

print("--- Ryanair")
from fuentes.ryanair import Ryanair  # noqa: E402

ry = Ryanair("MAD")
hoy = date.today()
try:
    tarifas = ry.tarifas(hoy + timedelta(days=30), hoy + timedelta(days=50), (3, 4), [3, 4])
    print(f"{'OK ' if tarifas else 'MAL'} {len(tarifas)} tarifas, {ry.consultas} consultas, {ry.errores} errores")
    for t in sorted(tarifas, key=lambda t: t["precio_persona"])[:5]:
        print(f"    {t['ciudad']} {t['ida']}: {t['precio_persona']} €")
except Exception as e:
    print(f"MAL Ryanair: {e}")
