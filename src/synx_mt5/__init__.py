"""SYNX-MT5-MCP - SYstem Nexus: MT5 MCP Server for AI Trading Agents"""

__version__ = "1.1.0"
__mcp_spec_version__ = "2025-11"

from synx_mt5.audit.engine import AuditEngine
from synx_mt5.config import Config

__all__ = [
    "__version__",
    "__mcp_spec_version__",
    "Config",
    "AuditEngine",
]
