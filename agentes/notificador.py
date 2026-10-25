"""Agente notificador: avisa SOLO de ofertas excelentes y confirmadas, y de fallos
del sistema. Canales configurables por variables de entorno (si faltan, se omiten):

  TELEGRAM_TOKEN      token del bot (de @BotFather)
  TELEGRAM_CHAT       id del chat, canal o grupo
  WHATSAPP_TELEFONO   p. ej. +34600111222   (CallMeBot)
  WHATSAPP_APIKEY     la que da CallMeBot al darse de alta
  WEB_URL             enlace a la web, para incluirlo en el mensaje
"""

import json
import os
from urllib.parse import quote

from primp import Client

import config


def _fecha(iso):
    return f"{int(iso[8:10])}/{int(iso[5:7])}"


def componer(ofertas, personas=config.PERSONAS):
    titulo = "¡Chollo de vuelo desde Madrid!" if len(ofertas) == 1 else f"{len(ofertas)} chollos de vuelo desde Madrid"
    lineas = [f"🔥 *{titulo}*", ""]
    for o in sorted(ofertas, key=lambda o: -o["puntuacion"]):
        aerolineas = o["aerolineas"] if isinstance(o["aerolineas"], list) else json.loads(o["aerolineas"])
        escalas = "directo" if not o["escalas"] else f"{o['escalas']} escala" + ("s" if o["escalas"] > 1 else "")
        rebaja = round((o["tipico"] - o["precio_actual"]) / o["tipico"] * 100)
        lineas += [
            f"✈️ *{o['ciudad']}* · {_fecha(o['ida'])} → {_fecha(o['vuelta'])}",
            f"⭐ Puntuación *{o['puntuacion']}/100*",
            f"💶 *{o['precio_actual']} €/persona* ida y vuelta (normal ~{o['tipico']} €, −{rebaja}%)",
            f"👥 {personas} personas ≈ {o['precio_actual'] * personas} € · {escalas} · {', '.join(aerolineas)}",
            o["enlace"],
            "",
        ]
    if os.environ.get("WEB_URL"):
        lineas.append(f"Todas las ofertas: {os.environ['WEB_URL']}")
    lineas.append("_Los precios cambian rápido: compruébalo antes de reservar._")
    return "\n".join(lineas).strip()


def _enviar_texto(texto, log):
    """Envía por todos los canales configurados. Devuelve True si al menos uno funcionó."""
    cliente = Client(timeout=30)
    enviado = False

    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT")
    if token and chat:
        try:
            r = cliente.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": texto, "parse_mode": "Markdown", "disable_web_page_preview": True},
            )
            log(f"  Telegram: {r.status_code}")
            enviado |= r.status_code == 200
        except Exception as e:
            log(f"  ! Telegram: {e}")

    tel, apikey = os.environ.get("WHATSAPP_TELEFONO"), os.environ.get("WHATSAPP_APIKEY")
    if tel and apikey:
        try:
            r = cliente.get(f"https://api.callmebot.com/whatsapp.php?phone={quote(tel)}&text={quote(texto)}&apikey={quote(apikey)}")
            log(f"  WhatsApp: {r.status_code}")
            enviado |= r.status_code == 200
        except Exception as e:
            log(f"  ! WhatsApp: {e}")

    if not (token and chat) and not (tel and apikey):
        log("  (sin canales configurados; mensaje que se enviaría:)\n" + texto)
    return enviado


def avisar_ofertas(ofertas, log=print):
    if not ofertas:
        log("  Ninguna oferta excelente nueva: no se envía nada.")
        return False
    return _enviar_texto(componer(ofertas), log)


def avisar_fallo(nota, log=print):
    return _enviar_texto(f"⚠️ *Chollos de viaje: el buscador tiene problemas*\n{nota}", log)
