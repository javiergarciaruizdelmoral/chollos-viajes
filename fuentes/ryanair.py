"""Fuente Ryanair: tarifas ida y vuelta más baratas desde el origen a todos sus destinos.

Usa los mismos servicios públicos que la web de Ryanair (no hay API oficial):
  - lista de rutas desde el aeropuerto de origen
  - buscador de tarifas ida y vuelta, consultado por país de destino (máx. 20 aeropuertos por consulta)

Cada consulta devuelve la tarifa más barata por destino dentro de la ventana de fechas,
así que la ventana se trocea por meses para obtener más fechas candidatas.
"""

import json
import time
from datetime import date, timedelta

from primp import Client

RUTAS = "https://www.ryanair.com/api/views/locate/searchWidget/routes/es/airport/{origen}"
TARIFAS = "https://services-api.ryanair.com/farfnd/v4/roundTripFares"
ENLACE = (
    "https://www.ryanair.com/es/es/trip/flights/select?adults=1&teens=0&children=0&infants=0"
    "&dateOut={ida}&dateIn={vuelta}&originIata={origen}&destinationIata={destino}&isReturn=true"
)
DIAS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
PAUSA = 1


class Ryanair:
    nombre = "ryanair"

    def __init__(self, origen, log=print):
        self.origen = origen
        self.log = log
        self.cliente = Client(impersonate="chrome_145", timeout=30)
        self.consultas = self.errores = 0

    def _get(self, url, params=None):
        self.consultas += 1
        r = self.cliente.get(url, params={k: str(v) for k, v in (params or {}).items()})
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
        return json.loads(r.text)

    def destinos(self):
        """{iata: (ciudad, país)} de todos los destinos de Ryanair desde el origen."""
        rutas = self._get(RUTAS.format(origen=self.origen))
        return {
            x["arrivalAirport"]["code"]: (x["arrivalAirport"]["name"], x["arrivalAirport"]["country"]["code"])
            for x in rutas
        }

    def tarifas(self, desde, hasta, noches, dias_salida):
        """Tarifas ida y vuelta con salida entre `desde` y `hasta`, de `noches` (min, max) noches.

        Devuelve registros en el formato común de las fuentes.
        """
        destinos = self.destinos()
        paises = sorted({pais for _, pais in destinos.values()})
        vistos = {}
        inicio = desde
        while inicio <= hasta:
            fin = min(hasta, (inicio.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1))
            for pais in paises:
                params = {
                    "departureAirportIataCode": self.origen, "arrivalCountryCode": pais,
                    "outboundDepartureDateFrom": inicio.isoformat(), "outboundDepartureDateTo": fin.isoformat(),
                    "inboundDepartureDateFrom": inicio.isoformat(),
                    "inboundDepartureDateTo": (fin + timedelta(days=noches[1])).isoformat(),
                    "durationFrom": noches[0], "durationTo": noches[1],
                    "outboundDepartureDaysOfWeek": ",".join(DIAS[d] for d in dias_salida),
                    "currency": "EUR", "market": "es-es", "adultPaxCount": 1, "limit": 20,
                }
                try:
                    for f in self._get(TARIFAS, params).get("fares", []):
                        r = self._registro(f, destinos)
                        clave = (r["destino"], r["ida"], r["vuelta"])
                        if clave not in vistos or r["precio_persona"] < vistos[clave]["precio_persona"]:
                            vistos[clave] = r
                except Exception as e:
                    self.errores += 1
                    self.log(f"  ! Ryanair {pais} {inicio:%m/%Y}: {e}")
                time.sleep(PAUSA)
            inicio = fin + timedelta(days=1)
        return list(vistos.values())

    def _registro(self, f, destinos):
        ida, vuelta = f["outbound"], f["inbound"]
        destino = ida["arrivalAirport"]["iataCode"]
        fecha_ida, fecha_vuelta = ida["departureDate"][:10], vuelta["departureDate"][:10]
        return {
            "fuente": self.nombre,
            "destino": destino,
            "ciudad": destinos.get(destino, (ida["arrivalAirport"]["name"],))[0],
            "pais": ida["arrivalAirport"]["city"]["countryCode"],
            "ida": fecha_ida,
            "vuelta": fecha_vuelta,
            "precio_persona": round(f["summary"]["price"]["value"]),
            "aerolineas": ["Ryanair"],
            "escalas": 0,
            "minutos_vuelo": None,
            "hora_salida": ida["departureDate"][11:16],
            "hora_vuelta": vuelta["departureDate"][11:16],
            "enlace": ENLACE.format(ida=fecha_ida, vuelta=fecha_vuelta, origen=self.origen, destino=destino),
        }
