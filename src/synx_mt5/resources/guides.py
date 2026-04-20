"""Resource guide content for all mt5:// endpoints.

This module provides the static content served by each MCP resource endpoint.
Guides are comprehensive, production-grade documentation for AI agents.
"""

from typing import Any


def get_getting_started() -> str:
    return """\
# SYNX-MT5-MCP — Getting Started

## Quick Start

Welcome to SYNX-MT5-MCP. Follow this workflow at the start of every session.

### Step 1: Read Your Context
```
Read mt5://synx/active_profile
Read mt5://synx/risk_limits
```

### Step 2: Verify Connection
```
Call account_info to verify MT5 is connected
Call get_connection_status for bridge health
```

### Step 3: Set Strategy Context
```
Use set_strategy_context to document your trading plan for this session
```

### Step 4: Understand Your Boundaries
```
Read mt5://synx/python_api_boundary  # What you can and cannot do via Python API
Read mt5://synx/trading_guide         # Order types, filling modes, MT5 constants
```

### Step 5: Optional — Market Intelligence
```
Call get_market_regime for current market conditions
Call get_correlation_matrix for cross-symbol correlations
```

## Your Capability Profile

Execution tools (order_send, position_close, etc.) require human approval by default.
Risk limits are enforced deterministically — the server will block orders that exceed
configured limits.

## Available Tool Categories

| Category | Example Tools |
|---|---|
| Market Data | get_symbols, copy_rates_from_pos, get_symbol_info_tick |
| Intelligence | get_market_regime, get_correlation_matrix, get_agent_memory |
| Account | account_info, positions_get, orders_get |
| Execution | order_send, position_close, order_modify (requires approval) |
| History | history_deals_get, get_trading_statistics |
| Risk | get_risk_status, get_drawdown_analysis |
| Chart Control | chart_screenshot, chart_indicator_add (requires SYNX_EA) |
| MQL5 Dev | mql5_compile, mql5_write_file (requires MetaEditor) |

## Safety Features

- **Execution requires HITL approval** for all execution tools
- **Risk limits are enforced** — orders are blocked before reaching MT5
- **Idempotency** — duplicate order retries are blocked
- **Audit chain** — all operations are recorded with tamper-evident hashes
- **Prompt injection shield** — all market data is sanitised before agent context
"""


def get_security_model() -> str:
    return """\
# Security Model

## Defense Layers

SYNX-MT5-MCP implements 6 independent security layers:

### Layer 1: Credential Vault
- MT5 credentials stored in OS keyring (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- Credentials read once at startup, held in SecureString, zeroed after use
- Never written to shell history, environment variables, or log files
- For CI/CD: SYNX_VAULT_* environment variables consumed and zeroed at startup

### Layer 2: Prompt Injection Shield
- All market data, broker messages, and EA output passed through injection shield
- Pattern matching against 15+ instruction override patterns
- Control character and Unicode bidi attack sanitisation
- Injection violations logged and blocked

### Layer 3: Capability Profiles
Four graduated profiles control what tools the agent can access:

| Profile | Description |
|---|---|
| read_only | Market data only, no account info |
| analyst | Full market data + account + intelligence, no execution |
| executor | Analyst + order execution within risk limits |
| full | All tools (dangerous, HITL strongly recommended) |

### Layer 4: Risk Guard
Deterministic middleware between agent and MT5:
- Pre-flight validator (SL required, minimum R:R, position limits)
- Position sizing engine (volume capped by risk per trade %)
- Drawdown circuit breaker (suspends execution on drawdown breach)
- HITL approval gate (human confirms before any execution)

### Layer 5: Idempotency Engine
- Every order gets a unique magic number
- Duplicate orders within TTL window are rejected
- No accidental double-fills from LLM retry storms

### Layer 6: Audit Chain
- Append-only JSONL with SHA-256 hash chain
- All tool invocations, risk decisions, and HITL events recorded
- `synx-mt5 audit verify` detects tampering

## Threat Model

| Threat | Protection |
|---|---|
| Credential harvester (T1) | Keyring vault, never in args/env/logs |
| Prompt injection (T2) | Injection shield on all market data |
| Tool poisoning (T3) | Static schemas, metadata hash on startup |
| Supply chain (T4) | Pinned deps, pip-audit in CI |
| Hallucination orders (T5) | Risk limits + HITL gate |
| Duplicate fills (T6) | Idempotency engine |
"""


