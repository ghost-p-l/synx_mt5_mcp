"""
Tool registry - Registers all MCP tools with complete schemas and real handler implementations.

Uses the MCP Server decorator pattern:
- @server.list_tools() for tool definitions
- @server.call_tool() for tool invocation
- @server.list_resources() + @server.read_resource() for resource content
- @server.list_prompts() + @server.get_prompt() for prompt templates
"""

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from mcp.types import (
    CallToolResult,
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    TextContent,
    Tool,
)

from synx_mt5.resources import (
    RISK_ACKNOWLEDGMENT_PROMPT,
    SESSION_START_PROMPT,
    STRATEGY_DOCUMENTATION_PROMPT,
)
from synx_mt5.resources.guides import (
    get_active_profile_content,
    get_chart_control_guide,
    get_getting_started,
    get_intelligence_guide,
    get_market_data_guide,
    get_mql5_dev_guide,
    get_python_api_boundary,
    get_risk_limits_content,
    get_security_model,
    get_strategy_context_content,
    get_trading_guide,
)
from synx_mt5.security.capability import get_active_profile


@dataclass
class HandlerServices:
    bridge: Any
    audit: Any
    config: Any
    circuit_breaker: Any
    hitl_gate: Any
    idempotency: Any
    preflight: Any
    sizing: Any
    strategy_context: Any
    agent_memory: Any
    connection_manager: Any
    market_data_service: Any
    intelligence_service: Any
    position_service: Any
    history_service: Any
    risk_service: Any
    terminal_mgmt_service: Any
    market_depth_service: Any
    chart_service: Any
    mql5_service: Any
    backtest_service: Any
    execution_service: Any


def _get_services(synx_server: Any) -> HandlerServices:
    return HandlerServices(
        bridge=synx_server.bridge,
        audit=synx_server.audit,
        config=synx_server.config,
        circuit_breaker=synx_server.circuit_breaker,
        hitl_gate=synx_server.hitl_gate,
        idempotency=synx_server.idempotency,
        preflight=synx_server.preflight,
        sizing=synx_server.sizing,
        strategy_context=synx_server.strategy_context,
        agent_memory=synx_server.agent_memory,
        connection_manager=synx_server.connection_manager,
        market_data_service=synx_server.market_data_service,
        intelligence_service=synx_server.intelligence_service,
        position_service=synx_server.position_service,
        history_service=synx_server.history_service,
        risk_service=synx_server.risk_service,
        terminal_mgmt_service=synx_server.terminal_mgmt_service,
        market_depth_service=synx_server.market_depth_service,
        chart_service=synx_server.chart_service,
        mql5_service=synx_server.mql5_service,
        backtest_service=synx_server.backtest_service,
        execution_service=synx_server.execution_service,
    )


def _build_tools() -> list[Tool]:
    tools = []
    for tool_name, schema in TOOL_SCHEMAS.items():
        tools.append(
            Tool(
                name=tool_name,
                description=schema["description"],
                inputSchema=schema["inputSchema"],
            )
        )
    return tools


def register_all_tools(server: Any, synx_server: Any) -> None:
    """Register all MCP tools using the decorator pattern."""

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return _build_tools()

    @server.call_tool(validate_input=True)
    async def call_tool(tool_name: str, arguments: dict) -> CallToolResult:
        handler = _TOOL_HANDLERS.get(tool_name)
        if handler is None:
            return CallToolResult(
                content=[TextContent(type="text", text=f"No handler for tool '{tool_name}'")],
                isError=True,
            )
        try:
            services = _get_services(synx_server)
            result = await handler(services, arguments or {})
            if isinstance(result, CallToolResult):
                return result
            if isinstance(result, dict):
                import json

                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(result, indent=2))],
                    structuredContent=result,
                    isError=result.get("error") is not None,
                )
            return CallToolResult(
                content=[TextContent(type="text", text=str(result))],
            )
        except Exception as e:
            import structlog

            log = structlog.get_logger(__name__)
            log.error("tool_handler_error", tool=tool_name, error=str(e))
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {e}")],
                isError=True,
            )


