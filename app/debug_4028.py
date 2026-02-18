import socket
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.100.23"
PORT = 4028
CMD = b'{"command":"summary"}\n'

s = socket.create_connection((HOST, PORT), timeout=5)
s.sendall(CMD)
s.settimeout(5)

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
