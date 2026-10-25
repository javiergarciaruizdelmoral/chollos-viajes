"""Agente explorador de vuelos: busca en Google Flights el precio por persona
para cada destino y perfil, rotando las fechas probadas cada día."""

import json
import time
from datetime import date, timedelta

from fast_flights import FlightQuery, Passengers, create_query
from fast_flights.exceptions import FlightsNotFound
from fast_flights.parser import parse_js
from primp import Client
from selectolax.lexbor import LexborHTMLParser

import config

URL = "https://www.google.com/travel/flights"
# Cookie de consentimiento aceptado: sin ella, desde la UE Google devuelve la página de cookies
COOKIES = {"SOCS": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg", "CONSENT": "YES+"}


def _cliente():
    return Client(impersonate="chrome_145", impersonate_os="macos", referer=True, cookie_store=True)


def fechas_candidatas(perfil, hoy):
    """Todas las fechas de salida posibles para un perfil."""
    if "rango_salida" in perfil:
        inicio, fin = (date.fromisoformat(d) for d in perfil["rango_salida"])
        inicio = max(inicio, hoy + timedelta(days=1))
        # una salida cada 3 días para cubrir el rango sin disparar búsquedas
        return [inicio + timedelta(days=i) for i in range(0, (fin - inicio).days + 1, 3)]
    return [
        d
        for d in (hoy + timedelta(days=i) for i in range(7, perfil["semanas_vista"] * 7))
        if d.weekday() in perfil["dias_salida"]
    ]


def fechas_de_hoy(candidatas, n, semilla):
    """Elige n fechas repartidas por el rango, desplazándose cada día para cubrirlo entero con el tiempo."""
    if not candidatas:
        return []
    paso = max(1, len(candidatas) // n)
    return sorted({candidatas[(semilla + i * paso) % len(candidatas)] for i in range(n)})


def buscar(cliente, destino, ida, vuelta, max_escalas):
    q = create_query(
        flights=[
            FlightQuery(date=ida.isoformat(), from_airport=config.ORIGEN, to_airport=destino),
            FlightQuery(date=vuelta.isoformat(), from_airport=destino, to_airport=config.ORIGEN),
        ],
        trip="round-trip",
        passengers=Passengers(adults=1),
        language="es",
        currency="EUR",
        max_stops=max_escalas,
    )
    # gl=es: buscar como desde España (si no, desde servidores de EE. UU. salen otras tarifas)
    res = cliente.get(URL, params={**q.params(), "gl": "es"}, cookies=COOKIES)
    try:
        js = LexborHTMLParser(res.text).css_first(r"script.ds\:1").text()
        vuelos = [v for v in parse_js(js) if v.price]
    except (FlightsNotFound, AttributeError, TypeError, IndexError):
        # la página no traía resultados: bloqueo, página de cookies o fechas aún sin tarifas
        buscar.ultimo_motivo = motivo_fallo(res)
        return None
    if not vuelos:
        buscar.ultimo_motivo = "sin vuelos para esas fechas"
        return None
    mejor = min(vuelos, key=lambda v: v.price)
    tramos = mejor.flights
    salida = tramos[0].departure
    return {
        "destino": destino,
        "ida": ida.isoformat(),
        "vuelta": vuelta.isoformat(),
        "precio_persona": mejor.price,
        "aerolineas": mejor.airlines,
        "escalas": len(tramos) - 1,
        "minutos_vuelo": sum(t.duration or 0 for t in tramos),
        "hora_salida": f"{salida.time[0]:02d}:{salida.time[1]:02d}",
        "enlace": q.url(),
        **valoracion_google(js),
    }


def motivo_fallo(res):
    """Describe por qué una respuesta de Google no traía vuelos, para el diagnóstico."""
    titulo = LexborHTMLParser(res.text).css_first("title")
    titulo = titulo.text() if titulo else ""
    if res.status_code != 200:
        return f"HTTP {res.status_code}"
    if "unusual traffic" in res.text or "/sorry/" in str(res.url):
        return "bloqueo de Google (captcha)"
    if "consent" in str(res.url) or "Antes de continuar" in titulo:
        return "página de cookies"
    return f"página sin datos de vuelos ({titulo[:60]!r})"


buscar.ultimo_motivo = None


def valoracion_google(js):
    """Extrae la valoración de precio que calcula Google Flights para esa búsqueda.

    En los datos de la página, el bloque 5 es:
      [nivel, [_, precio_actual], [_, precio_tipico], [_, diferencia], [_, rango_bajo], [_, rango_alto], ...,
       (posición 10) [[[timestamp_ms, precio], ...]] = historial de los últimos ~60 días]
    """
    try:
        bloque = json.loads(js.split("data:", 1)[1].rsplit(",", 1)[0])[5]
        historial = [precio for _, precio in (bloque[10][0] if len(bloque) > 10 and bloque[10] else [])]
        return {
            "google_tipico": bloque[2][1],
            "google_rango": [bloque[4][1], bloque[5][1]],
            "google_min_60d": min(historial) if historial else None,
        }
    except (IndexError, TypeError, ValueError):
        return {}


class Buscador:
    """Lanza búsquedas con pausas y un reintento, y lleva la cuenta para el vigilante."""

    def __init__(self, log=print):
        self.cliente = _cliente()
        self.log = log
        self.busquedas = self.resultados = self.errores = 0

    def buscar(self, perfil_clave, destino, ida, vuelta):
        perfil = config.PERFILES[perfil_clave]
        ciudad, precio_ref = perfil["destinos"][destino]
        for intento in (1, 2):
            self.busquedas += 1
            try:
                r = buscar(self.cliente, destino, ida, vuelta, perfil["max_escalas"])
                break
            except Exception as e:  # un fallo de red no debe parar al resto
                self.errores += 1
                self.log(f"  ! {ciudad} {ida} (intento {intento}): {e}")
                r = None
                time.sleep(config.PAUSA_ENTRE_BUSQUEDAS * 3)
        time.sleep(config.PAUSA_ENTRE_BUSQUEDAS)
        if r:
            self.resultados += 1
            r.update(perfil=perfil_clave, ciudad=ciudad, precio_ref=precio_ref)
        return r


def explorar(buscador, hoy=None, solo_perfil=None):
    """Agente explorador: devuelve todos los precios encontrados en las fechas que tocan hoy."""
    hoy = hoy or date.today()
    resultados = []
    for clave, perfil in config.PERFILES.items():
        if solo_perfil and clave != solo_perfil:
            continue
        candidatas = fechas_candidatas(perfil, hoy)
        for i, (codigo, (ciudad, _)) in enumerate(perfil["destinos"].items()):
            for ida in fechas_de_hoy(candidatas, perfil["fechas_por_destino"], hoy.toordinal() + i):
                r = buscador.buscar(clave, codigo, ida, ida + timedelta(days=perfil["noches"]))
                if r:
                    resultados.append(r)
                    buscador.log(f"  {ciudad} {r['ida']}: {r['precio_persona']} €")
                else:
                    buscador.log(f"  {ciudad} {ida}: sin resultados ({buscar.ultimo_motivo})")
    return resultados
