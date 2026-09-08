# Spec 039: Vnish Thermal & Acoustic Fan Governor

## Estado y Metadatos
- **ID**: `039-vnish-fan-governor`
- **Prioridad**: P1 (Confiabilidad Operativa, Prevención de Throttling y Reducción Acústica)
- **Estado**: PROPUESTA FORMAL (Lista para Auditoría de Claude Sonnet 4.6 Thinking)
- **Fecha**: 2026-09-08
- **Autor**: Antigravity (Pair Programming con Operador)
- **Dependencias**: Specs 020, 022, 035 (`app/fan_health.py`), 037 (`app/vnish_presets.py`), 038 (V3 Hardening).

---

## 1. Contexto Operativo y Problema Raíz

### 1.1 El Problema Observado
En la flota de mineros Antminer S19j Pro corriendo firmware Vnish (versión `1.2.7` a `1.2.9`):
1. **Modo Automático Nativo Deficiente**: El algoritmo de control de ventiladores integrado en Vnish presenta una inercia térmica excesiva y un retardo de reacción significativo (*delay*). Ante incrementos de temperatura ambiente o carga de trabajo, los ventiladores demoran en acelerar, permitiendo que la temperatura máxima de los chips alcance los **84.0°C**.
2. **Throttling Forzado por `preset_switcher`**: El firmware Vnish tiene configurado activamente el `preset_switcher` con el umbral `decrease_temp: 84°C`. Al tocar los 84°C, el firmware reduce automáticamente el preset de frecuencia/potencia (downclocking), provocando caídas abruptas de hashrate (de 1850W/90+ TH/s a 1740W o inferior).
3. **Paliativo Actual del Operador (Manual 100%)**: Para evitar el downclocking, el operador configuró todos los ventiladores en modo manual fijo al **100%** (`fan_duty: 100`, ~6.000 RPM). Si bien esto mantiene la temperatura en un rango seguro (75°C a 80°C), introduce:
   - **Contaminación acústica máxima** en la instalación.
   - **Desgaste acelerado y prematuro** de los rodamientos de los 4 ventiladores por minero.
   - **Consumo eléctrico parásito innecesario** (los ventiladores al 100% consumen sustancialmente más potencia).
4. **Falta de Visibilidad en el Monitor**: El comando `/fans` y la telemetría actual no reportan si el minero se encuentra en modo `manual` o `auto`, impidiendo que el operador conozca el estado de control sin ingresar a la interfaz web de cada equipo.

---

## 2. Objetivos de la Especificación

1. **Visibilidad Total del Modo de Ventilación (Fase 1 - Inmediata)**:
   - Extraer e incorporar el modo de control (`manual`, `auto`, `immers`) y el porcentaje de PWM actual tanto desde la API 4028 (`fan_mode`, `fan_pwm`) como desde la API REST `/api/v1/summary`.
   - Exponer el modo y porcentaje en el comando `/fans` de Telegram, la tabla ejecutiva `/status` y las instantáneas de diagnóstico.
2. **Cliente Seguro Vnish REST API (Fase 2)**:
   - Proveer un cliente HTTP (`VnishClient`) con ciclo de vida seguro de sesión:
     - Autenticación mediante `POST /api/v1/unlock` (`{"pw": "<password>"}`) obteniendo token Bearer.
     - Lectura atómica de configuración mediante `GET /api/v1/settings`.
     - Actualización protegida mediante `POST /api/v1/settings`.
     - Cierre inmediato de sesión mediante `POST /api/v1/lock`.
   - Aislamiento estricto contra timeouts, caídas de red y reintentos limitados.
3. **Algoritmo Regulador Térmico/Acústico de Lazo Cerrado (Fase 3)**:
   - Implementar un gobernador automático (`FanGovernor`) que module el PWM manual de forma suave y controlada:
     - **Temperatura Objetivo ($T_{target}$)**: Configurable (default: **82.0°C**), garantizando un margen de 2.0°C por debajo del umbral de downclock (84.0°C) y 3.0°C por debajo del corte de seguridad (85.0°C).
     - **Ajuste Gradual por Escalones**: Variaciones acotadas de $\pm 2\%$ a $\pm 3\%$ por paso.
     - **Ventana de Asentamiento Térmico (*Dwell Time*)**: Espera obligatoria de 90 a 120 segundos entre modulaciones consecutivas para permitir la estabilización física de los disipadores.
     - **Piso de Seguridad Infranqueable ($PWM_{min}$)**: Límite inferior configurable (default: **70%**). El algoritmo jamás reducirá la velocidad por debajo de este valor.
     - **Disparo de Emergencia ante Picos Térmicos (*Thermal Spike Override*)**: Si cualquier chip supera los **83.0°C**, el gobernador omite el paso gradual y restablece inmediatamente los ventiladores al **100%**.
     - **Modo Simulación (*Dry-Run*) y Feature Flag**: Deshabilitado por defecto (`fan_governor_enabled: false`), con capacidad de operar en modo sólo-auditoría (`dry_run: true`) registrando las decisiones sin enviar comandos de escritura al hardware.
