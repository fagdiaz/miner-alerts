# Spec 074: Paired Elevator Contingency & Inrush Dampener

## 1. Contexto & Justificación Operativa
Durante eventos de desbalance de fases eléctricas o reinicios en un elevador monofásico con dos mineros ASIC (S19j Pro), el algoritmo de contingencia asimétrica ([Spec 057](../057-intervention-governance-contingency/spec.md)) presentaba un desacople de software que impedía la aplicación del preset físico en hardware (Hipótesis 1), un conflicto con el `preset_switcher` interno de VNish que re-aceleraba los equipos en frío (Hipótesis 2), y una falta de amortiguación en el minero compañero ante el transitorio de corriente inductivo ($L \cdot \frac{di}{dt}$) del arranque (Hipótesis 3), provocando caídas en cascada reproducibles de 750s a 960s.

Adicionalmente, el Fan Governor ([Spec 039](../039-vnish-fan-governor/spec.md)) activaba `RECOVERY_MAX_COOLING` (100% PWM) durante el booteo, enfriando los chips BM1362 a $<53^\circ\text{C}$ e induciendo fallas espurias de comunicación SPI/I2C (`chain_break` en autotune en frío, Hipótesis 4).

## 2. Objetivos Principales
1. **Resolución Canónica Incondicional**: Asegurar que la asignación de presets por contingencia (`_decision.target_miner`) resuelva correctamente tanto nombres canónicos (`S19JPRO-24`) como alias de display (`24`) hacia el objeto de configuración y socket de red.
2. **Top-Preset Clamping en VNish**: Al modular el preset de un equipo a la baja (ej. 2300W o 2100W), topear simultáneamente `preset_switcher.top_preset` al mismo valor para evitar que el firmware acelere autónomamente cuando los chips están fríos.
3. **Amortiguación de Arranque de Par (Paired Inrush Dampener)**: Cuando un minero en un elevador arranca ($elapsed < 300\text{s}$), el compañero robusto reduce transitoriamente su consumo en 1 peldaño relativo (ej. 2700W $\to$ 2500W) para liberar 200W-400W de margen eléctrico inductivo durante el transitorio $di/dt$. Al consolidar 300s de estabilidad con 3/3 placas, el compañero recupera su preset nominal.
4. **Piso Térmico en Calentamiento (Governor Warmup Floor)**: Evitar `RECOVERY_MAX_COOLING` cuando el minero está en fase de calentamiento ($elapsed < 180\text{s}$ o $P < 500\text{W}$), manteniendo ventilación moderada ($\le 60\%$ PWM si $T < 75^\circ\text{C}$) para que los chips BM1362 alcancen su temperatura óptima de autotune ($65^\circ\text{C}-75^\circ\text{C}$).

## 3. Requisitos No Funcionales & Invariantes
- **Cero Regresiones**: Mantener el 100% de la suite de pruebas unitarias existente (1204 tests PASS).
- **Seguridad Térmica Primaria**: Si la temperatura supera $83.5^\circ\text{C}$, el Emergency Spike del Governor tiene prioridad absoluta e inmediata sobre el Warmup Floor.
- **Determinismo Puro**: La lógica de decisiones en `adaptive_contingency.py` y `fan_governor.py` debe ser libre de I/O de red, 100% determinista y verificable con tests unitarios.
