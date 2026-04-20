"""Tick Streamer - Real-time market data broadcast over WebSocket.

A separate process that subscribes to real-time tick data and publishes over
WebSocket. Tick data passes through the Injection Shield before being emitted.
"""

import asyncio
import json
import time
from typing import Any

import structlog
import websockets
from websockets.server import WebSocketServerProtocol  # type: ignore[attr-defined]

from synx_mt5.bridge.factory import BridgeFactory
from synx_mt5.config import load_config
from synx_mt5.security.injection_shield import sanitise_dict

log = structlog.get_logger(__name__)


class TickStreamer:
    """
    Real-time tick data streamer over WebSocket.

    Broadcasts bid/ask ticks for subscribed symbols to all connected WebSocket clients.
    Each tick is sanitised through the Injection Shield before emission.
    """

    def __init__(
        self,
        symbols: list[str],
        host: str = "127.0.0.1",
        port: int = 8766,
        poll_interval_ms: int = 100,
        config_path: str | None = None,
    ):
        self.symbols = [s.upper() for s in symbols]
        self.host = host
        self.port = port
        self.poll_interval = poll_interval_ms / 1000.0
        self.config = load_config(config_path) if config_path else load_config()
        self.bridge: Any = None
        self._clients: set[WebSocketServerProtocol] = set()
        self._running = False
        self._last_ticks: dict[str, dict] = {}

    async def _connect_bridge(self) -> bool:
        """Connect to MT5 bridge."""
        try:
            self.bridge = BridgeFactory.create(self.config)
            connected = await self.bridge.connect()
            if connected:
                log.info("tick_streamer_bridge_connected", symbols=self.symbols)
                for symbol in self.symbols:
                    await self.bridge.market_book_add(symbol)
                return True
            return False
        except Exception as e:
            log.error("tick_streamer_bridge_connect_failed", error=str(e))
            return False

    async def _poll_ticks(self) -> None:
        """Poll tick data and broadcast to all clients."""
        while self._running:
            try:
                for symbol in self.symbols:
                    tick = await self.bridge.symbol_info_tick(symbol)
                    if tick and tick != self._last_ticks.get(symbol):
                        self._last_ticks[symbol] = tick

                        sanitized = sanitise_dict(tick, f"tick:{symbol}")
                        payload = {
                            "type": "tick",
                            "symbol": symbol,
                            "data": sanitized,
                            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        }

                        if self._clients:
                            message = json.dumps(payload)
                            await asyncio.gather(
                                *[client.send(message) for client in self._clients],
                                return_exceptions=True,
                            )

                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                log.error("tick_poll_error", error=str(e))
                await asyncio.sleep(1.0)

    async def _handle_client(
        self,
        websocket: WebSocketServerProtocol,
    ) -> None:
        """Handle a WebSocket client connection."""
        self._clients.add(websocket)
        client_host = websocket.remote_address[0] if websocket.remote_address else "unknown"
        log.info("tick_streamer_client_connected", client=client_host)

        try:
            welcome = {
                "type": "welcome",
                "symbols": self.symbols,
                "poll_interval_ms": int(self.poll_interval * 1000),
            }
            await websocket.send(json.dumps(welcome))

            async for message in websocket:
                try:
                    data = json.loads(message)
                    action = data.get("action")
                    if action == "subscribe":
                        symbol = data.get("symbol", "").upper()
                        if symbol not in self.symbols:
                            self.symbols.append(symbol)
                            if self.bridge:
                                await self.bridge.market_book_add(symbol)
                            log.info("tick_streamer_symbol_added", symbol=symbol)
                            await websocket.send(
                                json.dumps(
                                    {
                                        "type": "subscribed",
                                        "symbol": symbol,
                                    }
                                )
                            )
                    elif action == "unsubscribe":
                        symbol = data.get("symbol", "").upper()
                        if symbol in self.symbols and len(self.symbols) > 1:
                            self.symbols.remove(symbol)
                            if self.bridge:
                                await self.bridge.market_book_release(symbol)
                            log.info("tick_streamer_symbol_removed", symbol=symbol)
                            await websocket.send(
                                json.dumps(
                                    {
                                        "type": "unsubscribed",
                                        "symbol": symbol,
                                    }
                                )
                            )
                    elif action == "ping":
                        await websocket.send(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "error",
                                "message": "Invalid JSON",
                            }
                        )
                    )
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            log.info("tick_streamer_client_disconnected", client=client_host)

    async def _ws_handler(self, websocket: WebSocketServerProtocol) -> None:
        """WebSocket connection handler."""
        await self._handle_client(websocket)

    async def run(self) -> None:
        """Run the tick streamer."""
        self._running = True

        if not await self._connect_bridge():
            log.error("tick_streamer_failed_to_connect")
            raise RuntimeError("Failed to connect to MT5 bridge")

        log.info(
            "tick_streamer_starting",
            host=self.host,
            port=self.port,
            symbols=self.symbols,
        )

        async with websockets.serve(self._ws_handler, self.host, self.port):
            log.info("tick_streamer_ready", host=self.host, port=self.port)
            await asyncio.gather(
                self._poll_ticks(),
                asyncio.Event().wait(),
            )


async def main() -> None:
    """CLI entry point for tick streamer."""
    import argparse

    import structlog

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.make_filtering_bound_logger.__self__._default_level,  # noqa
        ),
    )

    parser = argparse.ArgumentParser(description="SYNX-MT5-MCP Tick Streamer")
    parser.add_argument("--symbols", default="EURUSD,GBPUSD,XAUUSD", help="Comma-separated symbols")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8766, type=int)
    parser.add_argument("--poll-interval-ms", default=100, type=int)
    parser.add_argument("--config", help="Path to configuration file")
    args = parser.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")]

    streamer = TickStreamer(
        symbols=symbols,
        host=args.host,
        port=args.port,
        poll_interval_ms=args.poll_interval_ms,
        config_path=args.config,
    )

    await streamer.run()


if __name__ == "__main__":
    asyncio.run(main())
