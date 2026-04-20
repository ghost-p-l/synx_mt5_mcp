# Python API Boundary

## Verified 32 Functions

The official MetaTrader5 Python package exposes exactly **32 functions**. This document maps them to SYNX-MT5-MCP tools.

### Connection (5 functions)

| Function | Tool | Description |
|----------|------|-------------|
| `initialize()` | `initialize` | Initialize MT5 terminal |
| `login()` | (internal) | Login to account |
| `shutdown()` | `shutdown` | Disconnect from terminal |
| `version()` | (internal) | Get MT5 version |
| `last_error()` | (internal) | Get last error |

### Terminal (1 function)

| Function | Tool | Description |
|----------|------|-------------|
| `terminal_info()` | `get_terminal_info` | Get terminal status |

### Symbols (5 functions)

| Function | Tool | Description |
|----------|------|-------------|
| `symbols_total()` | `get_symbols_total` | Count available symbols |
| `symbols_get()` | `get_symbols` | List symbols matching filter |
| `symbol_info()` | `get_symbol_info` | Get symbol contract spec |
| `symbol_info_tick()` | `get_symbol_info_tick` | Get current bid/ask |
| `symbol_select()` | `symbol_select` | Add/remove from MarketWatch |

### Market Depth (3 functions)

| Function | Tool | Description |
|----------|------|-------------|
| `market_book_add()` | `market_book_subscribe` | Subscribe to DOM |
| `market_book_get()` | `market_book_get` | Get DOM snapshot |
| `market_book_release()` | `market_book_unsubscribe` | Release subscription |

### Rates/History (5 functions)

| Function | Tool | Description |
|----------|------|-------------|
| `copy_rates_from()` | `copy_rates_from` | OHLCV from datetime |
| `copy_rates_from_pos()` | `copy_rates_from_pos` | OHLCV from position |
| `copy_rates_range()` | `copy_rates_range` | OHLCV in date range |
| `copy_ticks_from()` | `copy_ticks_from` | Ticks from datetime |
| `copy_ticks_range()` | `copy_ticks_range` | Ticks in date range |

### Orders (6 functions)

| Function | Tool | Description |
|----------|------|-------------|
| `orders_total()` | `orders_total` | Count pending orders |
| `orders_get()` | `orders_get` | Get pending orders |
| `order_calc_margin()` | `order_calc_margin` | Calculate margin |
| `order_calc_profit()` | `order_calc_profit` | Calculate profit |
| `order_check()` | `order_check` | Validate order |
| `order_send()` | `order_send` | Place order |

### Positions (2 functions)

| Function | Tool | Description |
|----------|------|-------------|
| `positions_total()` | `positions_total` | Count open positions |
| `positions_get()` | `positions_get` | Get open positions |

### History (5 functions)

| Function | Tool | Description |
|----------|------|-------------|
| `history_orders_total()` | `history_orders_total` | Count historical orders |
| `history_orders_get()` | `history_orders_get` | Get historical orders |
| `history_deals_total()` | `history_deals_total` | Count historical deals |
| `history_deals_get()` | `history_deals_get` | Get historical deals |

## What This Means

**Python API is complete for:**
- Market data retrieval
- Order execution
- Position management
- Account inspection

**Python API CANNOT:**
- Open/close charts
- Take screenshots
- Add indicators
- Compile MQL5
- Control Strategy Tester

These capabilities require the **SYNX_EA REST bridge** or **MetaEditor subprocess**.
