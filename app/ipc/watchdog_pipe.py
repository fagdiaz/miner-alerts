"""High-frequency local IPC channel between Miner Alerts monitor and watchdog.

Provides Named Pipe transport on Windows NT with an explicit permissive SDDL
security descriptor, and automatic fallback to a local TCP loopback socket.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime
import logging
import math
import os
from pathlib import Path
import socket
import sys
import threading
import time
import traceback
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger("miner_alerts.ipc")

DEFAULT_PIPE_NAME = r"\\.\pipe\MinerAlertsWatchdog"
DEFAULT_FALLBACK_PORT = 4029
DEFAULT_TIMEOUT_SECONDS = 0.1
DEFAULT_MAX_DEADLOCK_TICK_AGE_S = 60.0

# Windows Native API Constants
PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
PIPE_UNLIMITED_INSTANCES = 255
INVALID_HANDLE_VALUE = -1
ERROR_PIPE_CONNECTED = 535
ERROR_BROKEN_PIPE = 109
ERROR_NO_DATA = 232
ERROR_SEM_TIMEOUT = 121
ERROR_FILE_NOT_FOUND = 2
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
SDDL_REVISION_1 = 1


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


def _create_pipe_security_attributes() -> Tuple[Optional[SECURITY_ATTRIBUTES], Optional[int]]:
    """Creates a SECURITY_ATTRIBUTES structure with SDDL D:(A;;GRGW;;;WD).

    Allows read/write access to Everyone local, preventing ERROR_ACCESS_DENIED (5)
    when monitor runs as LocalSystem / service and watchdog runs as a local user.
    Returns (sa_struct, p_sd_address). Caller must LocalFree(p_sd_address) when done.
    """
    if os.name != "nt":
        return None, None
    try:
        advapi32 = getattr(ctypes.windll, "advapi32", None)
        if not advapi32:
            return None, None
        p_sd = wintypes.LPVOID()
        sddl = "D:(A;;GRGW;;;WD)"
        converted = advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, SDDL_REVISION_1, ctypes.byref(p_sd), None
        )
        if converted and p_sd.value:
            sa = SECURITY_ATTRIBUTES()
            sa.nLength = ctypes.sizeof(SECURITY_ATTRIBUTES)
            sa.lpSecurityDescriptor = p_sd
            sa.bInheritHandle = False
            return sa, p_sd.value
    except Exception as exc:
        logger.warning("Failed to create SDDL security descriptor for pipe: %s", exc)
    return None, None


def _free_security_descriptor(p_sd_value: Optional[int]) -> None:
    if os.name == "nt" and p_sd_value:
        try:
            kernel32 = getattr(ctypes.windll, "kernel32", None)
            if kernel32:
                kernel32.LocalFree(wintypes.LPVOID(p_sd_value))
        except Exception:
            pass


def dump_thread_frames(output_dir: Optional[Path] = None) -> Path:
    """Captures stack traces of all active Python threads without interrupting execution.

    Writes to deadlock_forensics_<timestamp>.log in output_dir.
    """
    if output_dir is None:
        output_dir = Path("logs")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = output_dir / f"deadlock_forensics_{timestamp}.log"

    frames = sys._current_frames()
    threads_by_ident = {t.ident: t for t in threading.enumerate()}

    with open(target, "w", encoding="utf-8") as f:
        f.write(f"=== DEADLOCK FORENSICS DUMP - {datetime.now().isoformat()} ===\n")
        f.write(f"Active threads count: {len(frames)}\n\n")
        for thread_id, frame in frames.items():
            thread_obj = threads_by_ident.get(thread_id)
            thread_name = thread_obj.name if thread_obj else "Unknown"
            daemon_str = f"daemon={thread_obj.daemon}" if thread_obj else "daemon=unknown"
            f.write(f"\n--- Thread ID: {thread_id} | Name: {thread_name} | {daemon_str} ---\n")
            traceback.print_stack(frame, file=f)

    return target


class IPCPingResult(tuple):
    """Result of an IPC ping operation.

    Can be unpacked as a 4-tuple: (ok, tick_sequence, uptime_s, error)
    or accessed via named properties.
    """

    def __new__(
        cls,
        ok: bool,
        tick_sequence: Optional[int] = None,
        uptime_s: Optional[float] = None,
        error: Optional[str] = None,
        last_tick_elapsed_s: Optional[float] = None,
        nonce: Optional[str] = None,
        transport: Optional[str] = None,
    ) -> "IPCPingResult":
        instance = super().__new__(cls, (ok, tick_sequence, uptime_s, error))
        instance.ok = ok
        instance.tick_sequence = tick_sequence
        instance.uptime_s = uptime_s
        instance.error = error
        instance.last_tick_elapsed_s = last_tick_elapsed_s
        instance.nonce = nonce
        instance.transport = transport
        return instance


class WatchdogIPCServer:
    """Lightweight, low-overhead IPC server for monitor health polling.

    Runs in a dedicated daemon thread without acquiring supervisory locks.
    """

    def __init__(
        self,
        pipe_name: str = DEFAULT_PIPE_NAME,
        fallback_port: int = DEFAULT_FALLBACK_PORT,
        timeout_s: float = DEFAULT_TIMEOUT_SECONDS,
        get_status_callback: Optional[Callable[[], Tuple[int, float, float]]] = None,
        forensics_dir: Optional[Path] = None,
    ) -> None:
        self.pipe_name = pipe_name
        self.fallback_port = fallback_port
        self.timeout_s = max(0.01, float(timeout_s))
        self.get_status_callback = get_status_callback
        self.forensics_dir = forensics_dir or Path("logs")

        self._stopped = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._pipe_handle: Optional[int] = None
        self._fallback_mode: bool = False
        self._active_transport: str = "none"
        self._started = threading.Event()

    @property
    def active_transport(self) -> str:
        return self._active_transport

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stopped.is_set()

    def start(self) -> None:
        """Starts the IPC server daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stopped.clear()
        self._started.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="WatchdogIPCServer",
            daemon=True,
        )
        self._thread.start()
        self._started.wait(timeout=1.0)

    def stop(self, timeout_s: float = 0.5) -> None:
        """Gracefully stops the server in <200 ms using a wake-up connect unblock."""
        if self._stopped.is_set():
            return
        self._stopped.set()
        self._wake_up_unblock()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout_s)

    def _wake_up_unblock(self) -> None:
        """Performs a non-blocking local connection to unblock pending ConnectNamedPipe or accept()."""
        if self._active_transport == "pipe" and os.name == "nt":
            try:
                kernel32 = getattr(ctypes.windll, "kernel32", None)
                if kernel32:
                    h_wake = kernel32.CreateFileW(
                        self.pipe_name,
                        GENERIC_READ | GENERIC_WRITE,
                        0,
                        None,
                        OPEN_EXISTING,
                        0,
                        None,
                    )
                    if h_wake != INVALID_HANDLE_VALUE:
                        kernel32.CloseHandle(h_wake)
            except Exception:
                pass
        elif self._active_transport == "socket" or self._fallback_mode or os.name != "nt":
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.05)
                    sock.connect(("127.0.0.1", self.fallback_port))
            except Exception:
                pass

    def _run(self) -> None:
        """Primary server execution loop."""
        if os.name == "nt":
            try:
                self._run_named_pipe()
                return
            except Exception as exc:
                logger.warning(
                    "Named pipe initialization failed (%s); switching to loopback socket fallback",
                    exc,
                )
        self._run_socket_fallback()

    def _format_status_response(self, nonce: str) -> str:
        tick_seq = 0
        uptime_s = 0.0
        last_tick_s = 0.0
        if self.get_status_callback:
            try:
                cb_res = self.get_status_callback()
                if cb_res and len(cb_res) >= 3:
                    tick_seq = int(cb_res[0])
                    raw_up = float(cb_res[1])
                    uptime_s = time.time() - raw_up if raw_up > 1_000_000_000 else raw_up
                    last_tick_s = float(cb_res[2])
            except Exception as exc:
                logger.debug("Error in get_status_callback: %s", exc)
        return f"PONG {nonce} {tick_seq} {uptime_s:.2f} {last_tick_s:.3f}\n"

    def _handle_command(self, raw_line: str) -> str:
        clean = raw_line.replace("\x00", "").strip()
        lines = [ln.strip() for ln in clean.splitlines() if ln.strip()]
        if not lines:
            return "ERR empty_command\n"
        line = lines[0]
        parts = line.split()
        cmd = parts[0].upper()
        if cmd == "PING":
            nonce = parts[1] if len(parts) > 1 else "-"
            return self._format_status_response(nonce)
        elif cmd in ("DUMP", "FORENSICS"):
            try:
                log_path = dump_thread_frames(self.forensics_dir)
                return f"DUMPED {log_path}\n"
            except Exception as exc:
                return f"ERR dump_failed {exc}\n"
        return "ERR unknown_command\n"

    def _run_named_pipe(self) -> None:
        kernel32 = ctypes.windll.kernel32
        sa, p_sd = _create_pipe_security_attributes()
        try:
            h_pipe = kernel32.CreateNamedPipeW(
                self.pipe_name,
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                1,  # Single server pipe instance
                4096,
                4096,
                int(self.timeout_s * 1000),
                ctypes.byref(sa) if sa else None,
            )
            if h_pipe == INVALID_HANDLE_VALUE:
                err = kernel32.GetLastError()
                raise OSError(f"CreateNamedPipeW failed with error code {err}")

            self._pipe_handle = h_pipe
            self._active_transport = "pipe"
            self._started.set()

            while not self._stopped.is_set():
                connected = kernel32.ConnectNamedPipe(h_pipe, None)
                if not connected:
                    err = kernel32.GetLastError()
                    if err != ERROR_PIPE_CONNECTED:
                        # Reset pipe handle in case of ERROR_NO_DATA or client aborted early
                        kernel32.DisconnectNamedPipe(h_pipe)
                        if self._stopped.is_set():
                            break
                        time.sleep(0.01)
                        continue

                if self._stopped.is_set():
                    kernel32.DisconnectNamedPipe(h_pipe)
                    break

                # Read request from client
                buf = ctypes.create_string_buffer(1024)
                bytes_read = wintypes.DWORD()
                ok = kernel32.ReadFile(
                    h_pipe,
                    buf,
                    1024,
                    ctypes.byref(bytes_read),
                    None,
                )
                if ok and bytes_read.value > 0:
                    raw_text = buf.raw[: bytes_read.value].decode("utf-8", errors="replace")
                    response = self._handle_command(raw_text)
                    resp_bytes = response.encode("utf-8")
                    written = wintypes.DWORD()
                    kernel32.WriteFile(
                        h_pipe,
                        resp_bytes,
                        len(resp_bytes),
                        ctypes.byref(written),
                        None,
                    )
                    kernel32.FlushFileBuffers(h_pipe)

                kernel32.DisconnectNamedPipe(h_pipe)
        finally:
            if self._pipe_handle and self._pipe_handle != INVALID_HANDLE_VALUE:
                kernel32.CloseHandle(self._pipe_handle)
                self._pipe_handle = None
            _free_security_descriptor(p_sd)
            self._active_transport = "none"

    def _run_socket_fallback(self) -> None:
        self._fallback_mode = True
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("127.0.0.1", self.fallback_port))
        server_sock.listen(5)
        server_sock.settimeout(0.2)
        self._active_transport = "socket"
        self._started.set()

        try:
            while not self._stopped.is_set():
                try:
                    conn, _ = server_sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                with conn:
                    if self._stopped.is_set():
                        break
                    conn.settimeout(self.timeout_s)
                    try:
                        data = conn.recv(1024)
                        if data:
                            raw_text = data.decode("utf-8", errors="replace")
                            response = self._handle_command(raw_text)
                            conn.sendall(response.encode("utf-8"))
                    except Exception as exc:
                        logger.debug("Socket client handler error: %s", exc)
        finally:
            try:
                server_sock.close()
            except Exception:
                pass
            self._active_transport = "none"