4. **Comandos de Control en Telegram (Fase 4)**:
   - `/governor` (alias `/gov`): Muestra el estado del regulador, objetivo térmico, PWM actual por minero y última acción tomada.
   - `/gov set <temp>`: Ajuste en caliente del target térmico con validación de límites (75°C a 83°C).
   - `/gov on` / `/gov off`: Activación/desactivación del control automático con retorno defensivo a 100% al apagar.

---

## 3. Historias de Usuario (User Stories)

### US-1: Visibilidad de Modo en Telegram (Prioridad: P1)
**Como** operador de la granja,  
**Quiero** ver en `/fans` si cada minero está en modo Manual (y a qué porcentaje) o en modo Automático,  
**Para** no tener que abrir la interfaz web de cada equipo para verificar la política de enfriamiento.

**Criterios de Aceptación**:
- `/fans` muestra una columna o indicador claro: `Modo: Manual (100%)` o `Modo: Auto`.
- Se mantiene el formato compacto compatible con pantallas móviles.
- Si no hay datos de modo, se reporta `Modo: N/D` de forma segura sin excepciones.

---

### US-2: Reducción Acústica sin Downclocking (Prioridad: P1)
**Como** operador,  
**Quiero** que el sistema reduzca la velocidad de los ventiladores desde el 100% hacia el valor óptimo que mantenga los chips en ~82°C estables,  
**Para** disminuir drásticamente el ruido y desgaste sin activar jamás la reducción de hashrate por 84°C ni el reinicio por 85°C.

**Criterios de Aceptación**:
- El algoritmo evalúa la temperatura máxima de chip de cada minero en cada ciclo.
- Si la temperatura es $\le 80^\circ\text{C}$ y transcurrió el tiempo de asentamiento, reduce el PWM en $-2\%$.
- Si la temperatura está en el rango $[81.0^\circ\text{C}, 82.5^\circ\text{C}]$, mantiene el PWM sin cambios (*deadband* / banda muerta anti-oscilación).
- Si la temperatura sube a $[82.6^\circ\text{C}, 82.9^\circ\text{C}]$, incrementa el PWM en $+3\%$.
- Si la temperatura alcanza $\ge 83.0^\circ\text{C}$, salta inmediatamente al **100%** de PWM y emite una advertencia de saturación.
- Nunca desciende del piso mínimo configurado (70%).

---

### US-3: Operación a Prueba de Fallos (*Fail-Safe*) (Prioridad: P0)
**Como** operador,  
**Quiero** que cualquier fallo de red, timeout HTTP o caída de un minero deje los ventiladores en su último estado seguro y no interrumpa el monitor principal,  
**Para** garantizar que la monitorización crítica de hashrate y reinicios siga 100% activa.

**Criterios de Aceptación**:
- Las llamadas a la API REST de Vnish corren con timeouts estrictos (máximo 3.0s).
- Los errores HTTP se capturan silenciosamente en un bloque defensivo sin propagar excepciones al hilo principal de adquisición.
- Si el gobernador se desactiva manualmente o entra en error sostenido, devuelve preventivamente los ventiladores al 100%.

---

## 4. Requisitos No Funcionales y Restricciones Constitucionales

1. **Aislamiento de Hilos**: Las llamadas HTTP de control deben ejecutarse desacopladas o acotadas para no degradar el tick autoritativo de 30 segundos de la API 4028.
2. **Cero Tokens Filtrados**: Las contraseñas y tokens de sesión de Vnish jamás deben imprimirse en texto plano en los logs de producción (`out.log`, `err.log`).
3. **Persistencia de Configuración**: Las credenciales de acceso Vnish se configuran en `app/config.json` (archivo ignorado por git) bajo la sección `vnish_api`.
4. **Compatibilidad Firmware**: Compatible con Vnish v1.2.7, v1.2.8 y v1.2.9 en plataforma Bitmain Antminer S19j Pro.