def register_resources(server: Any, synx_server: Any) -> None:
    """Register MCP resources with real content providers."""

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="mt5://synx/getting_started",
                name="Getting Started",
                description="Quick-start workflow for agents",
                mimeType="text/markdown",
            ),
            Resource(
                uri="mt5://synx/security_model",
                name="Security Model",
                description="Security constraints and threat model",
                mimeType="text/markdown",
            ),
            Resource(
                uri="mt5://synx/active_profile",
                name="Active Profile",
                description="Current capability profile and allowed tools",
                mimeType="text/markdown",
            ),
            Resource(
                uri="mt5://synx/risk_limits",
                name="Risk Limits",
                description="Active risk configuration",
                mimeType="text/markdown",
            ),
            Resource(
                uri="mt5://synx/trading_guide",
                name="Trading Guide",
                description="Order types, filling modes, MT5 constants",
                mimeType="text/markdown",
            ),
            Resource(
                uri="mt5://synx/market_data_guide",
                name="Market Data Guide",
                description="Timeframes, tick data, symbol conventions",
                mimeType="text/markdown",
            ),
            Resource(
                uri="mt5://synx/intelligence_guide",
                name="Intelligence Guide",
                description="How to use regime detection and correlations",
                mimeType="text/markdown",
            ),
            Resource(
                uri="mt5://synx/strategy_context",
                name="Strategy Context",
                description="Current strategy memo",
                mimeType="text/markdown",
            ),
            Resource(
                uri="mt5://synx/python_api_boundary",
                name="Python API Boundary",
                description="Complete 32-function boundary map",
                mimeType="text/markdown",
            ),
            Resource(
                uri="mt5://synx/chart_control_guide",
                name="Chart Control Guide",
                description="How to use chart tools via SYNX_EA",
                mimeType="text/markdown",
            ),
            Resource(
                uri="mt5://synx/mql5_dev_guide",
                name="MQL5 Dev Guide",
                description="MQL5 development workflow",
                mimeType="text/markdown",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        services = _get_services(synx_server)
        return _get_resource_content(uri, services)


def _get_resource_content(uri: str, services: HandlerServices) -> str:
    """Get resource content by URI."""
    uri = str(uri)
    if uri == "mt5://synx/getting_started":
        return get_getting_started()
    elif uri == "mt5://synx/security_model":
        return get_security_model()
    elif uri == "mt5://synx/active_profile":
        profile_name, profile_tools = get_active_profile()
        return get_active_profile_content(profile_name, list(profile_tools))
    elif uri == "mt5://synx/risk_limits":
        risk_config = services.config.model_dump() if services.config else {}
        return get_risk_limits_content(risk_config)
    elif uri == "mt5://synx/trading_guide":
        return get_trading_guide()
    elif uri == "mt5://synx/market_data_guide":
        return get_market_data_guide()
    elif uri == "mt5://synx/intelligence_guide":
        return get_intelligence_guide()
    elif uri == "mt5://synx/strategy_context":
        ctx = None
        if services.strategy_context:
            with suppress(Exception):
                ctx = services.strategy_context.get()
        return get_strategy_context_content(ctx)
    elif uri == "mt5://synx/python_api_boundary":
        return get_python_api_boundary()
    elif uri == "mt5://synx/chart_control_guide":
        return get_chart_control_guide()
    elif uri == "mt5://synx/mql5_dev_guide":
        return get_mql5_dev_guide()
    return f"Resource not found: {uri}"


def register_prompts(server: Any) -> None:
    """Register MCP prompt templates."""

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="session_start",
                title="Session Start",
                description="First-session workflow for AI agents connecting to MT5",
                arguments=[
                    PromptArgument(
                        name="profile",
                        description="Capability profile (read_only, analyst, executor, full)",
                        required=False,
                    ),
                ],
            ),
            Prompt(
                name="risk_acknowledgment",
                title="Risk Acknowledgment",
                description="Risk acknowledgment before order execution",
                arguments=[],
            ),
            Prompt(
                name="strategy_documentation",
                title="Strategy Documentation",
                description="Template for documenting a trading strategy",
                arguments=[
                    PromptArgument(
                        name="symbols",
                        description="Trading symbols (e.g. EURUSD, GBPUSD)",
                        required=False,
                    ),
                    PromptArgument(
                        name="timeframe",
                        description="Trading timeframe (e.g. H1, H4, D1)",
                        required=False,
                    ),
                ],
            ),
        ]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
        from mcp.types import Role

        if name == "session_start":
            profile = (arguments or {}).get("profile", "analyst")
            text = SESSION_START_PROMPT.replace(
                "Market Data: get_symbols",
                f"Market Data: get_symbols (profile: {profile})",
            )
            return GetPromptResult(
                description="Session start prompt for SYNX-MT5-MCP",
                messages=[
                    PromptMessage(role=Role.USER, content=TextContent(type="text", text=text))
                ],
            )
        elif name == "risk_acknowledgment":
            return GetPromptResult(
                description="Risk acknowledgment prompt",
                messages=[
                    PromptMessage(
                        role=Role.USER,
                        content=TextContent(type="text", text=RISK_ACKNOWLEDGMENT_PROMPT),
                    )
                ],
            )
        elif name == "strategy_documentation":
            symbols = (arguments or {}).get("symbols", "")
            timeframe = (arguments or {}).get("timeframe", "")
            text = STRATEGY_DOCUMENTATION_PROMPT
            if symbols:
                text += f"\n\n**Symbols for this strategy:** {symbols}"
            if timeframe:
                text += f"\n**Timeframe:** {timeframe}"
            return GetPromptResult(
                description="Strategy documentation template",
                messages=[
                    PromptMessage(role=Role.USER, content=TextContent(type="text", text=text))
                ],
            )
        raise ValueError(f"Unknown prompt: {name}")


