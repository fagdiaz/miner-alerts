# Contrato de Interfaz: Active Thermal Purge Ramp & Acoustic Contrast API

## 1. Modulación de Ventilación Vnish REST API
- **Rampa de Purga Térmica (Inicio de Parada)**:
  * Invocación: `safe_set_fan_duty(host, password, duty_percent=100, timeout=2.5)`
  * Payload Vnish: `POST /api/v1/settings` con `{"miner": {"cooling": {"mode": {"name": "manual", "param": 100}}}}`
  * Timing: Despachado en paralelo inmediatamente tras `safe_stop_mining` (segundo 0 de la ventana).
  * Efecto: Ventiladores aceleran a 100% (~6.000 RPM). Con 0W de potencia en hashboards, el aire forzado evacua masivamente el calor latente de los bloques de aluminio.

- **Piso de Reposo Acústico (Término de Purga)**:
  * Invocación: `safe_set_fan_duty(host, password, duty_percent=40, timeout=2.5)`
  * Payload Vnish: `POST /api/v1/settings` con `{"miner": {"cooling": {"mode": {"name": "manual", "param": 40}}}}`
  * Timing: Despachado en el segundo 45 exacto por el hilo daemon `ShutdownPurgeNotify`.
  * Efecto: Ventiladores desaceleran abruptamente de 6.000 RPM a ~2.400 RPM / piso mínimo (~720 RPM en reposo sin carga). El contraste acústico inmediato (silencio relativo) confirma al técnico in situ que los disipadores están fríos y el corte eléctrico es seguro.

- **Restauración de Ventilación en Reanudación (`/resume`)**:
  * Invocación tras `safe_resume_mining`: restablecer duty activo preventivo (ej: 100% o delegación al Fan Governor) para evitar que los chips inicien carga con ventiladores en reposo.

## 2. Contrato de Concurrencia Desacoplada
- Despacho mediante `execute_parallel_fan_duty(miners, duty, password, timeout=2.5)`:
  * Bounded `ThreadPoolExecutor(max_workers=min(4, len(miners)))`.
  * Timeout individual: 2.5s.
  * Captura total de excepciones y retorno de diccionario `{miner_id: OperationResult}`.
  * No bloquea en ningún caso el ciclo principal del monitor de API 4028.

## 3. Contrato UI Telegram Mobile-First (<= 32 Columnas)
- `render_shutdown_in_progress`:
  * Línea: `• Coolers: Rampa 100% (Purga)`
  * Línea: `⏳ Barriendo calor (45s)`
  * Cumple `visible_line_width <= 32`.
- `render_safe_area_card`:
  * Línea: `• Coolers: Reposo (40%) | Silencio`
  * Línea: `• Disipadores: Fríos (<35°C)`
  * Línea: `🔌 Ya podés bajar la térmica`
  * Cumple `visible_line_width <= 32`.
