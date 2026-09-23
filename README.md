# Alertas Macro — EUR/USD, US100, US30

Bot que vigila el calendario económico y, cuando sale un dato de alto impacto
(EUR o USD), le pide a Claude que analice si es favorable o desfavorable para
EUR/USD, US100 (Nasdaq) y US30 (Dow), y te lo envía a Telegram.

## 1. Crear el bot de Telegram

1. Abre Telegram y busca **@BotFather**.
2. Envíale `/newbot`, ponle un nombre y un usuario (debe acabar en `bot`).
3. BotFather te da un **token** tipo `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxx`.
   Guárdalo como `TELEGRAM_BOT_TOKEN`.
4. Escríbele cualquier mensaje a tu bot recién creado (para "activarlo").
5. Averigua tu **chat_id**: entra en
   `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` en el navegador
   (sustituye `<TU_TOKEN>`) y busca el número en `"chat":{"id": ...}`.
   Guárdalo como `TELEGRAM_CHAT_ID`.

## 2. Subir estos 4 archivos a tu repositorio `alertas-macro`

- `main.py`
- `requirements.txt`
- `.github/workflows/alertas.yml`
- `README.md` (este archivo)

## 3. Configurar los Secrets en GitHub

En el repo: **Settings → Secrets and variables → Actions → New repository secret**.
Añade estos tres:

| Nombre | Valor |
|---|---|
| `ANTHROPIC_API_KEY` | tu clave `sk-ant-...` de platform.claude.com |
| `TELEGRAM_BOT_TOKEN` | el token que te dio BotFather |
| `TELEGRAM_CHAT_ID` | tu chat_id del paso 1.5 |

## 4. Probarlo

Ve a la pestaña **Actions** del repo → workflow **Alertas Macro** →
**Run workflow** (botón manual). Revisa los logs; si hay un evento de alto
impacto reciente, te debería llegar el mensaje a Telegram.

A partir de ahí se ejecuta solo cada 5 minutos.

## Notas

- Solo avisa de eventos con impacto **High** de **EUR** o **USD**, una vez
  que el dato "actual" ya se publicó (no antes).
- Además del sesgo (favorable/desfavorable), el mensaje incluye dirección
  esperada, una posible zona de entrada y un posible objetivo de precio para
  EUR/USD, US100 y US30, calculados por Claude a partir del precio en vivo
  (Yahoo Finance) y la magnitud de la sorpresa del dato.
- **Importante**: esas zonas y objetivos son una estimación orientativa de
  la IA en el momento, no un análisis técnico (no mira estructura, soportes/
  resistencias reales ni velas) ni una recomendación de inversión — trátalo
  como un punto de partida para tu propio análisis, no como una señal para
  operar a ciegas.
- Guarda en `notified.json` qué eventos ya avisó, para no repetir el mismo
  mensaje en cada ejecución.
- El calendario viene de ForexFactory (feed público, sin necesidad de clave);
  los precios en vivo, de Yahoo Finance (también público).
- Si quieres avisar también *antes* de que salga el dato (por ejemplo 15 min
  antes, sin análisis todavía), dímelo y añado esa segunda alerta.