class WatchdogIPCClient:
    """Client for high-frequency watchdog health queries with strict timeouts."""

    def __init__(
        self,
        pipe_name: str = DEFAULT_PIPE_NAME,
        fallback_port: int = DEFAULT_FALLBACK_PORT,
        timeout_s: float = DEFAULT_TIMEOUT_SECONDS,
        force_transport: Optional[str] = None,
    ) -> None:
        self.pipe_name = pipe_name
        self.fallback_port = fallback_port
        self.timeout_s = max(0.01, float(timeout_s))
        self.force_transport = force_transport

    def ping(self, nonce: Optional[str] = None) -> IPCPingResult:
        """Sends PING to monitor and parses response in <= timeout_s."""
        if nonce is None:
            nonce = f"{int(time.time() * 1000) % 1_000_000:06d}"

        # 1. Pipe transport attempt
        if self.force_transport != "socket" and os.name == "nt":
            pipe_res = self._ping_pipe(nonce)
            if pipe_res.ok or self.force_transport == "pipe":
                return pipe_res

        # 2. Socket transport fallback
        if self.force_transport != "pipe":
            return self._ping_socket(nonce)

        return IPCPingResult(ok=False, nonce=nonce, error="No valid transport available")

    def request_forensics_dump(self) -> Tuple[bool, Optional[str]]:
        """Requests monitor to perform an in-process thread forensics dump."""
        if self.force_transport != "socket" and os.name == "nt":
            ok, path_or_err = self._send_cmd_pipe("DUMP\n")
            if ok or self.force_transport == "pipe":
                return ok, path_or_err
        if self.force_transport != "pipe":
            return self._send_cmd_socket("DUMP\n")
        return False, "No valid transport available"

    def _ping_pipe(self, nonce: str) -> IPCPingResult:
        kernel32 = ctypes.windll.kernel32
        timeout_ms = int(self.timeout_s * 1000)
        ready = kernel32.WaitNamedPipeW(self.pipe_name, timeout_ms)
        if not ready:
            err = kernel32.GetLastError()
            return IPCPingResult(ok=False, nonce=nonce, transport="pipe", error=f"pipe_wait_timeout:{err}")

        h_client = kernel32.CreateFileW(
            self.pipe_name,
            GENERIC_READ | GENERIC_WRITE,
            0,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if h_client == INVALID_HANDLE_VALUE:
            err = kernel32.GetLastError()
            return IPCPingResult(ok=False, nonce=nonce, transport="pipe", error=f"pipe_open_error:{err}")

        try:
            req = f"PING {nonce}\n".encode("utf-8")
            written = wintypes.DWORD()
            ok_w = kernel32.WriteFile(h_client, req, len(req), ctypes.byref(written), None)
            if not ok_w:
                return IPCPingResult(ok=False, nonce=nonce, transport="pipe", error="pipe_write_failed")

            # Non-blocking poll with PeekNamedPipe
            start_t = time.perf_counter()
            deadline = start_t + self.timeout_s
            bytes_avail = wintypes.DWORD()

            while time.perf_counter() < deadline:
                peek_ok = kernel32.PeekNamedPipe(
                    h_client, None, 0, None, ctypes.byref(bytes_avail), None
                )
                if not peek_ok:
                    break
                if bytes_avail.value > 0:
                    break
                time.sleep(0.002)

            if bytes_avail.value <= 0:
                return IPCPingResult(ok=False, nonce=nonce, transport="pipe", error="pipe_read_timeout")

            buf = ctypes.create_string_buffer(bytes_avail.value + 1)
            bytes_read = wintypes.DWORD()
            ok_r = kernel32.ReadFile(h_client, buf, bytes_avail.value, ctypes.byref(bytes_read), None)
            if not ok_r or bytes_read.value <= 0:
                return IPCPingResult(ok=False, nonce=nonce, transport="pipe", error="pipe_read_failed")

            raw_resp = buf.raw[: bytes_read.value].decode("utf-8", errors="replace")
            return self._parse_pong_response(raw_resp, nonce, "pipe")
        finally:
            kernel32.CloseHandle(h_client)

    def _ping_socket(self, nonce: str) -> IPCPingResult:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout_s)
                sock.connect(("127.0.0.1", self.fallback_port))
                sock.sendall(f"PING {nonce}\n".encode("utf-8"))
                resp_bytes = sock.recv(1024)
                if not resp_bytes:
                    return IPCPingResult(ok=False, nonce=nonce, transport="socket", error="socket_empty_response")
                raw_resp = resp_bytes.decode("utf-8", errors="replace")
                return self._parse_pong_response(raw_resp, nonce, "socket")
        except socket.timeout:
            return IPCPingResult(ok=False, nonce=nonce, transport="socket", error="socket_timeout")
        except Exception as exc:
            return IPCPingResult(ok=False, nonce=nonce, transport="socket", error=f"socket_conn_error:{type(exc).__name__}")

    def _parse_pong_response(self, raw_resp: str, expected_nonce: str, transport: str) -> IPCPingResult:
        parts = raw_resp.strip().split()
        if len(parts) < 2 or parts[0] != "PONG":
            return IPCPingResult(ok=False, nonce=expected_nonce, transport=transport, error=f"invalid_response:{raw_resp.strip()}")
        resp_nonce = parts[1]
        if resp_nonce != expected_nonce:
            return IPCPingResult(ok=False, nonce=expected_nonce, transport=transport, error=f"nonce_mismatch:{resp_nonce}!={expected_nonce}")

        tick_seq = (
            int(parts[2])
            if len(parts) > 2 and (parts[2].isdigit() or parts[2].lstrip("-").isdigit())
            else 0
        )
        try:
            uptime_s = float(parts[3]) if len(parts) > 3 else 0.0
            if not math.isfinite(uptime_s):
                uptime_s = 0.0
        except ValueError:
            uptime_s = 0.0
        try:
            last_tick_s = float(parts[4]) if len(parts) > 4 else 0.0
            if not math.isfinite(last_tick_s):
                last_tick_s = 0.0
        except ValueError:
            last_tick_s = 0.0

        return IPCPingResult(
            ok=True,
            tick_sequence=tick_seq,
            uptime_s=uptime_s,
            last_tick_elapsed_s=last_tick_s,
            nonce=resp_nonce,
            transport=transport,
        )

    def _send_cmd_pipe(self, cmd: str) -> Tuple[bool, Optional[str]]:
        kernel32 = ctypes.windll.kernel32
        timeout_ms = int(self.timeout_s * 1000)
        if not kernel32.WaitNamedPipeW(self.pipe_name, timeout_ms):
            return False, "pipe_unavailable"
        h_client = kernel32.CreateFileW(
            self.pipe_name,
            GENERIC_READ | GENERIC_WRITE,
            0,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if h_client == INVALID_HANDLE_VALUE:
            return False, f"pipe_open_error:{kernel32.GetLastError()}"
        try:
            cmd_bytes = cmd.encode("utf-8")
            written = wintypes.DWORD()
            if not kernel32.WriteFile(h_client, cmd_bytes, len(cmd_bytes), ctypes.byref(written), None):
                return False, "pipe_write_failed"

            start_t = time.perf_counter()
            deadline = start_t + self.timeout_s * 5
            bytes_avail = wintypes.DWORD()
            while time.perf_counter() < deadline:
                if not kernel32.PeekNamedPipe(h_client, None, 0, None, ctypes.byref(bytes_avail), None):
                    break
                if bytes_avail.value > 0:
                    break
                time.sleep(0.005)

            if bytes_avail.value <= 0:
                return False, "pipe_read_timeout"

            buf = ctypes.create_string_buffer(bytes_avail.value + 1)
            bytes_read = wintypes.DWORD()
            if not kernel32.ReadFile(h_client, buf, bytes_avail.value, ctypes.byref(bytes_read), None):
                return False, "pipe_read_failed"
            resp = buf.raw[: bytes_read.value].decode("utf-8", errors="replace").strip()
            if resp.startswith("DUMPED "):
                return True, resp[7:].strip()
            return False, resp
        finally:
            kernel32.CloseHandle(h_client)

    def _send_cmd_socket(self, cmd: str) -> Tuple[bool, Optional[str]]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.timeout_s * 5)
                sock.connect(("127.0.0.1", self.fallback_port))
                sock.sendall(cmd.encode("utf-8"))
                resp = sock.recv(1024).decode("utf-8", errors="replace").strip()
                if resp.startswith("DUMPED "):
                    return True, resp[7:].strip()
                return False, resp
        except Exception as exc:
            return False, f"socket_error:{type(exc).__name__}"
