# Checklist de Requisitos: Spec 039 - Vnish Thermal & Acoustic Fan Governor

## 1. Alineación Constitucional y de Seguridad
- [x] El target térmico (82.0°C) respeta los límites de hardware y deja margen con respecto al downclocking de Vnish (84.0°C) y el límite de autoboot (85.0°C).
- [x] Existe un piso mínimo infranqueable de ventilación (70%).
- [x] Existe un salto de emergencia inmediato al 100% de PWM ante picos térmicos ($\ge 83.0^\circ\text{C}$).
- [x] Las llamadas de red a la API REST de Vnish tienen timeouts estrictos (3.0s) y captura defensiva de errores para no afectar el bucle de monitoreo.
- [x] Los tokens y contraseñas jamás se exponen en texto plano en los logs de producción.

## 2. Visibilidad y UX
- [x] El comando `/fans` muestra el modo de ventilación (`Manual: 100%` vs `Auto`) de manera concisa y clara.
- [x] El comando `/gov` permite auditar en cualquier momento la última decisión tomada por el regulador.
- [x] El gobernador puede apagarse en caliente devolviendo los ventiladores al 100% de forma segura.

## 3. Calidad y Concurrencia
- [x] Toda la lógica de decisión térmica se aísla en una función pura libre de I/O para pruebas deterministas.
- [x] El estado persistido en `state.json` respeta `state_lock` y copias inmutables.
- [x] Los tests cubren timeouts de red, errores de autenticación y variaciones térmicas bruscas.
