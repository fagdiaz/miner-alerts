# Contrato de Interfaz: Help Center API (Spec 045)

## 1. Módulo `app.telegram.help_center`

### 1.1 Funciones de Consulta y Navegación

```python
def lookup_command(needle: str) -> Optional[CommandDefinition]:
    """Busca un comando por nombre canónico o por cualquiera de sus aliases.
    
    Insensible a mayúsculas/minúsculas y barras iniciales (ej. '/silent' -> 'silent').
    Retorna CommandDefinition si se encuentra, o None si no existe.
    """
```

```python
def parse_help_callback(raw_data: str) -> Optional[HelpAction]:
    """Valida y descompone un callback_data que inicia con 'help:'.
    
    Reglas:
    - Longitud en bytes <= 64 (rechaza si es mayor).
    - Gramática estricta:
      * 'help:nav:home' -> HelpAction(kind="nav", target="home")
      * 'help:cat:<cat_id>' -> HelpAction(kind="cat", target=<cat_id>)
      * 'help:cmd:<cmd_name>' -> HelpAction(kind="cmd", target=<cmd_name>)
    - Retorna None si no cumple la gramática o hace referencia a una categoría/comando inexistente.
    """
```

```python
def render_help_home() -> Tuple[str, Dict[str, Any]]:
    """Genera la vista principal del Centro de Ayuda Mobile-First.
    
    Retorna:
    - text: Texto estructurado con viñetas, líneas <= 32 cols visibles, total <= 3600 chars.
    - markup: Diccionario Telegram con InlineKeyboardMarkup conteniendo botones de categorías.
    """
```

```python
def render_help_category(cat_key: str) -> Tuple[str, Dict[str, Any]]:
    """Genera el submenú de una categoría temática.
    
    Retorna:
    - text: Lista compacta de comandos de la categoría con uso y resumen.
    - markup: InlineKeyboardMarkup con botones táctiles para cada comando y botón de retorno.
    """
```

```python
def render_help_command_detail(cmd_name: str) -> Tuple[str, Dict[str, Any]]:
    """Genera la tarjeta vertical detallada de un comando individual.
    
    Retorna:
    - text: Descripción, sintaxis de uso, ejemplos, notas y advertencias.
    - markup: InlineKeyboardMarkup con [ ⬅️ Categoría ], [ 📖 Ayuda ] y [ 📱 Menú ].
    """
```

### 1.2 Funciones de Sanitización y Ancho

```python
def strip_markdown(text: str) -> str:
    """Elimina etiquetas Markdown (*, _, `, [) para calcular ancho visual real."""
```

```python
def visible_line_width(line: str) -> int:
    """Calcula la cantidad de caracteres visibles de una línea descartando tags."""
```

```python
def escape_markdown(text: str) -> str:
    """Escapa caracteres conflictivos para parse_mode='Markdown' (*, _, `, [)."""
```
