"""Connection Tools - MT5 bridge initialization and connection management."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator

from synx_mt5.audit.engine import AuditEngine, AuditEventType
from synx_mt5.security.capability import get_active_profile
from synx_mt5.security.injection_shield import sanitise_string

log = structlog.get_logger(__name__)


class ConnectionState(StrEnum):
    """Connection state enumeration."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class InitializeInput(BaseModel):
    """Input model for initialize tool."""

    path: str | None = Field(default=None, description="Override MT5 terminal path")

    @field_validator("path")
    @classmethod
    def sanitize_path(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = sanitise_string(v, "initialize:path")
        if len(v) > 512:
            raise ValueError("Path exceeds maximum length")
        return v


class InitializeOutput(BaseModel):
    """Output model for initialize tool."""

    version: str
    build: int
    connected: bool
    terminal_path: str | None = None
    connect_time_ms: float | None = None
    retcode: int = 0
    retcode_description: str = "Success"


class ConnectionStatusOutput(BaseModel):
    """Output model for get_connection_status tool."""

    state: ConnectionState
    uptime_seconds: float
    last_ping_ms: float
    session_id: str
    profile: str
    tools_count: int
    connected_since: str | None = None


class ShutdownInput(BaseModel):
    """Input model for shutdown tool."""

    force: bool = Field(
        default=False, description="Force shutdown without waiting for pending operations"
    )


class ShutdownOutput(BaseModel):
    """Output model for shutdown tool."""

    disconnected: bool
    message: str


@dataclass
class ConnectionMetrics:
    """Connection metrics tracker."""

    connect_time: datetime | None = None
    last_ping: datetime | None = None
    last_ping_ms: float = 0.0
    reconnect_attempts: int = 0
    total_requests: int = 0
    failed_requests: int = 0

    def uptime_seconds(self) -> float:
        if self.connect_time is None:
            return 0.0
        delta = datetime.now(UTC) - self.connect_time
        return delta.total_seconds()

    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return 1.0 - (self.failed_requests / self.total_requests)


class ConnectionManager:
    """
    Manages MT5 bridge connection lifecycle.

    Provides:
    - Connection state tracking
    - Metrics collection
    - Reconnection logic
    - Audit logging
    """

    def __init__(
        self,
        bridge: Any,
        audit: AuditEngine,
        session_id: str,
    ):
        self.bridge = bridge
        self.audit = audit
        self.session_id = session_id
        self.metrics = ConnectionMetrics()
        self._state = ConnectionState.DISCONNECTED
        self._lock = False

    @property
    def state(self) -> ConnectionState:
        return self._state

    @state.setter
    def state(self, value: ConnectionState) -> None:
        old_state = self._state
        self._state = value
        if old_state != value:
            log.info(
                "connection_state_changed",
                old_state=old_state.value,
                new_state=value.value,
                session_id=self.session_id,
            )

    async def initialize(self, path: str | None = None) -> InitializeOutput:
        """
        Initialize MT5 bridge connection.

        This is the first tool that must be called before any other tools.
        Credentials are loaded from OS keyring - never from inputs.
        """
        import time

        start_time = time.perf_counter()

        self.state = ConnectionState.CONNECTING
        self.audit.log(
            AuditEventType.CREDENTIAL_LOAD,
            {
                "operation": "initialize",
                "session_id": self.session_id,
            },
        )

        try:
            connected = await self.bridge.connect()
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            if connected:
                self.state = ConnectionState.CONNECTED
                self.metrics.connect_time = datetime.now(UTC)
                self.metrics.last_ping = datetime.now(UTC)
                self.metrics.last_ping_ms = elapsed_ms

                self.audit.log(
                    AuditEventType.BRIDGE_CONNECT,
                    {
                        "connect_time_ms": round(elapsed_ms, 2),
                        "session_id": self.session_id,
                        "path": path,
                    },
                )

                terminal_info = await self.bridge.terminal_info()

                log.info(
                    "mt5_initialized",
                    elapsed_ms=round(elapsed_ms, 2),
                    version=terminal_info.get("version", "unknown"),
                )

                return InitializeOutput(
                    version=terminal_info.get("version", "unknown"),
                    build=terminal_info.get("build", 0),
                    connected=True,
                    terminal_path=terminal_info.get("path"),
                    connect_time_ms=round(elapsed_ms, 2),
                    retcode=0,
                    retcode_description="Initialized successfully",
                )
            else:
                self.state = ConnectionState.ERROR
                return InitializeOutput(
                    version="",
                    build=0,
                    connected=False,
                    retcode=-1,
                    retcode_description="Connection failed",
                )

        except Exception as e:
            self.state = ConnectionState.ERROR
            log.error("initialize_failed", error=str(e), error_type=type(e).__name__)

            self.audit.log(
                AuditEventType.BRIDGE_DISCONNECT,
                {
                    "reason": "initialize_error",
                    "error": str(e),
                    "session_id": self.session_id,
                },
            )

            return InitializeOutput(
                version="",
                build=0,
                connected=False,
                retcode=-1,
                retcode_description=f"Error: {str(e)}",
            )

    async def get_status(self) -> ConnectionStatusOutput:
        """Get current connection status and metrics."""
        profile_name, profile_tools = get_active_profile()

        is_connected = await self.bridge.is_connected()

        if is_connected and self.state != ConnectionState.CONNECTED:
            self.state = ConnectionState.CONNECTED
        elif not is_connected and self.state == ConnectionState.CONNECTED:
            self.state = ConnectionState.DISCONNECTED

        return ConnectionStatusOutput(
            state=self.state,
            uptime_seconds=round(self.metrics.uptime_seconds(), 2),
            last_ping_ms=round(self.metrics.last_ping_ms, 2),
            session_id=self.session_id,
            profile=profile_name,
            tools_count=len(profile_tools),
            connected_since=self.metrics.connect_time.isoformat()
            if self.metrics.connect_time
            else None,
        )

    async def shutdown(self, force: bool = False) -> ShutdownOutput:
        """
        Gracefully disconnect from MT5 terminal.

        Requires 'full' capability profile.
        """
        if self.state == ConnectionState.DISCONNECTED:
            return ShutdownOutput(
                disconnected=True,
                message="Already disconnected",
            )

        try:
            if not force:
                await self.bridge.disconnect()
            else:
                if hasattr(self.bridge, "_executor"):
                    self.bridge._executor.shutdown(wait=False)

            self.state = ConnectionState.DISCONNECTED
            self.metrics.connect_time = None

            self.audit.log(
                AuditEventType.BRIDGE_DISCONNECT,
                {
                    "reason": "manual_shutdown",
                    "force": force,
                    "session_id": self.session_id,
                },
            )

            log.info("mt5_shutdown", force=force)

            return ShutdownOutput(
                disconnected=True,
                message="Disconnected successfully",
            )

        except Exception as e:
            log.error("shutdown_error", error=str(e))
            return ShutdownOutput(
                disconnected=False,
                message=f"Error during shutdown: {str(e)}",
            )


async def handle_initialize(
    manager: ConnectionManager,
    input_data: InitializeInput,
) -> dict[str, Any]:
    """Handle initialize tool invocation."""
    result = await manager.initialize(input_data.path)
    return result.model_dump()


async def handle_get_connection_status(
    manager: ConnectionManager,
) -> dict[str, Any]:
    """Handle get_connection_status tool invocation."""
    result = await manager.get_status()
    return result.model_dump()


async def handle_shutdown(
    manager: ConnectionManager,
    input_data: ShutdownInput,
) -> dict[str, Any]:
    """Handle shutdown tool invocation."""
    result = await manager.shutdown(input_data.force)
    return result.model_dump()
