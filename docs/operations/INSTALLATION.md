# Instalación y entorno Windows

> Tipo: procedimiento · Revisión: 2026-11-16 · Ámbito: instancia nueva o entorno de desarrollo.

## Precondiciones

Windows, acceso al checkout y Python compatible con las dependencias del proyecto.
La última validación registrada usó Python 3.14; el proyecto no mantiene aquí una
matriz certificada para todas las versiones anteriores. Los mineros exponen API 4028
y endpoints HTTP/WS del firmware; Hashcore requiere su instalación local cuando se use.

Comprobar primero si existe un servicio activo:

```powershell
Get-Service -Name MinerAlerts -ErrorAction SilentlyContinue
```

No lanzar una segunda instancia mientras el servicio esté ejecutándose. La consulta
al SCM puede requerir privilegios; una respuesta de acceso denegado no demuestra ausencia.

## Preparar un entorno nuevo

Los comandos se ejecutan desde la raíz del repositorio. No recrear el virtualenv de
producción como parte de una revisión documental.

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Para pruebas de desarrollo se requiere pytest y los plugins usados por la suite,
incluido pytest-subtests. Las dependencias de observabilidad están separadas en
[requirements-observability.txt](../../requirements-observability.txt).

## Configuración inicial

Solo en un entorno sin configuración local previa:

```powershell
if (Test-Path -LiteralPath .\app\config.json) { throw 'Ya existe configuración local: conservarla.' }
Copy-Item -LiteralPath .\app\config.example.json -Destination .\app\config.json
```

Completar localmente mineros y credenciales. Para una primera validación aislada,
configurar `qa_mode=true` y `qa_allow_real_actions=false`; comprobar el modo efectivo
en el log de arranque. QA con acciones habilitadas puede actuar sobre equipos reales.
Ver [configuración y precedencia](CONFIGURATION.md).

## Validaciones sin mineros

```powershell
& .\.venv\Scripts\python.exe -m py_compile app\miner_monitor.py
& .\.venv\Scripts\python.exe tools\miner_diagnostics.py --config app\config.example.json --out diagnostics\dry-run --dry-run
```

El segundo comando escribe reportes de diagnóstico, sin consultas a equipos. La
compilación comprueba sintaxis; no certifica Telegram, red ni seguridad de planta.

## Ejecución manual controlada

Solo cuando no exista una instancia activa y se hayan revisado configuración y QA:

```powershell
& .\.venv\Scripts\python.exe app\miner_monitor.py
```

La instalación como servicio usa NSSM/SCM y los parámetros reales del host. No hay
un instalador universal de servicio certificado por este manual; no registrar otra
copia para resolver un problema de rutas. Para recargas ver [RUNBOOK](RUNBOOK.md).

## Problemas de entorno

- Un padre/hijo Python no demuestra por sí solo doble instancia; contrastar mutex,
  proceso efectivo y heartbeat.
- Si el editor no resuelve imports, seleccionar el intérprete del virtualenv.
- Si PowerShell no inicia, no interpretar un proceso creado como comando ejecutado.
  Registrar el bloqueo y usar comprobaciones equivalentes por CMD/Python cuando sean
  suficientes. No declarar un script ejecutado por haber solicitado su lanzamiento.
- No borrar state.json como limpieza general: conserva cooldowns y contexto operativo.
