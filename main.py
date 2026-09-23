"""
Alertas Macro — EUR/USD, US100 (Nasdaq), US30 (Dow)
Flujo: calendario económico -> análisis con Claude -> envío a Telegram

Se ejecuta periódicamente (ver .github/workflows/alertas.yml).
En cada ejecución:
  1. Descarga el calendario económico de la semana (ForexFactory, gratis, sin API key)
  2. Filtra eventos de alto impacto que ocurren en los próximos ~10-15 minutos
     o que acaban de publicarse con "actual" ya disponible
  3. Consulta el precio actual de EUR/USD, US100 y US30
  4. Para cada evento relevante, pide a Claude un análisis de impacto que
     incluye favorable/desfavorable, dirección esperada, posible zona de
     entrada y hasta dónde podría llegar el movimiento
  5. Envía el mensaje a tu chat de Telegram
  6. Guarda en un archivo local qué eventos ya se notificaron, para no repetir
"""

import os
import json
import datetime
from pathlib import Path
from urllib.request import urlopen, Request

import anthropic

# ---------- Configuración ----------

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
NOTIFIED_FILE = Path(__file__).parent / "notified.json"

# Símbolos de Yahoo Finance para el precio en vivo (feed público, sin API key)
PRICE_SYMBOLS = {
    "EUR/USD": "EURUSD=X",
    "US100": "NQ=F",   # futuro Nasdaq 100, sigue muy de cerca al índice
    "US30": "YM=F",    # futuro Dow Jones
}

# Solo estas divisas/eventos nos interesan directamente.
# EUR y USD porque mueven EUR/USD; USD también mueve US100/US30.
RELEVANT_CURRENCIES = {"EUR", "USD"}
RELEVANT_IMPACT = {"High"}  # ForexFactory: Low / Medium / High

ANTHROPIC_MODEL = "claude-sonnet-4-6"

# ---------- Utilidades ----------

def cargar_notificados() -> set:
    if NOTIFIED_FILE.exists():
        return set(json.loads(NOTIFIED_FILE.read_text()))
    return set()


def guardar_notificados(ids: set) -> None:
    NOTIFIED_FILE.write_text(json.dumps(sorted(ids)))


def obtener_calendario() -> list:
    req = Request(CALENDAR_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def evento_id(evento: dict) -> str:
    # Identificador estable para no notificar dos veces el mismo evento
    return f"{evento.get('title')}|{evento.get('date')}|{evento.get('country')}"


def es_relevante_ahora(evento: dict) -> bool:
    if evento.get("impact") not in RELEVANT_IMPACT:
        return False
    if evento.get("country") not in RELEVANT_CURRENCIES:
        return False
    # Solo nos interesa una vez que el dato "actual" ya se publicó
    return bool(evento.get("actual"))


def obtener_precio(simbolo: str) -> float | None:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}"
        "?interval=1m&range=1d"
    )
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["chart"]["result"][0]["meta"]["regularMarketPrice"]
    except Exception as e:
        print(f"No se pudo obtener precio de {simbolo}: {e}")
        return None


def obtener_precios_actuales() -> dict:
    return {nombre: obtener_precio(simbolo) for nombre, simbolo in PRICE_SYMBOLS.items()}


def analizar_con_claude(client: anthropic.Anthropic, evento: dict, precios: dict) -> str:
    precios_texto = "\n".join(
        f"- {nombre}: {valor if valor is not None else 'N/D'}"
        for nombre, valor in precios.items()
    )

    prompt = f"""Acaba de publicarse este dato macroeconómico:

Evento: {evento.get('title')}
País/divisa: {evento.get('country')}
Previsión: {evento.get('forecast') or 'N/D'}
Anterior: {evento.get('previous') or 'N/D'}
Real (actual): {evento.get('actual') or 'N/D'}

Precio actual en el momento del análisis:
{precios_texto}

Para cada uno de estos tres instrumentos — EUR/USD, US100 (Nasdaq) y US30 (Dow) —
analiza el impacto probable a muy corto plazo (próximos minutos/horas) y da:

1. Sesgo: FAVORABLE, DESFAVORABLE o NEUTRAL (para una posición larga)
2. Dirección esperada: alcista, bajista o rango
3. Posible zona de entrada (un nivel o rango de precio cercano al actual)
4. Posible objetivo: hasta dónde podría llegar el movimiento (nivel de precio)
5. Motivo, en una frase

Sé directo, sin disclaimers largos. Los niveles son una estimación orientativa
basada en el precio actual y la magnitud de la sorpresa del dato, no un cálculo
técnico exacto — dilo en una frase al final del mensaje completo, no por cada
instrumento.

Formato exacto por instrumento:

EUR/USD: [FAVORABLE/DESFAVORABLE/NEUTRAL] | [alcista/bajista/rango]
  Entrada: ~X.XXXX | Objetivo: ~X.XXXX — motivo

US100: [FAVORABLE/DESFAVORABLE/NEUTRAL] | [alcista/bajista/rango]
  Entrada: ~XXXXX | Objetivo: ~XXXXX — motivo

US30: [FAVORABLE/DESFAVORABLE/NEUTRAL] | [alcista/bajista/rango]
  Entrada: ~XXXXX | Objetivo: ~XXXXX — motivo
"""
    respuesta = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return respuesta.content[0].text.strip()


def enviar_telegram(token: str, chat_id: str, texto: str) -> None:
    import urllib.parse
    url = TELEGRAM_API.format(token=token)
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "Markdown",
    }).encode()
    req = Request(url, data=data)
    with urlopen(req, timeout=20) as resp:
        resp.read()


# ---------- Programa principal ----------

def main():
    anthropic_key = os.environ["ANTHROPIC_API_KEY"]
    telegram_token = os.environ["TELEGRAM_BOT_TOKEN"]
    telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

    client = anthropic.Anthropic(api_key=anthropic_key)

    notificados = cargar_notificados()
    calendario = obtener_calendario()

    nuevos_notificados = set(notificados)

    for evento in calendario:
        if not es_relevante_ahora(evento):
            continue

        eid = evento_id(evento)
        if eid in notificados:
            continue

        precios = obtener_precios_actuales()
        analisis = analizar_con_claude(client, evento, precios)

        mensaje = (
            f"📊 *{evento.get('title')}* ({evento.get('country')})\n"
            f"Previsión: {evento.get('forecast') or 'N/D'} | "
            f"Anterior: {evento.get('previous') or 'N/D'} | "
            f"Real: {evento.get('actual') or 'N/D'}\n\n"
            f"{analisis}"
        )

        enviar_telegram(telegram_token, telegram_chat_id, mensaje)
        nuevos_notificados.add(eid)
        print(f"Notificado: {eid}")

    guardar_notificados(nuevos_notificados)


if __name__ == "__main__":
    main()
