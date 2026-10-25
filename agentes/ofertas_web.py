"""Agente lector de webs de ofertas: recoge los chollos que publican webs
especializadas (vía RSS) y se queda con los recientes que salen desde España."""

import calendar
import html
import re
from datetime import datetime, timedelta, timezone

import feedparser

AGENTE = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"
DIAS_RECIENTES = 4

FUENTES = [
    # (nombre, url, filtro): con filtro solo se aceptan entradas que lo mencionen
    ("Viajeros Piratas", "https://www.viajerospiratas.es/feed/", None),
    ("Travelzoo", "https://www.travelzoo.com/es/feed/", None),
    ("Fly4free", "https://www.fly4free.com/feed/", re.compile(r"\b(madrid|spain|barcelona)\b", re.I)),
]

RE_PRECIO = re.compile(r"(?:€\s?(\d[\d.]*)|(\d[\d.]*)\s?(?:€|euros?))", re.I)


def _texto_plano(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _precio(texto):
    m = RE_PRECIO.search(texto)
    if not m:
        return None
    return int((m.group(1) or m.group(2)).replace(".", ""))


def recoger(log=print):
    limite = datetime.now(timezone.utc) - timedelta(days=DIAS_RECIENTES)
    ofertas = []
    for nombre, url, filtro in FUENTES:
        try:
            feed = feedparser.parse(url, agent=AGENTE)
        except Exception as e:
            log(f"  ! {nombre}: {e}")
            continue
        n = 0
        for e in feed.entries:
            fecha_struct = e.get("published_parsed") or e.get("updated_parsed")
            fecha = (
                datetime.fromtimestamp(calendar.timegm(fecha_struct), timezone.utc) if fecha_struct else None
            )
            if fecha and fecha < limite:
                continue
            titulo = _texto_plano(e.get("title"))
            resumen = _texto_plano(e.get("summary"))[:280]
            if filtro and not filtro.search(f"{titulo} {resumen}"):
                continue
            ofertas.append({
                "fuente": nombre,
                "titulo": titulo,
                "resumen": resumen,
                "enlace": e.get("link"),
                "precio": _precio(titulo) or _precio(resumen),
                "fecha": fecha.date().isoformat() if fecha else None,
            })
            n += 1
        log(f"  {nombre}: {n} ofertas recientes")
    return ofertas
