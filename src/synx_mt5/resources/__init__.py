"""Resources module - MCP resources and prompt templates."""

from synx_mt5.resources import guides
from synx_mt5.resources.prompts import (
    EXECUTION_WORKFLOW_PROMPT,
    REGIME_ANALYSIS_PROMPT,
    RISK_ACKNOWLEDGMENT_PROMPT,
    SESSION_START_PROMPT,
    STRATEGY_DOCUMENTATION_PROMPT,
)


class ResourceProvider:
    """Provides MCP resource content."""

    RESOURCES = {
        "getting_started": SESSION_START_PROMPT,
        "security_model": """\
# Security Model

## Defense Layers
1. Credential Vault - OS keyring
2. Injection Shield - Pattern matching
3. Capability Profiles - Graduated access
4. Risk Guard - Pre-flight, HITL
5. Idempotency - Duplicate prevention
6. Audit Chain - Tamper-evident logging
""",
        "python_api_boundary": """\
# Python API Boundary

## 32 Verified Functions
- Connection: initialize, login, shutdown
- Terminal: terminal_info
- Symbols: symbols_total, symbols_get, symbol_info, symbol_select
- Market Depth: market_book_add/get/release
- Rates: copy_rates_from, copy_rates_from_pos, copy_rates_range
- Ticks: copy_ticks_from, copy_ticks_range
- Orders: orders_total, orders_get, order_calc_margin, order_calc_profit, order_check, order_send
- Positions: positions_total, positions_get
- History: history_orders_total/get, history_deals_total/get

## What CAN do
- Market data retrieval
- Order execution
- Position management
- Account inspection

## What CANNOT do
- Chart operations (requires SYNX_EA)
- MQL5 compilation (requires MetaEditor)
""",
    }

    @classmethod
    def get_resource(cls, uri: str) -> str:
        """Get resource content by URI."""
        if uri.startswith("mt5://synx/"):
            key = uri.replace("mt5://synx/", "")
            return cls.RESOURCES.get(key, "")
        return ""


__all__ = [
    "ResourceProvider",
    "SESSION_START_PROMPT",
    "RISK_ACKNOWLEDGMENT_PROMPT",
    "STRATEGY_DOCUMENTATION_PROMPT",
    "EXECUTION_WORKFLOW_PROMPT",
    "REGIME_ANALYSIS_PROMPT",
]
