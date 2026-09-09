# Modelo de Datos: Spec 045 - Telegram Mobile Help Center

## 1. Entidades Principales

### 1.1 `CommandDefinition` (Inmutable)
Representa la definición canónica de un comando soportado por el bot:

```python
@dataclass(frozen=True)
class CommandDefinition:
    name: str                        # Nombre canónico (ej. 'silent', 'menu', 'fans')
    summary: str                     # Descripción breve para listados (<= 40 chars)
    usage: str                       # Sintaxis de uso (ej. '/silent <duración|off>')
    category: str                    # ID de categoría ('mon', 'thm', 'pwr', 'ctrl', 'diag')
    detail: List[str]                # Líneas explicativas detalladas
    examples: List[str]              # Ejemplos de uso real
    notes: List[str]                 # Advertencias o notas de contexto
    danger_level: str = "safe"       # "safe" o "danger"
    aliases: List[str] = field(default_factory=list)          # Aliases aceptados por el bot
    official_aliases: List[str] = field(default_factory=list) # Atajos oficiales (ej. '/rb<ID>')
```

### 1.2 `HelpCategory` (Inmutable)
Representa una agrupación temática de comandos para navegación táctil:

```python
@dataclass(frozen=True)
class HelpCategory:
    id: str                          # Identificador corto ('mon', 'thm', 'pwr', 'ctrl', 'diag')
    title: str                       # Título legible (ej. 'Monitoreo', 'Térmico & Fans')
    icon: str                        # Emoji identificador ('📊', '🌡️', '⚡', '🔄', '📜')
    description: str                 # Breve descripción de la categoría
    command_names: List[str]         # Nombres canónicos de los comandos pertenecientes
```

### 1.3 `HelpAction` (Parsed Callback Query)
Resultado estructurado del parseo seguro de `callback_data` con prefijo `help:`:

```python
@dataclass(frozen=True)
class HelpAction:
    kind: str                        # Tipo de acción: "nav", "cat", "cmd"
    target: str                      # Identificador de destino: "home", categoría ('thm') o comando ('silent')
```

---

## 2. Categorías Canónicas Definidas

| ID | Icono | Nombre | Comandos Incluidos |
|---|---|---|---|
| `mon` | 📊 | Monitoreo | `status`, `chart`, `digest`, `info` |
| `thm` | 🌡️ | Térmico & Fans | `fans`, `governor`, `silent` |
| `pwr` | ⚡ | Energía & Presets | `efficiency`, `presets`, `balancer`, `elevadores` |
| `ctrl` | 🔄 | Control & Acciones | `menu`, `reboot`, `reboot_no_ok`, `restart`, `confirm`, `snooze`, `unsnooze`, `snoozed` |
| `diag` | 📜 | Diagnóstico | `events`, `event`, `why`, `diagnose`, `health`, `quality`, `firmware`, `selftest`, `help` |

---

## 3. Formato de Callbacks y Presupuesto de Bytes

| Patrón | Ejemplo | Longitud (bytes) | Límite API | Margen |
|---|---|---|---|---|
| `help:nav:home` | `help:nav:home` | 13 | 64 | +51 bytes |
| `help:cat:<cat_id>` | `help:cat:thm` | 12 | 64 | +52 bytes |
| `help:cmd:<cmd_name>` | `help:cmd:reboot_no_ok` | 21 | 64 | +43 bytes |
