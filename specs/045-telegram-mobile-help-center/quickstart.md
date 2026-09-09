# Quickstart: Spec 045 - Telegram Mobile Help Center

## Verificación Rápida y Uso en Desarrollo

### 1. Importar y Consultar el Help Center
```python
from app.telegram.help_center import (
    lookup_command,
    parse_help_callback,
    render_help_home,
    render_help_category,
    render_help_command_detail,
)

# 1. Obtener la vista Home
text, keyboard = render_help_home()
print("Caracteres Home:", len(text))

# 2. Navegar a una categoría
text_cat, kb_cat = render_help_category("thm")
print("Categoría Térmico:", text_cat[:100])

# 3. Consultar detalle de un comando
text_cmd, kb_cmd = render_help_command_detail("silent")
print("Detalle /silent:", text_cmd[:100])

# 4. Parsear un callback query recibido
action = parse_help_callback("help:cat:thm")
assert action.kind == "cat"
assert action.target == "thm"
```

### 2. Ejecutar Tests de Verificación
```powershell
& ".\.venv\Scripts\python.exe" -m unittest tests.test_help_center -v
```

### 3. Verificar Toda la Suite
```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -s tests -p "test_*.py"
```
