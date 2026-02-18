import socket
import sys

DEFAULT_HOST = "192.168.100.23"
PORT = 4028
CMD = b'{"command":"summary"}\n'

if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
    print("Uso: python app\\debug_4028.py [IP]")
    print(f"Ejemplo: python app\\debug_4028.py {DEFAULT_HOST}")
    sys.exit(0)

HOST = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST

try:
    s = socket.create_connection((HOST, PORT), timeout=5)
    s.sendall(CMD)
    s.settimeout(5)
except Exception as exc:
    print(f"ERROR: No se pudo conectar a {HOST}:{PORT} ({exc})")
    sys.exit(1)

data = b""
try:
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        data += chunk
except Exception:
    pass
finally:
    s.close()

clean = data.replace(b"\x00", b"")
print("BYTES:", len(data))
print("PREVIEW_REPR:", repr(clean[:300]))
print("PREVIEW_TEXT:", clean[:300].decode("utf-8", "ignore"))