# =============================================================================
# TOOL SCHEMAS
# =============================================================================

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "initialize": {
        "description": "Initialize the MT5 bridge connection. Must be called first.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Override terminal path"}},
        },
    },
    "get_connection_status": {
        "description": "Get current bridge connection state and session info.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "shutdown": {
        "description": "Gracefully disconnect from MT5 terminal.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "force": {"type": "boolean", "description": "Force shutdown without waiting"},
            },
        },
    },
    "get_symbols": {
        "description": "List all available trading symbols.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group": {"type": "string", "description": "Filter pattern (e.g. '*USD*')"},
                "exact_match": {
                    "type": "boolean",
                    "description": "Use exact match instead of pattern",
                },
            },
        },
    },
    "get_symbols_total": {
        "description": "Get the total number of available symbols.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "get_symbol_info": {
        "description": "Get full contract specification for a symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Symbol name (e.g. EURUSD)"},
            },
            "required": ["symbol"],
        },
    },
    "get_symbol_info_tick": {
        "description": "Get current bid/ask/last/volume for a symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Symbol name"},
            },
            "required": ["symbol"],
        },
    },
    "copy_rates_from_pos": {
        "description": "Get OHLCV bars from a position offset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "timeframe": {
                    "type": "string",
                    "enum": ["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1"],
                },
                "start_pos": {
                    "type": "integer",
                    "description": "Bar offset from current (0 = most recent)",
                },
                "count": {"type": "integer", "description": "Number of bars (max 50000)"},
            },
            "required": ["symbol", "timeframe", "start_pos", "count"],
        },
    },
    "copy_rates_from": {
        "description": "Get OHLCV bars from a specific datetime.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "timeframe": {"type": "string"},
                "date_from": {"type": "string", "description": "ISO 8601 datetime"},
                "count": {"type": "integer"},
            },
            "required": ["symbol", "timeframe", "date_from", "count"],
        },
    },
    "copy_rates_range": {
        "description": "Get OHLCV bars within a date range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "timeframe": {"type": "string"},
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
            },
            "required": ["symbol", "timeframe", "date_from", "date_to"],
        },
    },
    "copy_ticks_from": {
        "description": "Get tick data from a specific datetime.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "date_from": {"type": "string"},
                "count": {"type": "integer"},
                "flags": {"type": "integer", "description": "Tick flags filter"},
            },
            "required": ["symbol", "date_from", "count"],
        },
    },
    "copy_ticks_range": {
        "description": "Get tick data within a date range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "flags": {"type": "integer"},
            },
            "required": ["symbol", "date_from", "date_to"],
        },
    },
    "symbol_select": {
        "description": "Add or remove a symbol from MarketWatch.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "select": {"type": "boolean"},
            },
            "required": ["symbol", "select"],
        },
    },
    "order_check": {
        "description": "Dry-run order validation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "volume": {"type": "number"},
                "order_type": {"type": "string"},
                "price": {"type": "number"},
                "sl": {"type": "number"},
                "tp": {"type": "number"},
            },
            "required": ["symbol", "volume", "order_type"],
        },
    },
    "order_calc_margin": {
        "description": "Calculate margin required for an order.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "volume": {"type": "number"},
                "order_type": {"type": "string"},
                "price": {"type": "number"},
            },
            "required": ["symbol", "volume", "order_type", "price"],
        },
    },
    "order_calc_profit": {
        "description": "Calculate potential profit for an order.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "volume": {"type": "number"},
                "order_type": {"type": "string"},
                "price_open": {"type": "number"},
                "price_close": {"type": "number"},
            },
            "required": ["symbol", "volume", "order_type", "price_open", "price_close"],
        },
    },
    "order_send": {
        "description": "Place a market or pending order. Requires executor+ profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "volume": {"type": "number"},
                "order_type": {"type": "string"},
                "price": {"type": "number"},
                "sl": {"type": "number"},
                "tp": {"type": "number"},
                "comment": {"type": "string"},
                "magic": {"type": "integer"},
            },
            "required": ["symbol", "volume", "order_type"],
        },
    },
    "order_modify": {
        "description": "Modify sl/tp or price of a pending order.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket": {"type": "integer"},
                "price": {"type": "number"},
                "sl": {"type": "number"},
                "tp": {"type": "number"},
            },
            "required": ["ticket"],
        },
    },
    "order_cancel": {
        "description": "Cancel a pending order.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket": {"type": "integer"},
            },
            "required": ["ticket"],
        },
    },
    "position_close": {
        "description": "Close an open position by ticket.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket": {"type": "integer"},
                "volume": {"type": "number", "description": "Partial close if specified"},
                "deviation": {"type": "integer"},
            },
            "required": ["ticket"],
        },
    },
    "position_close_partial": {
        "description": "Close a partial amount from an open position.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket": {"type": "integer"},
                "volume": {"type": "number"},
                "deviation": {"type": "integer"},
            },
            "required": ["ticket", "volume"],
        },
    },
    "position_close_all": {
        "description": "Close ALL open positions. DESTRUCTIVE. Requires full profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Filter by symbol"},
                "confirm": {"type": "boolean", "description": "Must be true"},
            },
            "required": ["confirm"],
        },
    },
    "position_modify": {
        "description": "Modify SL/TP of an open position.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket": {"type": "integer"},
                "sl": {"type": "number"},
                "tp": {"type": "number"},
            },
            "required": ["ticket"],
        },
    },
    "positions_get": {
        "description": "Get all open positions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "ticket": {"type": "integer"},
            },
        },
    },
    "positions_total": {
        "description": "Get total number of open positions.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "orders_get": {
        "description": "Get all pending orders.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "ticket": {"type": "integer"},
            },
        },
    },
    "orders_total": {
        "description": "Get total number of pending orders.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "account_info": {
        "description": "Get full account information.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "get_terminal_info": {
        "description": "Get MT5 terminal information.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "history_orders_get": {
        "description": "Get historical orders within a date range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "symbol": {"type": "string"},
                "group": {"type": "string"},
                "position": {"type": "integer"},
            },
            "required": ["date_from", "date_to"],
        },
    },
    "history_orders_total": {
        "description": "Get count of historical orders.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
            },
            "required": ["date_from", "date_to"],
        },
    },
    "history_deals_get": {
        "description": "Get historical deals within a date range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "symbol": {"type": "string"},
                "group": {"type": "string"},
                "position": {"type": "integer"},
            },
            "required": ["date_from", "date_to"],
        },
    },
    "history_deals_total": {
        "description": "Get count of historical deals.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
            },
            "required": ["date_from", "date_to"],
        },
    },
    "get_trading_statistics": {
        "description": "Compute comprehensive trading statistics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
            },
            "required": ["date_from", "date_to"],
        },
    },
    "market_book_subscribe": {
        "description": "Subscribe to market depth (DOM) for a symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
            },
            "required": ["symbol"],
        },
    },
    "market_book_get": {
        "description": "Get current market depth snapshot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
            },
            "required": ["symbol"],
        },
    },
    "market_book_unsubscribe": {
        "description": "Unsubscribe from market depth.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
            },
            "required": ["symbol"],
        },
    },
    "get_market_regime": {
        "description": "Classify current market regime using ADX, ATR, and EMA200.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "timeframe": {"type": "string"},
                "lookback": {"type": "integer"},
            },
            "required": ["symbol", "timeframe"],
        },
    },
    "get_correlation_matrix": {
        "description": "Compute Pearson correlation between symbols.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": {"type": "string"}},
                "timeframe": {"type": "string"},
                "lookback": {"type": "integer"},
            },
            "required": ["symbols", "timeframe"],
        },
    },
    "get_strategy_context": {
        "description": "Retrieve the current strategy context memo.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "set_strategy_context": {
        "description": "Set the strategy context memo. Max 2000 chars.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "context": {"type": "string"},
            },
            "required": ["context"],
        },
    },
    "get_agent_memory": {
        "description": "Retrieve a named memory value.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
            },
            "required": ["key"],
        },
    },
    "set_agent_memory": {
        "description": "Store a named memory value. Disk-backed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
    "get_risk_status": {
        "description": "Get current risk subsystem status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "get_risk_limits": {
        "description": "View all configured risk limits.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    "get_drawdown_analysis": {
        "description": "Get drawdown analysis for a date range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
            },
            "required": ["date_from", "date_to"],
        },
    },
    "get_audit_summary": {
        "description": "Get audit log summary for a time period.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hours": {"type": "integer"},
                "event_filter": {"type": "string"},
            },
        },
    },
    "verify_audit_chain": {
        "description": "Verify audit log chain integrity.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "terminal_get_info": {
        "description": "Get MT5 terminal info.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "terminal_get_data_path": {
        "description": "Get MT5 terminal data directory path.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "terminal_get_common_path": {
        "description": "Get MT5 common data directory path.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "chart_list": {
        "description": "List all open charts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "chart_open": {
        "description": "Open a new chart.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "timeframe": {"type": "string"},
            },
            "required": ["symbol", "timeframe"],
        },
    },
    "chart_close": {
        "description": "Close a chart.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_id": {"type": "integer"},
            },
            "required": ["chart_id"],
        },
    },
    "chart_screenshot": {
        "description": "Capture chart as PNG.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_id": {"type": "integer"},
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "align_to_right": {"type": "boolean"},
            },
            "required": ["chart_id"],
        },
    },
    "chart_set_symbol_timeframe": {
        "description": "Change chart symbol and/or timeframe.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_id": {"type": "integer"},
                "symbol": {"type": "string"},
                "timeframe": {"type": "string"},
            },
            "required": ["chart_id"],
        },
    },
    "chart_apply_template": {
        "description": "Apply a .tpl template to a chart.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_id": {"type": "integer"},
                "template_name": {"type": "string"},
            },
            "required": ["chart_id", "template_name"],
        },
    },
    "chart_save_template": {
        "description": "Save chart as a .tpl template.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_id": {"type": "integer"},
                "template_name": {"type": "string"},
            },
            "required": ["chart_id", "template_name"],
        },
    },
    "chart_navigate": {
        "description": "Navigate chart to a position.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_id": {"type": "integer"},
                "position": {"type": "string", "enum": ["begin", "end", "current"]},
                "shift": {"type": "integer"},
            },
            "required": ["chart_id", "position"],
        },
    },
    "chart_indicator_add": {
        "description": "Attach an indicator to a chart.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_id": {"type": "integer"},
                "indicator_path": {"type": "string"},
                "window": {"type": "integer"},
                "parameters": {"type": "object"},
            },
            "required": ["chart_id", "indicator_path"],
        },
    },
    "chart_indicator_list": {
        "description": "List indicators on a chart.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_id": {"type": "integer"},
                "window": {"type": "integer"},
            },
            "required": ["chart_id"],
        },
    },
    "chart_attach_ea": {
        "description": "Attach an Expert Advisor to a chart.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_id": {"type": "integer"},
                "ea_name": {"type": "string"},
            },
            "required": ["chart_id", "ea_name"],
        },
    },
    "chart_remove_ea": {
        "description": "Remove/detach an Expert Advisor from a chart.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart_id": {"type": "integer"},
            },
            "required": ["chart_id"],
        },
    },
    "mql5_write_file": {
        "description": "Write MQL5 source code to terminal directory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "source_code": {"type": "string"},
                "overwrite": {"type": "boolean"},
            },
            "required": ["filename", "source_code"],
        },
    },
    "mql5_compile": {
        "description": "Compile .mq5 source with MetaEditor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "include_path": {"type": "string"},
            },
            "required": ["filename"],
        },
    },
    "mql5_list_files": {
        "description": "List MQL5 source and compiled files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string"},
                "extension": {"type": "string"},
            },
        },
    },
    "mql5_read_file": {
        "description": "Read MQL5 source file content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
            },
            "required": ["filename"],
        },
    },
    "mql5_run_script": {
        "description": "Run an MQL5 script once.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "script_name": {"type": "string"},
                "symbol": {"type": "string", "description": "Symbol name (e.g. EURUSD)"},
                "period": {
                    "type": "integer",
                    "description": "Timeframe in minutes (1,5,15,30,60,240,1440,10080,43200)",
                },
                "parameters": {"type": "object", "description": "Script parameters"},
            },
            "required": ["script_name"],
        },
    },
    "mql5_get_compile_errors": {
        "description": "Retrieve MetaEditor compilation errors.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Optional: specific file to check (e.g. Experts/MyEA.mq5)",
                },
            },
        },
    },
    "backtest_run": {
        "description": "Run a backtest in Strategy Tester.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ea_name": {"type": "string"},
                "symbol": {"type": "string"},
                "timeframe": {"type": "string"},
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "initial_deposit": {
                    "type": "number",
                    "description": "Initial deposit (default 10000)",
                },
                "leverage": {
                    "type": "integer",
                    "description": "Leverage (default 100)",
                },
                "model": {
                    "type": "string",
                    "enum": ["every_tick", "ohlc_m1", "open_prices"],
                    "description": "Backtest model (default every_tick)",
                },
                "optimization": {
                    "type": "boolean",
                    "description": "Run optimisation pass (default false)",
                },
            },
            "required": ["ea_name", "symbol", "timeframe", "date_from", "date_to"],
        },
    },
    "backtest_optimize": {
        "description": "Run parameter optimisation in Strategy Tester.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ea_name": {"type": "string"},
                "symbol": {"type": "string"},
                "timeframe": {"type": "string"},
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "parameters": {
                    "type": "array",
                    "description": "[{name, start, step, stop}]",
                },
                "criterion": {
                    "type": "string",
                    "description": "Optimisation criterion (default balance)",
                },
            },
            "required": ["ea_name", "symbol", "timeframe", "date_from", "date_to"],
        },
    },
    "backtest_list_results": {
        "description": "List available backtest result files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ea_name": {"type": "string"},
            },
        },
    },
    "backtest_get_results": {
        "description": "Get detailed backtest results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
            },
            "required": ["job_id"],
        },
    },
}

