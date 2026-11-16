# Flujo de trabajo y validación

> Tipo: procedimiento de desarrollo · Revisión: 2026-11-16.

## Entrar en contexto

Leer [AGENTS](../../AGENTS.md), [feature.json](../../.specify/feature.json), los
artefactos de esa feature y la [constitución](../../.specify/memory/constitution.md).
Después consultar [backlog](../speckit/ROADMAP.md), [secuencia](../speckit/SPEC_PROGRAM.md)
y [ventanas](../speckit/DELIVERY_PLAN.md). La evidencia reciente prevalece sobre una
tarea marcada o una cifra antigua de un README.

## Delimitar el trabajo

Mantener una sola spec en implementación. Diseñar tareas futuras no autoriza su
activación. Antes de código de producción, revisar estados compartidos, locks, hilos,
contratos, consumidores y efectos sobre planta. Conservar una ruta de rollback.

Los cambios solo documentales pueden organizar referencias sin tocar el runtime o
activar otra spec. Registrar su alcance y comprobar que código, config y specs
excluidas conservan sus hashes. La bitácora completa no se elimina ni se trunca.

## Validación proporcional

| Cambio | Comprobación pertinente |
|---|---|
| Índices/documentación | Enlaces, anchors, codificación, rutas, preservación y diffcheck |
| Python del monitor | py_compile y pruebas de contratos/regresión afectados |
| Telegram | Respuestas, cola, errores y diagnóstico de comandos cuando aplique |
| Restart/reboot/QA | Pruebas sin actuación, casos negativos, tiempos y permisos; producción controlada solo dentro de autorización |
| Configuración | Ejemplo y docs alineados; configuración local solo si se pidió su aplicación |
| Persistencia/backup | Fallos, concurrencia y restore en staging, nunca sobre base viva por defecto |

Comprobaciones de código desde la raíz, cuando el cambio las requiera:

```powershell
& .\.venv\Scripts\python.exe -m py_compile app\miner_monitor.py
& .\.venv\Scripts\python.exe -m pytest -q
```

La suite usa pytest y plugins del entorno de desarrollo. No ejecutar instancias
productivas, reinicios o pruebas eléctricas para validar documentación.

Para cambiosTelegram, habilitar DBG_TELEGRAM y DBG_TELEGRAM_COMMANDS_ONLY en un
entorno de prueba aislado cuando corresponda; no alterar por defecto el entorno del
servicio en ejecución. Registrar la versión exacta validada y no reutilizar un PASS
si el código afectado cambió después.

## Estabilización y release

Los cambios de producción deben pasar [speckit-stabilize](../../.agents/skills/speckit-stabilize/SKILL.md)
antes del cierre manual. La firma real del script usa parámetros object con valores
booleanos explícitos:

```powershell
& .\.agents\skills\speckit-stabilize\scripts\preflight_stabilize.ps1 -RunTests $true -CheckFleet $true
```

El script es apoyo, no sustituto de revisión. Si no puede ejecutarse, indicar qué
falló y qué controles equivalentes se hicieron; no certificar su ejecución. Una
dependencia bloqueada, prueba fallida o evidencia de seguridad pendiente impide
presentar el gate como aprobado. No reiniciar servicio por una edición de docs.

[tools/release_audit.py](../../tools/release_audit.py) corresponde al gate histórico
Spec 029; no es un certificador universal de cualquier versión actual. Contrastar
su alcance antes de interpretar su resultado.

## Git y evidencia

Commit y push son manuales y acotados a la feature. Las extensiones no sustituyen la
autorización del usuario ni vuelven publicable una config o estado privado. Una
aprobación para cerrar una spec no se extrapola a todos los cierres futuros.

Antes de publicar, revisar cambios, secretos, artefactos pertinentes y evidencia.
Actualizar tareas, backlog y documentación cuando cambie el estado. Las entradas
nuevas de DEVELOPMENT_LOG son aditivas y newest-first; no ordenar o reemplazar toda
la bitácora como efecto de un comando. Su [índice externo](../audit/DEVELOPMENT_LOG_INDEX.md)
facilita navegar el histórico preservado.

Después de una activación autorizada, verificar proceso/config cargados, salud y
ventana real de observación. D+1 y causa física no se aprueban por tests. Registrar
pendientes y dejar [prompt.txt](../../prompt.txt) listo para continuar con el modelo
y alcance elegidos por el usuario.
