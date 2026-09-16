"""Inter-process communication (IPC) for Miner Alerts monitoring and watchdog."""

from app.ipc.watchdog_pipe import (
    IPCPingResult,
    WatchdogIPCClient,
    WatchdogIPCServer,
    dump_thread_frames,
)

__all__ = [
    "IPCPingResult",
    "WatchdogIPCClient",
    "WatchdogIPCServer",
    "dump_thread_frames",
]