# =============================================================================
# TOOL HANDLERS
# =============================================================================

_TOOL_HANDLERS: dict[str, Callable[..., Any]] = {}


def _handler(name: str) -> Callable:
    """Decorator to register a tool handler."""

    def decorator(fn: Callable) -> Callable:
        _TOOL_HANDLERS[name] = fn
        return fn

    return decorator


# ---- CONNECTION TOOLS ----


@_handler("initialize")
async def handle_initialize(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.connection import InitializeInput
    from synx_mt5.tools.connection import handle_initialize as fn

    inp = InitializeInput.model_validate(args or {})
    return await fn(s.connection_manager, inp)


@_handler("get_connection_status")
async def handle_get_connection_status(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.connection import handle_get_connection_status as fn

    return await fn(s.connection_manager)


@_handler("shutdown")
async def handle_shutdown(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.connection import ShutdownInput
    from synx_mt5.tools.connection import handle_shutdown as fn

    inp = ShutdownInput.model_validate(args or {})
    return await fn(s.connection_manager, inp)


# ---- MARKET DATA TOOLS ----


@_handler("get_symbols")
async def handle_get_symbols(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.market_data import handle_get_symbols

    return await handle_get_symbols(s.market_data_service, args)


@_handler("get_symbols_total")
async def handle_get_symbols_total(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.market_data import handle_get_symbols_total

    return await handle_get_symbols_total(s.market_data_service, args)


@_handler("get_symbol_info")
async def handle_get_symbol_info(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.market_data import handle_get_symbol_info

    return await handle_get_symbol_info(s.market_data_service, args)


@_handler("get_symbol_info_tick")
async def handle_get_symbol_info_tick(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.market_data import handle_get_symbol_info_tick

    return await handle_get_symbol_info_tick(s.market_data_service, args)


@_handler("copy_rates_from_pos")
async def handle_copy_rates_from_pos(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.market_data import handle_copy_rates_from_pos

    return await handle_copy_rates_from_pos(s.market_data_service, args)


@_handler("copy_rates_from")
async def handle_copy_rates_from(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.market_data import handle_copy_rates_from

    return await handle_copy_rates_from(s.market_data_service, args)


@_handler("copy_rates_range")
async def handle_copy_rates_range(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.market_data import handle_copy_rates_range

    return await handle_copy_rates_range(s.market_data_service, args)


@_handler("copy_ticks_from")
async def handle_copy_ticks_from(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.market_data import handle_copy_ticks_from

    return await handle_copy_ticks_from(s.market_data_service, args)


@_handler("copy_ticks_range")
async def handle_copy_ticks_range(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.market_data import handle_copy_ticks_range

    return await handle_copy_ticks_range(s.market_data_service, args)


@_handler("symbol_select")
async def handle_symbol_select(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.terminal_mgmt import handle_symbol_select

    return await handle_symbol_select(s.terminal_mgmt_service, args)


# ---- INTELLIGENCE TOOLS ----


@_handler("get_market_regime")
async def handle_get_market_regime(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.intelligence import handle_get_market_regime

    return await handle_get_market_regime(s.intelligence_service, args)


@_handler("get_correlation_matrix")
async def handle_get_correlation_matrix(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.intelligence import handle_get_correlation_matrix

    return await handle_get_correlation_matrix(s.intelligence_service, args)


@_handler("get_strategy_context")
async def handle_get_strategy_context(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.intelligence import handle_get_strategy_context

    return await handle_get_strategy_context(s.intelligence_service, args)


@_handler("set_strategy_context")
async def handle_set_strategy_context(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.intelligence import handle_set_strategy_context

    return await handle_set_strategy_context(s.intelligence_service, args)


@_handler("get_agent_memory")
async def handle_get_agent_memory(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.intelligence import handle_get_agent_memory

    return await handle_get_agent_memory(s.intelligence_service, args)


@_handler("set_agent_memory")
async def handle_set_agent_memory(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.intelligence import handle_set_agent_memory

    return await handle_set_agent_memory(s.intelligence_service, args)


@_handler("get_drawdown_analysis")
async def handle_get_drawdown_analysis(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.intelligence import handle_get_drawdown_analysis

    return await handle_get_drawdown_analysis(s.intelligence_service, args)


# ---- EXECUTION TOOLS ----


@_handler("order_check")
async def handle_order_check(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.terminal_mgmt import handle_order_check

    return await handle_order_check(s.terminal_mgmt_service, args)


@_handler("order_calc_margin")
async def handle_order_calc_margin(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.terminal_mgmt import handle_order_calc_margin

    return await handle_order_calc_margin(s.terminal_mgmt_service, args)


@_handler("order_calc_profit")
async def handle_order_calc_profit(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.terminal_mgmt import handle_order_calc_profit

    return await handle_order_calc_profit(s.terminal_mgmt_service, args)


@_handler("order_send")
async def handle_order_send(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.execution import handle_order_send

    return await handle_order_send(s.execution_service, args)


@_handler("order_modify")
async def handle_order_modify(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.execution import handle_order_modify

    return await handle_order_modify(s.execution_service, args)


@_handler("order_cancel")
async def handle_order_cancel(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.execution import handle_order_cancel

    return await handle_order_cancel(s.execution_service, args)


@_handler("position_close")
async def handle_position_close(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.execution import handle_position_close

    return await handle_position_close(s.execution_service, args)


@_handler("position_close_partial")
async def handle_position_close_partial(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.execution import handle_position_close_partial

    return await handle_position_close_partial(s.execution_service, args)


@_handler("position_close_all")
async def handle_position_close_all(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.execution import handle_position_close_all

    return await handle_position_close_all(s.execution_service, args)


@_handler("position_modify")
async def handle_position_modify(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.execution import handle_position_modify

    return await handle_position_modify(s.execution_service, args)


# ---- POSITION MANAGEMENT TOOLS ----


@_handler("positions_get")
async def handle_positions_get(s: HandlerServices, args: dict) -> dict:
    symbol = args.get("symbol")
    ticket = args.get("ticket")
    return await s.position_service.positions_get(symbol=symbol, ticket=ticket)


@_handler("positions_total")
async def handle_positions_total(s: HandlerServices, args: dict) -> dict:
    return await s.position_service.positions_total()


@_handler("orders_get")
async def handle_orders_get(s: HandlerServices, args: dict) -> dict:
    symbol = args.get("symbol")
    ticket = args.get("ticket")
    return await s.position_service.orders_get(symbol=symbol, ticket=ticket)


@_handler("orders_total")
async def handle_orders_total(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.positions import handle_orders_total

    return await handle_orders_total(s.position_service, args)


@_handler("account_info")
async def handle_account_info(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.positions import handle_account_info

    return await handle_account_info(s.position_service, args)


@_handler("get_terminal_info")
async def handle_get_terminal_info(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.terminal_mgmt import handle_terminal_get_info

    return await handle_terminal_get_info(s.terminal_mgmt_service, args)


# ---- HISTORY TOOLS ----


@_handler("history_orders_get")
async def handle_history_orders_get(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.history import handle_history_orders_get

    return await handle_history_orders_get(s.history_service, args)


@_handler("history_orders_total")
async def handle_history_orders_total(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.history import handle_history_orders_total

    return await handle_history_orders_total(s.history_service, args)


@_handler("history_deals_get")
async def handle_history_deals_get(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.history import handle_history_deals_get

    return await handle_history_deals_get(s.history_service, args)


@_handler("history_deals_total")
async def handle_history_deals_total(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.history import handle_history_deals_total

    return await handle_history_deals_total(s.history_service, args)


@_handler("get_trading_statistics")
async def handle_get_trading_statistics(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.history import handle_get_trading_statistics

    return await handle_get_trading_statistics(s.history_service, args)


# ---- MARKET DEPTH TOOLS ----


@_handler("market_book_subscribe")
async def handle_market_book_subscribe(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.market_depth import handle_market_book_subscribe

    return await handle_market_book_subscribe(s.market_depth_service, args)


@_handler("market_book_get")
async def handle_market_book_get(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.market_depth import handle_market_book_get

    return await handle_market_book_get(s.market_depth_service, args)


@_handler("market_book_unsubscribe")
async def handle_market_book_unsubscribe(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.market_depth import handle_market_book_unsubscribe

    return await handle_market_book_unsubscribe(s.market_depth_service, args)


# ---- RISK TOOLS ----


@_handler("get_risk_status")
async def handle_get_risk_status(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.risk_tools import handle_get_risk_status

    return await handle_get_risk_status(s.risk_service, args)


@_handler("get_risk_limits")
async def handle_get_risk_limits(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.risk_tools import handle_get_risk_limits

    return await handle_get_risk_limits(s.risk_service, args)


# ---- AUDIT TOOLS ----


@_handler("get_audit_summary")
async def handle_get_audit_summary(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.risk_tools import handle_get_audit_summary

    return await handle_get_audit_summary(s.risk_service, args)


@_handler("verify_audit_chain")
async def handle_verify_audit_chain(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.risk_tools import handle_verify_audit_chain

    return await handle_verify_audit_chain(s.risk_service, args)


# ---- TERMINAL MANAGEMENT TOOLS ----


@_handler("terminal_get_data_path")
async def handle_terminal_get_data_path(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.terminal_mgmt import handle_terminal_get_data_path

    return await handle_terminal_get_data_path(s.terminal_mgmt_service, args)


@_handler("terminal_get_common_path")
async def handle_terminal_get_common_path(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.terminal_mgmt import handle_terminal_get_common_path

    return await handle_terminal_get_common_path(s.terminal_mgmt_service, args)


# ---- CHART CONTROL TOOLS ----


@_handler("chart_list")
async def handle_chart_list(s: HandlerServices, args: dict) -> dict:
    import structlog
    logger = structlog.get_logger(__name__)
    logger.info("handle_chart_list_called", has_chart_service=hasattr(s, 'chart_service'))
    return await s.chart_service.chart_list()


@_handler("chart_open")
async def handle_chart_open(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.chart_control import handle_chart_open

    return await handle_chart_open(s.chart_service, args)


@_handler("chart_close")
async def handle_chart_close(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.chart_control import handle_chart_close

    return await handle_chart_close(s.chart_service, args)


@_handler("chart_screenshot")
async def handle_chart_screenshot(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.chart_control import handle_chart_screenshot

    return await handle_chart_screenshot(s.chart_service, args)


@_handler("chart_set_symbol_timeframe")
async def handle_chart_set_symbol_timeframe(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.chart_control import handle_chart_set_symbol_timeframe

    return await handle_chart_set_symbol_timeframe(s.chart_service, args)


@_handler("chart_apply_template")
async def handle_chart_apply_template(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.chart_control import handle_chart_apply_template

    return await handle_chart_apply_template(s.chart_service, args)


@_handler("chart_save_template")
async def handle_chart_save_template(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.chart_control import handle_chart_save_template

    return await handle_chart_save_template(s.chart_service, args)


@_handler("chart_navigate")
async def handle_chart_navigate(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.chart_control import handle_chart_navigate

    return await handle_chart_navigate(s.chart_service, args)


@_handler("chart_indicator_add")
async def handle_chart_indicator_add(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.chart_control import handle_chart_indicator_add

    return await handle_chart_indicator_add(s.chart_service, args)


@_handler("chart_indicator_list")
async def handle_chart_indicator_list(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.chart_control import handle_chart_indicator_list

    return await handle_chart_indicator_list(s.chart_service, args)


@_handler("chart_attach_ea")
async def handle_chart_attach_ea(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.chart_control import handle_chart_attach_ea

    return await handle_chart_attach_ea(s.chart_service, args)


@_handler("chart_remove_ea")
async def handle_chart_remove_ea(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.chart_control import handle_chart_remove_ea

    return await handle_chart_remove_ea(s.chart_service, args)


# ---- MQL5 DEVELOPMENT TOOLS ----


@_handler("mql5_write_file")
async def handle_mql5_write_file(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.mql5_dev import handle_mql5_write_file

    return await handle_mql5_write_file(s.mql5_service, args)


@_handler("mql5_compile")
async def handle_mql5_compile(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.mql5_dev import handle_mql5_compile

    return await handle_mql5_compile(s.mql5_service, args)


@_handler("mql5_list_files")
async def handle_mql5_list_files(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.mql5_dev import handle_mql5_list_files

    return await handle_mql5_list_files(s.mql5_service, args)


@_handler("mql5_read_file")
async def handle_mql5_read_file(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.mql5_dev import handle_mql5_read_file

    return await handle_mql5_read_file(s.mql5_service, args)


@_handler("mql5_run_script")
async def handle_mql5_run_script(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.mql5_dev import handle_mql5_run_script

    return await handle_mql5_run_script(s.mql5_service, args)


@_handler("mql5_get_compile_errors")
async def handle_mql5_get_compile_errors(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.mql5_dev import handle_mql5_get_compile_errors

    return await handle_mql5_get_compile_errors(s.mql5_service, args)


# ---- STRATEGY TESTER TOOLS ----


@_handler("backtest_run")
async def handle_backtest_run(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.strategy_tester import handle_backtest_run

    return await handle_backtest_run(s.backtest_service, args)


@_handler("backtest_optimize")
async def handle_backtest_optimize(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.strategy_tester import handle_backtest_optimize

    return await handle_backtest_optimize(s.backtest_service, args)


@_handler("backtest_list_results")
async def handle_backtest_list_results(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.strategy_tester import handle_backtest_list_results

    return await handle_backtest_list_results(s.backtest_service, args)


@_handler("backtest_get_results")
async def handle_backtest_get_results(s: HandlerServices, args: dict) -> dict:
    from synx_mt5.tools.strategy_tester import handle_backtest_get_results

    return await handle_backtest_get_results(s.backtest_service, args)