def get_trading_guide() -> str:
    return """\
# Trading Guide

## Order Types

### Market Orders
- `ORDER_TYPE_BUY` — Buy at current ask price
- `ORDER_TYPE_SELL` — Sell at current bid price

### Pending Orders
- `ORDER_TYPE_BUY_LIMIT` — Buy below current price
- `ORDER_TYPE_SELL_LIMIT` — Sell above current price
- `ORDER_TYPE_BUY_STOP` — Buy above current price
- `ORDER_TYPE_SELL_STOP` — Sell below current price

## Filling Modes

MT5 brokers support different filling modes:

| Mode | Constant | Behaviour |
|---|---|---|
| IOC | ORDER_FILLING_IOC | Fill as much as possible, cancel remainder |
| FOK | ORDER_FILLING_FOK | Fill all or nothing |
| Return | ORDER_FILLING_RETURN | Partial fill, return remainder as order |

Configure via `bridge.filling_mode` in synx.yaml.

## Slippage

Configure via `bridge.slippage_points` in synx.yaml (in broker tick units).
Default: 20 points (2 pips for 5-digit brokers).

## MT5 Trade Constants

```
ORDER_TYPE_BUY  = 0
ORDER_TYPE_SELL = 1
ORDER_TYPE_BUY_LIMIT = 2
ORDER_TYPE_SELL_LIMIT = 3
ORDER_TYPE_BUY_STOP = 4
ORDER_TYPE_SELL_STOP = 5

ORDER_TIME_GTC = 0  # Good-till-cancelled (default)

TRADE_ACTION_DEAL = 1
TRADE_ACTION_PENDING = 2
TRADE_ACTION_SLTP = 3
TRADE_ACTION_MODIFY = 4
TRADE_ACTION_REMOVE = 5
```

## Order Send Workflow

1. `order_check` — Dry-run to verify order would be accepted
2. `order_calc_margin` — Calculate required margin
3. `order_calc_profit` — Calculate potential P&L
4. `order_send` — Place the order (passes through full risk stack)

## Position Management

- `position_close` — Close by ticket
- `position_close_partial` — Close partial volume by ticket
- `position_close_all` — Close ALL positions (requires full profile + confirm=true)

## Important Notes

- Comment field: max 31 characters, auto-sanitised
- Magic number: auto-generated by idempotency engine (do not set manually)
- SL and TP: in symbol price units, not pips
"""


def get_market_data_guide() -> str:
    return """\
# Market Data Guide

## Timeframes

| Name | MQL5 Constant | Description |
|---|---|---|
| M1 | PERIOD_M1 | 1 minute |
| M5 | PERIOD_M5 | 5 minutes |
| M15 | PERIOD_M15 | 15 minutes |
| M30 | PERIOD_M30 | 30 minutes |
| H1 | PERIOD_H1 | 1 hour |
| H4 | PERIOD_H4 | 4 hours |
| D1 | PERIOD_D1 | Daily |
| W1 | PERIOD_W1 | Weekly |
| MN1 | PERIOD_MN1 | Monthly |

## OHLCV Data

`copy_rates_from_pos`, `copy_rates_from`, `copy_rates_range` return:

```json
{
  "time": 1712505600,      // Unix timestamp
  "open": 1.08432,
  "high": 1.08455,
  "low": 1.08420,
  "close": 1.08450,
  "tick_volume": 12345,
  "spread": 12,             // In points (12 = 1.2 pips for 5-digit)
  "real_volume": 9876       // Renko/counter volume (MT5 specific)
}
```

## Tick Data

`copy_ticks_from`, `copy_ticks_range` return:

```json
{
  "time": 1712505600123,    // Unix timestamp with ms
  "bid": 1.08432,
  "ask": 1.08435,
  "last": 1.08433,
  "volume": 100,
  "flags": 6               // Tick flags (bid/ask/last changed)
}
```

## Rate Limits

Market data tools are rate-limited per profile:
- `copy_rates_from_pos`: 60 calls/min
- `copy_ticks_from`: 30 calls/min

Use `copy_rates_range` for bulk historical data requests.

## Symbol Conventions

- Symbol names are broker-specific (e.g., "EURUSD", "XAUUSD", "BTCUSD")
- Use `get_symbols` to discover available symbols
- Use `get_symbol_info` for contract specifications (lot size, spread, etc.)
- Use `get_symbol_info_tick` for current bid/ask/last/volume
- For forex, 5 digits = 0.00001 pip; 4 digits = 0.0001 pip
"""


