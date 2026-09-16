import json
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.network.cgminer_client import query_cgminer

DEFAULT_HOST = "192.168.100.23"
PORT = 4028

def debug_miner(host: str = DEFAULT_HOST, port: int = PORT, timeout: float = 5.0) -> int:
    res = query_cgminer(host, port, command="summary", timeout=timeout)
    if res is None:
        print(f"ERROR: No se pudo conectar a {host}:{port} o respuesta invalida.")
        return 1

    clean = json.dumps(res, indent=2)
    print("BYTES:", len(clean))
    print("PREVIEW_TEXT:", clean[:300])
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("Uso: python tools\\debug_4028.py [IP]")
        print(f"Ejemplo: python tools\\debug_4028.py {DEFAULT_HOST}")
        return 0

    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
    return debug_miner(host, PORT)


if __name__ == "__main__":
    sys.exit(main())
