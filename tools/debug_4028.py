import json
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.network.cgminer_client import query_cgminer

DEFAULT_HOST = "192.168.100.23"
PORT = 4028

if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
    print("Uso: python tools\\debug_4028.py [IP]")
    print(f"Ejemplo: python tools\\debug_4028.py {DEFAULT_HOST}")
    sys.exit(0)

HOST = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST

res = query_cgminer(HOST, PORT, command="summary", timeout=5.0)
if res is None:
    print(f"ERROR: No se pudo conectar a {HOST}:{PORT} o respuesta invalida.")
    sys.exit(1)

clean = json.dumps(res, indent=2)
print("BYTES:", len(clean))
print("PREVIEW_TEXT:", clean[:300])
