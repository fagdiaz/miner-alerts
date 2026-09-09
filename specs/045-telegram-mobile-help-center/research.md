# Investigación y Antecedentes Técnicos: Spec 045

## 1. Problema de Pantalla Móvil y Telegram Desktop vs Mobile
- En Telegram Desktop, los bloques de código y textos tabulares se despliegan en anchos de 80 a 120 columnas sin quiebre de línea forzado.
- En Telegram Mobile (dispositivos típicos con 360-412dp de ancho lógico en portrait, tamaño de fuente predeterminado), el área de texto admite aproximadamente 32-36 caracteres por línea antes de aplicar soft-wrapping.
- Cuando una tabla con encabezados fijos o columnas formateadas con espacios supera los 34 caracteres:
  1. Las palabras caen arbitrariamente a la siguiente línea desalineando los valores.
  2. Si se usan bloques de código triple comilla (\`\`\`), Telegram Mobile renderiza una caja con desplazamiento horizontal (scroll horizontal), lo que oculta métricas clave e incomoda la lectura al obligar a hacer swipe continuo con el pulgar.
- **Conclusión de Diseño**: Las tarjetas verticales (*card layout*) con viñetas claras (`•`), valores en líneas dedicadas y líneas de datos <= 32 caracteres visibles son la solución óptima para legibilidad táctil inmediata.

## 2. Inventario Canónico de Comandos del Dispatcher
Un análisis exhaustivo del bucle de despacho de `app/miner_monitor.py` reveló los siguientes comandos soportados en tiempo de ejecución:
1. `menu`, `start`, `panel`: Abre el Command Center táctil con InlineKeyboardMarkup.
2. `silent`, `silencio`, `modo_silencio`: Activa o desactiva el régimen silencioso acotado (40%-70% PWM) con guarda térmica.
3. `status`: Snapshot actual de la flota de mineros.
4. `fans`, `fan`: Monitoreo de ventiladores, RPM, PWM y margen térmico a 85°C.
5. `efficiency`, `eff`: Monitoreo de Joules por Terahash (J/TH) y consumo eléctrico.
6. `presets`, `preset`, `profile`: Supervisión de perfiles de frecuencia, voltaje y autotuning.
7. `governor`, `gov`: Regulador de temperatura de lazo cerrado para ventiladores.
8. `balancer`, `bal`, `power`: Balanceador de carga y presets para elevadores.
9. `elevadores`, `elevators`, `sensibilidad`, `elev`: Diagnóstico de sensibilidad eléctrica de elevadores.
10. `snooze`, `unsnooze`, `snoozed`: Mantenimiento y silenciamiento temporal de alertas.
11. `digest`, `summary`: Resumen diario consolidado de 24 horas.
12. `events`, `event`: Consulta de historial y detalle de incidentes registrados.
13. `why`: Explicación de la última decisión de autorreinicio.
14. `diagnose`: Diagnóstico correlacionado multidisciplinario.
15. `health`: Comparación con baseline estable.
16. `quality`: Análisis de shares y errores de hashboards.
17. `firmware`: Inspección de eventos de firmware Vnish.
18. `chart`: Gráficos visuales PNG generados en memoria.
19. `selftest`, `test`: Diagnóstico rápido de Telegram, Hashcore y mineros.
20. `reboot`, `reboot_no_ok`, `restart`, `confirm`: Comandos de control crítico con confirmación en dos pasos.
21. `help`, `info`: Consulta de ayuda y detalle de comandos.

## 3. Limitaciones de Callbacks en Telegram Bot API
- El parámetro `callback_data` de un botón inline tiene un límite duro estricto de **64 bytes** (codificado en UTF-8).
- Prefijos largos o parámetros innecesarios pueden provocar errores silenciosos o excepciones 400 Bad Request.
- Por tanto, la gramática de ayuda usa identificadores cortos:
  - `help:nav:home` (13 bytes)
  - `help:cat:<cat_id>` (cat_id de 3-4 chars -> ~12-14 bytes)
  - `help:cmd:<cmd_name>` (cmd_name de máx 16 chars -> ~25 bytes)
  Todos cumplen holgadamente el límite de 64 bytes.

## 4. Limitaciones de Markdown en Telegram Bot API
- Al usar `parse_mode="Markdown"`, caracteres no emparejados como `_`, `*`, `` ` `` y `[` provocan errores 400 Bad Request.
- En nombres de mineros (e.g. `S19JPRO_23`), los guiones bajos provocan errores si no están escapados como `\_`.
- Por tanto, la función `escape_markdown` debe proteger caracteres especiales antes de interpolar variables dinámicas o nombres.