def get_intelligence_guide() -> str:
    return """\
# Intelligence Layer Guide

## Market Regime Detection

`get_market_regime` classifies the current market state using ADX, ATR, and EMA200.

### Regime Types

| Regime | Meaning | Strategy Implication |
|---|---|---|
| TRENDING_UP | ADX > 25, price > EMA200 | Trend-following entries |
| TRENDING_DOWN | ADX > 25, price < EMA200 | Short entries |
| RANGING | ADX < 25 | Range-bound strategies |
| HIGH_VOLATILITY | ATR expansion detected | Wider SL, smaller size |
| LOW_VOLATILITY | Compressed ATR | Potential breakout setup |

### Configuration

```yaml
intelligence:
  regime_detector:
    adx_threshold: 25.0
    volatility_high: 0.005    # ATR/price > 0.5% = high volatility
    volatility_low: 0.001    # ATR/price < 0.1% = compressed
```

## Correlation Matrix

`get_correlation_matrix` computes Pearson correlation between symbols over a lookback period.

### Interpreting Correlations

| Value | Meaning | Risk Implication |
|---|---|---|
| +0.75 to +1.0 | Strong positive | Avoid same-direction on both |
| -0.75 to -1.0 | Strong negative | Can use as hedge |
| -0.25 to +0.25 | Weak/no correlation | Can hold both independently |

High correlations warn about concentration risk — if you're long EURUSD and GBPUSD
when correlation is +0.90, your effective exposure is ~1.8x a single position.

### Configuration

```yaml
intelligence:
  correlation:
    high_threshold: 0.75    # Flag correlations above this
```

## Agent Memory

`set_agent_memory` / `get_agent_memory` provide persistent key-value storage:

```
Key: alphanumeric + underscores only (e.g., "session_notes", "eurusd_entry")
Value: any JSON-serialisable type, max 64KB
Storage: ~/.synx-mt5/agent_memory.json (disk-backed, survives restarts)
```

## Strategy Context

`set_strategy_context` / `get_strategy_context` document the trading plan:

```
Use at session start to set context
Max 2000 characters
Stored to disk, survives server restarts
Sanitised through injection shield
```

### Example Strategy Context

```
Trend-following on EUR pairs
Timeframe: H4 swing trades
Entries: Break of 20-day high with ATR confirmation
Exits: 2x ATR trailing SL or 1:2 R:R
Risk: 1% per trade, max 3 positions
Symbols: EURUSD, GBPUSD (avoid simultaneously due to correlation)
```
"""


def get_chart_control_guide() -> str:
    return """\
# Chart Control Guide

**Note:** Chart operations require the SYNX_EA MQL5 Service to be running inside MT5.
The EA provides a REST API at port 18765 (configurable).

## Bridge Requirements

Chart control tools use the SYNX_EA REST bridge mode:

```yaml
bridge:
  mode: ea_rest
  ea_rest:
    host: "127.0.0.1"
    port: 18765
```

The EA must be attached as an MQL5 Service (not an Expert Advisor).

## Available Chart Operations

| Tool | Description | Bridge |
|---|---|---|
| chart_list | List all open charts | SYNX_EA REST |
| chart_open | Open a new chart | SYNX_EA REST |
| chart_close | Close a chart | SYNX_EA REST |
| chart_screenshot | Capture chart as PNG | SYNX_EA REST |
| chart_set_symbol_timeframe | Change symbol/TF | SYNX_EA REST |
| chart_apply_template | Apply .tpl template | SYNX_EA REST |
| chart_save_template | Save chart as .tpl | SYNX_EA REST |
| chart_navigate | Scroll chart | SYNX_EA REST |
| chart_indicator_add | Attach indicator | SYNX_EA REST |
| chart_indicator_list | List indicators | SYNX_EA REST |

## What the Python API CANNOT Do

These operations are ONLY available via SYNX_EA:
- Opening/closing/navigating charts
- Capturing chart screenshots
- Applying templates
- Adding/removing indicators

## MQL5 Code Generation + Deployment Workflow

```
1. mql5_codegen.generate_indicator(spec)   # Generate MQL5 source
2. mql5_write_file("Indicators/MyRSI.mq5", source)  # Write to MT5 dir
3. mql5_compile("Indicators/MyRSI.mq5")     # Compile with MetaEditor
4. chart_open(EURUSD, H1)                   # Open chart
5. chart_indicator_add(chart_id, MyRSI)    # Attach indicator
6. chart_screenshot(chart_id)              # Verify visually
```

## Template Files

Templates (.tpl) must be in MT5's `/Profiles/Templates/` directory.
Use `chart_apply_template` to apply and `chart_save_template` to save.
"""


