# Quickstart: Spec 086 — Autopsia Autónoma de Incidentes y Supervisor Conversacional (PROP-016)

**Fecha**: 2026-10-02  
**Autor**: Antigravity Engineering (Gemini 3.8 Flash High)  

---

## 1. Comandos de Telegram

### Inspección Forense del Último Incidente
Consulta el diagnóstico post-mortem del último reinicio registrado para un minero específico:
```text
/autopsia 25
/causa_raiz 24
/autopsy 23
```
*Si no se pasa argumento, muestra el resumen de las autopsias más recientes de toda la flota.*

---

## 2. Supervisor Conversacional Q&A (Lenguaje Natural Offline)

El bot interpreta directamente preguntas operativas habituales sin necesidad de comandos formales:
- `¿Por qué reinició la 25?` $\rightarrow$ Devuelve el diagnóstico forense del último incidente.
- `¿Qué le pasó a la 24?` $\rightarrow$ Consulta la última causa raíz en SQLite.
- `¿Cómo está el cable de red?` $\rightarrow$ Analiza caídas de enlace en la última hora.
- `¿Hay problemas de temperatura?` $\rightarrow$ Lista los mineros con chip temp más elevado.

---

## 3. Alertas Forenses Automáticas

Cuando un minero sufre un reinicio clasificado como `unexpected`, el monitor no se limita a avisar que cayó el tiempo transcurrido, sino que adjunta de forma automática el dictamen forense:

```text
🚨 REINICIO EN S19JPRO-25
────────────────────────────────
Causa: ⚠️ ENLACE ETHERNET
• 8 caídas de enlace en 5 min
• Watchdog cortó por hashrate 17%
Silicio: ✅ SANO (3 cadenas)
Sugerencia: Revisar cable RJ45
────────────────────────────────
```

---

## 4. Ejecución de Pruebas Automatizadas

Para validar todo el flujo forense y las compuertas de seguridad:
```powershell
& ".\.venv\Scripts\python.exe" -m pytest tests\test_incident_autopsy.py -v
```
Para verificar la suite global completa:
```powershell
& ".\.venv\Scripts\python.exe" -m pytest -q
```
