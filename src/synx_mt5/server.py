"""SYNX-MT5-MCP Server - Main entry point and MCP server bootstrap."""

import asyncio
import logging
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server

from synx_mt5 import __version__
from synx_mt5.audit import AuditEngine, AuditEventType
from synx_mt5.bridge.factory import BridgeFactory
from synx_mt5.config import Config, load_config
from synx_mt5.idempotency.engine import IdempotencyEngine
from synx_mt5.intelligence.memory import AgentMemory
from synx_mt5.intelligence.strategy_context import StrategyContextEngine
from synx_mt5.risk.circuit_breaker import DrawdownCircuitBreaker
from synx_mt5.risk.hitl import HITLGate
from synx_mt5.risk.preflight import PreFlightValidator
from synx_mt5.risk.sizing import PositionSizingEngine
from synx_mt5.security.capability import init_audit, load_profile
from synx_mt5.security.rate_limiter import RateLimiter

logger = structlog.get_logger(__name__)


class SYNXServer:
    """
    Main SYNX-MT5-MCP server.
    Manages lifecycle, bridge connections, and MCP protocol handling.
    """

    def __init__(self, config_path: str | None = None):
        self.config: Config = load_config(config_path)
        self.audit: AuditEngine = AuditEngine(
            log_path=Path(self.config.security.audit_log_path),
            chain_verification=self.config.security.chain_verification,
            rotate_size_mb=self.config.security.rotate_size_mb,
        )
        self.bridge: Any = None
        self.session_id: str = self.audit.session_id
        self._running: bool = False

        self.circuit_breaker: DrawdownCircuitBreaker | None = None
        self.hitl_gate: HITLGate | None = None
        self.idempotency: IdempotencyEngine | None = None
        self.preflight: PreFlightValidator | None = None
        self.sizing: PositionSizingEngine | None = None

        self.strategy_context: StrategyContextEngine | None = None
        self.agent_memory: AgentMemory | None = None

        self.market_data_service: Any = None
        self.intelligence_service: Any = None
        self.execution_service: Any = None
        self.position_service: Any = None
        self.history_service: Any = None
        self.risk_service: Any = None
        self.terminal_mgmt_service: Any = None
        self.market_depth_service: Any = None
        self.chart_service: Any = None
        self.mql5_service: Any = None
        self.backtest_service: Any = None
        self.connection_manager: Any = None

        self._server: Server | None = None

    async def initialize(self) -> None:
        """Initialize server components."""
        logger.info(
            "synx_server_initializing",
            version=__version__,
            profile=self.config.profile,
            bridge_mode=self.config.bridge.mode,
        )

        self.audit.log(
            AuditEventType.SERVER_START,
            {
                "version": __version__,
                "profile": self.config.profile,
                "bridge_mode": self.config.bridge.mode,
            },
        )

        init_audit(self.audit)

        profile_tools = self._get_profile_tools(self.config.profile)
        load_profile(self.config.profile, profile_tools)

        storage_path = Path(self.config.server.storage_path)
        storage_path.mkdir(parents=True, exist_ok=True)

        self.strategy_context = StrategyContextEngine(storage_path)
        self.agent_memory = AgentMemory(storage_path)

        self.idempotency = IdempotencyEngine(
            ttl_seconds=self.config.idempotency.ttl_seconds,
            max_cache_size=self.config.idempotency.max_cache_size,
        )

        self.sizing = PositionSizingEngine(
            config=self.config.risk.model_dump(),
        )

        self._init_services()

        logger.info("synx_server_initialized")

    def _get_profile_tools(self, profile: str) -> list[str]:
        """Load allowed tools for profile with extends inheritance."""
        import yaml

        def _load_with_inheritance(name: str, visited: set[str] | None = None) -> dict:
            if visited is None:
                visited = set()
            if name in visited:
                raise ValueError(f"Circular profile inheritance detected: {name}")
            visited.add(name)

            profile_path = Path(__file__).parent.parent / "config" / "profiles" / f"{name}.yaml"
            if not profile_path.exists():
                return {}
            with open(profile_path) as f:
                data = yaml.safe_load(f) or {}

            parent = data.get("extends")
            if parent:
                parent_data = _load_with_inheritance(parent, visited)
                parent_tools = parent_data.get("allowed_tools", [])
                own_tools = data.get("allowed_tools", [])
                data["allowed_tools"] = list(dict.fromkeys(parent_tools + own_tools))

                parent_hitl = parent_data.get("hitl_required", [])
                own_hitl = data.get("hitl_required", [])
                data["hitl_required"] = list(dict.fromkeys(parent_hitl + own_hitl))

            return data

        full_data = _load_with_inheritance(profile)
        return full_data.get("allowed_tools", [])

    def _load_profile_config(self, profile: str) -> dict:
        """Load full profile configuration with extends inheritance."""
        import yaml

        def _load_with_inheritance(name: str, visited: set[str] | None = None) -> dict:
            if visited is None:
                visited = set()
            if name in visited:
                raise ValueError(f"Circular profile inheritance detected: {name}")
            visited.add(name)

            profile_path = Path(__file__).parent.parent / "config" / "profiles" / f"{name}.yaml"
            if not profile_path.exists():
                return {}
            with open(profile_path) as f:
                data = yaml.safe_load(f) or {}

            parent = data.get("extends")
            if parent:
                parent_data = _load_with_inheritance(parent, visited)
                parent_tools = parent_data.get("allowed_tools", [])
                own_tools = data.get("allowed_tools", [])
                data["allowed_tools"] = list(dict.fromkeys(parent_tools + own_tools))

                parent_hitl = parent_data.get("hitl_required", [])
                own_hitl = data.get("hitl_required", [])
                data["hitl_required"] = list(dict.fromkeys(parent_hitl + own_hitl))

                parent_rates = parent_data.get("rate_limits", {})
                own_rates = data.get("rate_limits", {})
                data["rate_limits"] = {**parent_rates, **own_rates}

            return data

        return _load_with_inheritance(profile)

    def _init_services(self) -> None:
        """Initialize all service classes. Called after bridge is connected."""
        from synx_mt5.tools.chart_control import ChartService
        from synx_mt5.tools.history import HistoryService
        from synx_mt5.tools.intelligence import IntelligenceService
        from synx_mt5.tools.market_data import MarketDataService
        from synx_mt5.tools.market_depth import MarketDepthService
        from synx_mt5.tools.mql5_dev import MQL5Service
        from synx_mt5.tools.positions import PositionManagementService
        from synx_mt5.tools.risk_tools import RiskService
        from synx_mt5.tools.strategy_tester import BacktestService

        risk_cfg = self.config.risk.model_dump()

        profile_cfg = self._load_profile_config(self.config.profile)
        rate_limits = profile_cfg.get("rate_limits", {})
        if not rate_limits:
            rate_limits = {
                "copy_rates_from_pos": {
                    "calls": 60,
                    "window_seconds": 60,
                },
                "copy_ticks_from": {
                    "calls": 30,
                    "window_seconds": 60,
                },
            }

        rate_limiter = RateLimiter(rate_limits)

        regime_cfg = self.config.intelligence.regime_detector.model_dump()
        corr_ttl = self.config.intelligence.cache_ttl_seconds

        self.market_data_service = MarketDataService(
            bridge=self.bridge,
            audit=self.audit,
            rate_limiter=rate_limiter,
        )

        self.intelligence_service = IntelligenceService(
            bridge=self.bridge,
            audit=self.audit,
            storage_path=Path(self.config.server.storage_path),
            regime_config=regime_cfg,
            correlation_cache_ttl=corr_ttl,
        )

        self.position_service = PositionManagementService(
            bridge=self.bridge,
            audit=self.audit,
        )

        self.history_service = HistoryService(
            bridge=self.bridge,
            audit=self.audit,
        )

        self.market_depth_service = MarketDepthService(
            bridge=self.bridge,
            audit=self.audit,
        )

        self.chart_service = ChartService(
            bridge=self.bridge,
            audit=self.audit,
        )

        from synx_mt5.bridge.metaeditor import MetaEditorBridge

        metaeditor_bridge = MetaEditorBridge(
            config=self.config.mql5_dev,
            terminal_data_path=None,
        )
        self.mql5_service = MQL5Service(
            bridge=metaeditor_bridge,
            audit=self.audit,
        )

        self.backtest_service = BacktestService(
            bridge=self.bridge,
            audit=self.audit,
            results_dir=self.config.strategy_tester.results_dir,
            hitl=self.hitl_gate,
        )

        from synx_mt5.tools.terminal_mgmt import TerminalMgmtService

        self.terminal_mgmt_service = TerminalMgmtService(
            bridge=self.bridge,
            audit=self.audit,
        )

        from synx_mt5.tools.execution import ExecutionService

        self.execution_service = ExecutionService(
            bridge=self.bridge,
            audit=self.audit,
            risk_config=risk_cfg,
            preflight=self.preflight,
            sizing=self.sizing,
            circuit_breaker=self.circuit_breaker,
            hitl=self.hitl_gate,
            idempotency=self.idempotency,
        )

        self.risk_service = RiskService(
            audit=self.audit,
            risk_config=risk_cfg,
            circuit_breaker=self.circuit_breaker,
            hitl=self.hitl_gate,
            idempotency=self.idempotency,
            bridge=self.bridge,
        )

    async def connect_bridge(self) -> bool:
        """Connect to MT5 terminal."""
        try:
            self.bridge = BridgeFactory.create(self.config.bridge)
            connected = await self.bridge.connect()
            if connected:
                self.audit.log(
                    AuditEventType.BRIDGE_CONNECT,
                    {
                        "mode": self.config.bridge.mode,
                    },
                )

                self.preflight = PreFlightValidator(
                    config=self.config.risk.model_dump(),
                    bridge=self.bridge,
                )

                self.circuit_breaker = DrawdownCircuitBreaker(
                    config=self.config.risk.model_dump(),
                    bridge=self.bridge,
                    audit=self.audit,
                )
                asyncio.create_task(self.circuit_breaker.start_monitoring())

                self.hitl_gate = HITLGate(
                    config=self.config.hitl.model_dump(),
                    audit=self.audit,
                )

                from synx_mt5.tools.connection import ConnectionManager

                self.connection_manager = ConnectionManager(
                    bridge=self.bridge,
                    audit=self.audit,
                    session_id=self.audit.session_id,
                )

                self._init_services()

                logger.info("mt5_bridge_connected")
                return True
            return False
        except Exception as e:
            logger.error("mt5_bridge_connection_failed", error=str(e))
            return False

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("synx_server_shutting_down")
        self._running = False

        if self.circuit_breaker:
            await self.circuit_breaker.stop_monitoring()

        if self.bridge:
            with suppress(Exception):
                await self.bridge.disconnect()
            self.audit.log(AuditEventType.BRIDGE_DISCONNECT, {})

        self.audit.log(AuditEventType.SERVER_STOP, {})
        logger.info("synx_server_stopped")

    def _setup_server(self) -> None:
        """Set up MCP server with tools, resources, and prompts."""
        from synx_mt5.tools.registry import register_all_tools, register_prompts, register_resources

        self._server = Server("synx_mt5_mcp")
        register_all_tools(self._server, self)
        register_resources(self._server, self)
        register_prompts(self._server)

    async def run_stdio(self) -> None:
        """Run server with stdio transport."""
        self._setup_server()

        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream,
                write_stream,
                self._server.create_initialization_options(),
            )

    async def run_http(self, host: str, port: int, api_key: str) -> None:
        """Run server with HTTP/SSE transport using StreamableHTTP."""
        import uvicorn
        from mcp.server.streamable_http import StreamableHTTPServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route

        self._setup_server()
        transport = StreamableHTTPServerTransport(mcp_session_id=None)

        async def handle_mcp(scope, receive, send) -> None:
            await transport.handle_request(scope, receive, send)

        app = Starlette(
            routes=[
                Route("/mcp", handle_mcp, methods=["GET", "POST", "DELETE"]),
            ]
        )

        async with transport.connect() as (read_stream, write_stream):

            async def run_server():
                await self._server.run(
                    read_stream,
                    write_stream,
                    self._server.create_initialization_options(),
                )

            server_task = asyncio.create_task(run_server())

            config = uvicorn.Config(
                app=app,
                host=host,
                port=port,
                log_level="info",
            )
            srv = uvicorn.Server(config)
            await srv.serve()
            server_task.cancel()
            with suppress(asyncio.CancelledError):
                await server_task

        logger.info("synx_http_server_stopped")


def main():
    """CLI entry point."""
    import argparse

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )

    parser = argparse.ArgumentParser(description="SYNX-MT5-MCP Server")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--api-key")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    server = SYNXServer(config_path=args.config)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run():
        await server.initialize()

        if args.transport == "stdio":
            # Start stdio handshake immediately so the MCP client doesn't time out,
            # then connect to MT5 in the background.
            server._setup_server()

            async def _bg_connect():
                if not await server.connect_bridge():
                    logger.error("failed_to_connect_to_mt5_background")

            async with stdio_server() as (read_stream, write_stream):
                asyncio.create_task(_bg_connect())
                await server._server.run(
                    read_stream,
                    write_stream,
                    server._server.create_initialization_options(),
                )
        else:
            if not await server.connect_bridge():
                logger.error("failed_to_connect_to_mt5")
                sys.exit(1)
            await server.run_http(args.host, args.port, args.api_key or "")

    try:
        loop.run_until_complete(run())
    except KeyboardInterrupt:
        loop.run_until_complete(server.shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