def get_mql5_dev_guide() -> str:
    return """\
# MQL5 Development Guide

## Architecture

MQL5 development tools invoke `metaeditor64.exe` as a subprocess.
Files are written to the MT5 terminal's MQL5/ directory.

```
mql5_write_file → Write .mq5 source to MQL5/ directory
mql5_compile → Invoke MetaEditor subprocess
mql5_list_files → List MQL5/ source and compiled files
mql5_read_file → Read source back
mql5_run_script → Execute a one-shot MQL5 script
```

## Development Workflow

### Step 1: Write Source Code

Use `mql5_write_file`:
```
filename: "Indicators/MyRSI.mq5"
source_code: <complete MQL5 source>
overwrite: false  # Fail if file exists
```

### Step 2: Compile

Use `mql5_compile`:
```
filename: "Indicators/MyRSI.mq5"
```

Returns structured error log:
```json
{
  "success": false,
  "errors": 2,
  "warnings": 1,
  "log": [
    {"line": 15, "type": "error", "message": "';' - semicolon expected"},
    {"line": 23, "type": "error", "message": "'unknown_identifier' - undeclared identifier"}
  ]
}
```

### Step 3: Attach to Chart

After successful compilation:
```
chart_indicator_add(chart_id, "Indicators/MyRSI.ex5", parameters={period: 14})
```

## MQL5 Code Generation Engine

The `mql5_codegen` service can generate complete indicators and EAs from specs:

### Indicator Spec Format

```python
spec = {
    "name": "MyRSI",
    "type": "indicator",
    "outputs": [
        {"name": "main", "type": "line", "color": "#FF0000"}
    ],
    "parameters": [
        {"name": "period", "type": "int", "default": 14, "min": 2, "max": 100}
    ]
}
```

### EA Spec Format

```python
spec = {
    "name": "MyEA",
    "type": "expert",
    "parameters": [
        {"name": "LotSize", "type": "double", "default": 0.1},
        {"name": "StopLoss", "type": "int", "default": 50},
        {"name": "TakeProfit", "type": "int", "default": 100}
    ]
}
```

## Security

- All source code passes through injection shield before writing
- Max file size: 512KB (configurable via mql5_dev.max_file_size_kb)
- Files must end in .mq5 or .mqh
- Compilation timeout: 60s default

## Limitations

- MQL5 compilation requires MetaEditor installed (ships with MT5)
- Indicator buffer values cannot be read directly from Python
  (deploy custom indicator that writes to MQL5/Files/, read via EA bridge)
"""


def get_python_api_boundary() -> str:
    return """\
# Python API Boundary — Verified 32 Functions

The official MetaTrader5 Python package exposes exactly 32 functions.
This document maps each function to SYNX-MT5-MCP tools.

## Connection (5 functions)

| MT5 Function | SYNX Tool | Notes |
|---|---|---|
| initialize | initialize | Path optional, auto-detect |
| login | initialize | Credentials from keyring |
| shutdown | shutdown | Full profile only |
| version | — | Available via bridge |
| last_error | — | Available via bridge |

## Terminal (1 function)

| MT5 Function | SYNX Tool | Notes |
|---|---|---|
| terminal_info | get_terminal_info | Full terminal status |

## Symbols (5 functions)

| MT5 Function | SYNX Tool | Notes |
|---|---|---|
| symbols_total | get_symbols_total | Count of available symbols |
| symbols_get | get_symbols | Pattern filter supported |
| symbol_info | get_symbol_info | Contract spec for symbol |
| symbol_info_tick | get_symbol_info_tick | Live bid/ask/last |
| symbol_select | symbol_select | Add/remove from MarketWatch |

## Market Depth / DOM (3 functions)

| MT5 Function | SYNX Tool | Notes |
|---|---|---|
| market_book_add | market_book_subscribe | Subscribe to DOM |
| market_book_get | market_book_get | Get DOM snapshot |
| market_book_release | market_book_unsubscribe | Unsubscribe |

## Rates / History (5 functions)

| MT5 Function | SYNX Tool | Notes |
|---|---|---|
| copy_rates_from | copy_rates_from | Start datetime, count |
| copy_rates_from_pos | copy_rates_from_pos | Offset from current bar |
| copy_rates_range | copy_rates_range | Date range (max bars: 50000) |
| copy_ticks_from | copy_ticks_from | Start datetime, count |
| copy_ticks_range | copy_ticks_range | Date range |

## Orders (6 functions)

| MT5 Function | SYNX Tool | Notes |
|---|---|---|
| orders_total | orders_total | Count of pending orders |
| orders_get | orders_get | List pending orders |
| order_calc_margin | order_calc_margin | Margin required |
| order_calc_profit | order_calc_profit | P&L calculation |
| order_check | order_check | Dry-run validation |
| order_send | order_send | Place order (risk stack) |

## Positions (2 functions)

| MT5 Function | SYNX Tool | Notes |
|---|---|---|
| positions_total | positions_total | Count of open positions |
| positions_get | positions_get | List open positions |

## History (5 functions)

| MT5 Function | SYNX Tool | Notes |
|---|---|---|
| history_orders_total | history_orders_total | Count historical orders |
| history_orders_get | history_orders_get | List historical orders |
| history_deals_total | history_deals_total | Count deals |
| history_deals_get | history_deals_get | List deals |

## What Cannot Be Done via Python API

These require SYNX_EA REST bridge:
- Chart open/close/navigate
- Chart screenshots
- Indicator add/remove
- Template apply/save
- DOM streaming

These require MetaEditor subprocess:
- MQL5 compilation
- Strategy Tester execution

These are architecturally impossible:
- Direct indicator value reading (use custom MQL5 indicator + EA bridge)
- Broker raw protocol access
- Strategy Tester Python backtesting (use MQL5 code gen or Python backtesting lib)
"""


