# miner-alerts

## Setup rapido (PowerShell)
cd "F:\\02-ASIC - mineros\\miner-alerts"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

## Config
- Copia `app/config.example.json` a `app/config.json`.
- Completa `telegram.bot_token` y `telegram.chat_id`.
- `app/config.json` NO se commitea.

## BotFather
- Crea el bot en Telegram con `@BotFather` y obtene el token.

## Obtener chat_id
- Opcion 1: En Telegram, habla con `@userinfobot` y te devuelve tu chat_id.
- Opcion 2: Envia un mensaje a tu bot y abre en el navegador `https://api.telegram.org/bot<TOKEN>/getUpdates`, luego toma `message.chat.id`.

## Test de conectividad a mineros (puerto 4028)
Test-NetConnection 192.168.1.101 -Port 4028

## Ejecutar
python app\miner_monitor.py

## Debug (4028)
python app\debug_4028.py 192.168.100.23
