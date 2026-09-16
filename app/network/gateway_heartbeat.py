"""Gateway Heartbeat Worker — Detección de pérdida de red local (Spec 067).

Hilo daemon ultraliviano que verifica conectividad TCP al gateway/router local
cada ``interval_s`` segundos. Expone estado atómico para que el monitor principal
pueda suprimir alertas de desconexión durante microcortes de switch o parpadeos
de access point (Network Storm Suppression).

Diseño:
  - Hilo daemon independiente: nunca bloquea el bucle principal ni el GIL.
  - Timeout de conexión: 50 ms (configurable). No acumula latencia en el main loop.
  - Cierre de socket explícito en ``finally`` para evitar leaks de handles en Windows.
  - Fallback a puerto alternativo (por defecto: 53/DNS) si el puerto primario es rechazado.
  - ``try ... except Exception`` de nivel superior en ``_run()`` para contención total.
  - Zero dependencias externas: usa únicamente ``socket`` y ``threading`` de la stdlib.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class GatewayHeartbeatWorker:
    """Verifica conectividad TCP al gateway local y expone estado GIL-safe.

    Atributos de estado (lectura directa, sin lock necesario en CPython):
        gateway_online (bool): True si el último intento de conexión fue exitoso.
        last_gateway_loss_ts (Optional[float]): timestamp monotónico del último fallo.
        last_gateway_ok_ts (float): timestamp monotónico del último éxito.
        consecutive_failures (int): fallos consecutivos desde el último éxito.
    """

    def __init__(
        self,
        host: str = "192.168.100.1",
        port: int = 80,
        interval_s: float = 5.0,
        connect_timeout_s: float = 0.05,
        fallback_port: int = 53,
        name: str = "GatewayHeartbeat",
    ) -> None:
        self._host = host
        self._port = port
        self._fallback_port = fallback_port
        self._interval_s = max(1.0, interval_s)
        self._timeout = max(0.01, connect_timeout_s)
        self._name = name

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Exposed state — atomic bool/int/float in CPython (GIL-safe)
        self.gateway_online: bool = True  # Assume online until first check
        self.last_gateway_loss_ts: Optional[float] = None
        self.last_gateway_ok_ts: float = time.monotonic()
        self.consecutive_failures: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Arranca el hilo daemon de latido. Idempotente si ya está corriendo."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=self._name,
        )
        self._thread.start()
        logger.debug("GatewayHeartbeatWorker started host=%s port=%d", self._host, self._port)

    def stop(self) -> None:
        """Señaliza parada (best-effort — el hilo es daemon y muere con el proceso)."""
        self._stop_event.set()

    def is_recently_lost(self, within_seconds: float = 15.0) -> bool:
        """True si el gateway estuvo o está caído en los últimos ``within_seconds`` segundos.

        Se usa como guard para la ventana de supresión de tormentas de red:
            - Si ``gateway_online`` es False ahora → True.
            - Si ``gateway_online`` se recuperó pero la pérdida ocurrió dentro
              de la ventana → True (absorbe el transitorio).
            - Si nunca hubo pérdida → False.
        """
        if not self.gateway_online:
            return True
        if self.last_gateway_loss_ts is None:
            return False
        elapsed_since_recovery = time.monotonic() - self.last_gateway_loss_ts
        return elapsed_since_recovery < within_seconds

    def gateway_loss_elapsed_s(self) -> Optional[float]:
        """Segundos transcurridos desde que el gateway se perdió, o None si online."""
        if self.gateway_online or self.last_gateway_loss_ts is None:
            return None
        return time.monotonic() - self.last_gateway_loss_ts

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _try_connect(self, host: str, port: int) -> bool:
        """Intenta TCP connect. Cierra el socket explícitamente en finally."""
        sock = None
        try:
            sock = socket.create_connection((host, port), timeout=self._timeout)
            return True
        except OSError:
            return False
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

    def _probe(self) -> bool:
        """Sondea el gateway, con fallback al puerto alternativo."""
        if self._try_connect(self._host, self._port):
            return True
        if self._fallback_port and self._fallback_port != self._port:
            return self._try_connect(self._host, self._fallback_port)
        return False

    def _run(self) -> None:
        """Loop principal del worker. Barrera total de excepciones."""
        try:
            while not self._stop_event.is_set():
                try:
                    online = self._probe()
                    now = time.monotonic()

                    if online:
                        if not self.gateway_online:
                            # Recuperación: registrar timestamp de vuelta
                            elapsed = now - (self.last_gateway_loss_ts or now)
                            logger.info(
                                "GatewayHeartbeat: gateway RECOVERED host=%s elapsed=%.1fs",
                                self._host,
                                elapsed,
                            )
                        self.gateway_online = True
                        self.last_gateway_ok_ts = now
                        self.consecutive_failures = 0
                    else:
                        self.consecutive_failures += 1
                        if self.gateway_online:
                            # Primera pérdida: registrar timestamp
                            self.last_gateway_loss_ts = now
                            logger.warning(
                                "GatewayHeartbeat: gateway LOST host=%s port=%d (or fallback %d)",
                                self._host,
                                self._port,
                                self._fallback_port,
                            )
                        self.gateway_online = False

                except Exception as _probe_exc:
                    logger.warning(
                        "GatewayHeartbeat: probe error host=%s: %s: %s",
                        self._host,
                        type(_probe_exc).__name__,
                        _probe_exc,
                    )
                    self.consecutive_failures += 1
                    if self.gateway_online:
                        self.last_gateway_loss_ts = time.monotonic()
                    self.gateway_online = False

                self._stop_event.wait(self._interval_s)

        except Exception as _fatal:
            logger.error(
                "GatewayHeartbeat: fatal error in worker thread, stopping: %s: %s",
                type(_fatal).__name__,
                _fatal,
            )