def get_active_profile_content(profile_name: str, allowed_tools: list[str]) -> str:
    return f"""\
# Active Profile: {profile_name}

## Profile: {profile_name}

{_PROFILE_DESCRIPTIONS.get(profile_name, "Custom profile")}

## Allowed Tools ({len(allowed_tools)})

```
{chr(10).join(f"  - {t}" for t in sorted(allowed_tools))}
```

## Tool Access

Tools not in this list are not registered with the MCP server.
Attempting to call an unregistered tool returns a capability error.

## Changing Profiles

Edit `profile:` in your synx.yaml, then restart the server.

Available profiles:
- `read_only` — Market data only
- `analyst` — Market data + account + intelligence
- `executor` — Analyst + order execution + chart control
- `full` — All tools (dangerous)
"""


def get_risk_limits_content(risk_config: dict[str, Any]) -> str:
    lines = ["# Risk Limits", "", "## Position Limits"]
    limits = risk_config.get("risk", risk_config)
    lines.append(f"- Max risk per trade: {limits.get('max_risk_per_trade_pct', 1.0)}%")
    lines.append(f"- Min SL distance: {limits.get('min_sl_pips', 5)} pips")
    lines.append(f"- Min R:R ratio: {limits.get('min_rr_ratio', 1.0)}")
    lines.append(f"- Max positions per symbol: {limits.get('max_positions_per_symbol', 3)}")
    lines.append(f"- Max total positions: {limits.get('max_total_positions', 10)}")
    lines.append(f"- Max total exposure: {limits.get('max_total_exposure_pct', 10.0)}%")
    lines.append(f"- SL required: {limits.get('require_sl', True)}")

    cb = limits.get("circuit_breaker", {})
    lines.append("")
    lines.append("## Circuit Breaker")
    lines.append(f"- Session max drawdown: {cb.get('max_session_drawdown_pct', 3.0)}%")
    lines.append(f"- Daily max drawdown: {cb.get('max_daily_drawdown_pct', 5.0)}%")
    lines.append(f"- Cooldown: {cb.get('cooldown_seconds', 3600)}s")

    return "\n".join(lines)


def get_strategy_context_content(ctx: dict[str, Any] | None) -> str:
    if not ctx:
        return "# Strategy Context\n\nNo strategy context set. Use `set_strategy_context` to document your trading plan."
    return f"""\
# Strategy Context

**Last Updated:** {ctx.get("last_updated", "unknown")}
**Set By:** {ctx.get("set_by", "unknown")}

---

{ctx.get("context", "No content")}
"""


_PROFILE_DESCRIPTIONS: dict[str, str] = {
    "read_only": "Read-only access to market data. No account information. No order execution.",
    "analyst": "Full market data + account inspection + intelligence layer. No order execution.",
    "executor": "Full analyst access plus controlled order execution within risk limits. HITL approval required.",
    "full": "ALL tools enabled. For advanced users only. HITL strongly recommended for live trading.",
}
