# SYNX-MT5-MCP API Reference

Complete reference for all 68+ MCP tools available in SYNX-MT5-MCP v1.1.0.

## Tool Categories

1. [Terminal Management](#terminal-management) — MT5 terminal operations
2. [Market Data](#market-data) — Symbol info, OHLCV, ticks, quotes
3. [Orders & Execution](#orders--execution) — Order send, cancel, modify
4. [Positions](#positions) — Position management and monitoring
5. [Trading History](#trading-history) — Deals and orders history
6. [Chart Control](#chart-control) — Chart operations, indicators
7. [MQL5 Development](#mql5-development) — Compilation, code management
8. [Strategy Testing](#strategy-testing) — Backtesting and optimization
9. [Market Depth](#market-depth) — DOM and market book data
10. [Intelligence](#intelligence) — Market regime, correlation analysis
11. [Risk Management](#risk-management) — Risk limits, drawdown tracking
12. [Account Management](#account-management) — Account info, equity tracking

---

## Terminal Management

### get_terminal_info

Get MetaTrader 5 terminal information.

```
Method: get_terminal_info
Returns: {
  name: str,                    # Terminal name
  path: str,                    # Terminal installation path
  data_path: str,              # Data folder path
  company: str,                # Broker company
  language: str,               # Terminal language
  platform: int,               # Platform ID
}
```

**Use Case:** Verify terminal configuration, diagnose path issues.

**Example:**
```
Request: get_terminal_info()
Response: {
  "name": "MetaTrader 5",
  "path": "C:\\Program Files\\MetaTrader 5",
  "data_path": "C:\\Users\\user\\AppData\\Roaming\\MetaQuotes\\Terminal\\...",
  "company": "MetaQuotes Software Corp."
}
```

### get_connection_status

Get bridge connection state and session info.

```
Method: get_connection_status
Returns: {
  connected: bool,              # Overall connection status
  primary_bridge: bool,         # PythonCOM bridge status
  secondary_bridge: bool,       # EAFile bridge status
  mode: str,                    # Bridge mode (python_com/ea_file/composite)
  last_connection_time: str,    # ISO timestamp
}
```

**Use Case:** Verify bridge connectivity, diagnose connection issues.

### initialize

Initialize the MT5 bridge connection.

```
Method: initialize
Parameters:
  path: str (optional)          # Override terminal path
Returns: {
  success: bool,
  message: str
}
```

**Use Case:** Manual MT5 connection initialization.

### shutdown

Gracefully disconnect from MT5 terminal.

```
Method: shutdown
Parameters:
  force: bool (default: false)  # Force shutdown without waiting
Returns: {
  success: bool
}
```

**Use Case:** Clean server shutdown, disconnect terminals.

---

## Market Data

### get_symbol_info

Get full contract specification for a symbol.

```
Method: get_symbol_info
Parameters:
  symbol: str                   # Symbol name (e.g., "EURUSD")
Returns: {
  name: str,
  description: str,
  path: str,
  currency_base: str,
  currency_profit: str,
  currency_margin: str,
  digits: int,                  # Decimal places (4 for EURUSD)
  point: float,                 # Point value (0.0001 for forex)
  tick_size: float,
  trade_mode: int,              # 0=disabled, 1=buysell, 2=buyonly, 4=sellonly
  trade_stops_level: int,
  trade_fill_mode: int,
  volume_min: float,
  volume_max: float,
  volume_step: float,
  volume_limit: float,
  swap_long: float,
  swap_short: float,
  bid: float,
  ask: float,
  last: float,
  volume: int,
  time: int                     # Unix timestamp
}
```

**Use Case:** Get trading parameters, volume limits, precision.

**Example:**
```
Request: get_symbol_info("EURUSD")
Response: {
  "digits": 4,
  "point": 0.0001,
  "volume_min": 0.01,
  "volume_max": 100,
  "trade_mode": 1,
  "bid": 1.0850,
  "ask": 1.0851
}
```

### get_symbol_info_tick

Get current bid/ask/last/volume for a symbol.

```
Method: get_symbol_info_tick
Parameters:
  symbol: str
Returns: {
  bid: float,                   # Current bid price
  ask: float,                   # Current ask price
  last: float,                  # Last trade price
  volume: int,                  # Current volume
  time: int                     # Quote time (Unix timestamp)
}
```

**Use Case:** Get real-time prices, current bid/ask.

### copy_rates_from

Get OHLCV bars from a specific datetime.

```
Method: copy_rates_from
Parameters:
  symbol: str
  timeframe: str                # M1, M5, M15, M30, H1, H4, D1, W1, MN1
  date_from: str                # ISO 8601 datetime
  count: int                    # Number of bars (max 50000)
Returns: [
  {
    time: int,                  # Unix timestamp
    open: float,
    high: float,
    low: float,
    close: float,
    volume: int
  },
  ...
]
```

**Use Case:** Fetch historical OHLCV data for analysis, backtesting.

**Example:**
```
Request: copy_rates_from("EURUSD", "H1", "2026-04-20T00:00:00Z", 24)
Response: [
  {"time": 1713571200, "open": 1.0850, "high": 1.0860, "low": 1.0840, "close": 1.0855, "volume": 150000},
  ...24 bars total
]
```

### copy_rates_range

Get OHLCV bars within a date range.

```
Method: copy_rates_range
Parameters:
  symbol: str
  timeframe: str
  date_from: str                # ISO start date
  date_to: str                  # ISO end date
Returns: [OHLCV bars]
```

**Use Case:** Get all bars in a date range for backtesting.

### copy_rates_from_pos

Get OHLCV bars from a position offset.

```
Method: copy_rates_from_pos
Parameters:
  symbol: str
  timeframe: str
  start_pos: int                # Bar offset from current (0=most recent)
  count: int                    # Number of bars
Returns: [OHLCV bars]
```

**Use Case:** Get recent bars efficiently without datetime conversion.

### copy_ticks_from

Get tick data from a specific datetime.

```
Method: copy_ticks_from
Parameters:
  symbol: str
  date_from: str                # ISO datetime
  count: int                    # Number of ticks
  flags: int (optional)         # Tick filter flags
Returns: [
  {
    time: int,                  # Tick timestamp
    bid: float,
    ask: float,
    last: float,
    volume: int,
    flags: int
  },
  ...
]
```

**Use Case:** Get tick-level data for precise analysis.

### copy_ticks_range

Get tick data within a date range.

```
Method: copy_ticks_range
Parameters:
  symbol: str
  date_from: str
  date_to: str
  flags: int (optional)
Returns: [tick data]
```

**Use Case:** Tick-level analysis over date ranges.

### get_symbols

List all available trading symbols.

```
Method: get_symbols
Parameters:
  group: str (optional)         # Filter pattern (e.g., '*USD*')
  exact_match: bool (optional)  # Use exact match instead of pattern
Returns: [
  "EURUSD",
  "GBPUSD",
  ...
]
```

**Use Case:** Discover available symbols, find related instruments.

### get_symbols_total

Get the total number of available symbols.

```
Method: get_symbols_total
Returns: int                    # Total symbol count
```

### quote_get

Get real-time quote data for a symbol.

```
Method: quote_get
Parameters:
  symbol: str (optional)        # Current symbol if blank
Returns: {
  symbol: str,
  bid: float,
  ask: float,
  last: float,
  volume: int
}
```

**Use Case:** Get current price snapshot.

---

## Orders & Execution

### order_send

Place a market or pending order.

```
Method: order_send
Parameters:
  symbol: str                   # Symbol name
  volume: float                 # Order size in lots
  order_type: str               # BUY_MARKET, SELL_MARKET, BUY_LIMIT, SELL_LIMIT, etc.
  price: float (optional)       # Limit/stop price (required for pending orders)
  sl: float (optional)          # Stop loss price
  tp: float (optional)          # Take profit price
  comment: str (optional)       # Max 31 chars
  magic: int (optional)         # Magic number for tracking
Returns: {
  ticket: int,                  # Order ticket number
  volume: float,
  symbol: str,
  type: int,
  time_setup: int,
  type_time: int,
  state: str,
  price_open: float
}
```

**Pre-Flight Checks:**
- Symbol exists and is tradeable
- Volume within broker limits
- SL distance >= min_sl_pips
- Risk:reward ratio >= min_rr_ratio
- Total exposure within limits

**Use Case:** Execute market or pending orders.

**Example:**
```
Request: order_send("EURUSD", 0.1, "BUY_MARKET", 0, 1.0840, 1.0870)
Response: {
  "ticket": 12345,
  "symbol": "EURUSD",
  "type": "BUY",
  "price_open": 1.0850,
  "volume": 0.1
}
```

### order_check

Dry-run order validation without execution.

```
Method: order_check
Parameters:
  symbol: str
  volume: float
  order_type: str
  price: float (optional)
  sl: float (optional)
  tp: float (optional)
Returns: {
  retcode: int,                 # Return code (0 = success)
  volume: float,
  margin: float,
  comment: str
}
```

**Use Case:** Validate order parameters before sending.

### order_calc_margin

Calculate margin required for an order.

```
Method: order_calc_margin
Parameters:
  symbol: str
  volume: float
  order_type: str
  price: float
Returns: {
  margin: float,                # Margin requirement in account currency
  comment: str
}
```

**Use Case:** Check margin requirement before large orders.

### order_calc_profit

Calculate potential profit for an order.

```
Method: order_calc_profit
Parameters:
  symbol: str
  volume: float
  order_type: str
  price_open: float
  price_close: float
Returns: {
  profit: float,                # Profit in account currency
  comment: str
}
```

**Use Case:** Calculate P&L before opening position.

### order_modify

Modify stop loss, take profit, or price of a pending order.

```
Method: order_modify
Parameters:
  ticket: int                   # Order ticket to modify
  price: float (optional)       # New limit/stop price
  sl: float (optional)          # New stop loss
  tp: float (optional)          # New take profit
Returns: {
  retcode: int,
  comment: str
}
```

**Use Case:** Adjust pending order parameters.

### order_cancel

Cancel a pending order.

```
Method: order_cancel
Parameters:
  ticket: int                   # Order ticket to cancel
Returns: {
  retcode: int,
  comment: str
}
```

**Use Case:** Remove pending orders.

### orders_get

Get all pending orders (optionally filtered).

```
Method: orders_get
Parameters:
  symbol: str (optional)        # Filter by symbol
  ticket: int (optional)        # Get specific order by ticket
Returns: [
  {
    ticket: int,
    symbol: str,
    type: str,
    time_setup: int,
    state: str,
    price_open: float,
    volume: float,
    sl: float,
    tp: float,
    comment: str,
    magic: int
  },
  ...
]
```

**Use Case:** Monitor pending orders, get order details.

### orders_total

Get count of pending orders.

```
Method: orders_total
Returns: int
```

---

## Positions

### position_close

Close an open position by ticket.

```
Method: position_close
Parameters:
  ticket: int                   # Position ticket
  deviation: int (optional)     # Max slippage in points
  volume: float (optional)      # Partial close amount
Returns: {
  ticket: int,
  symbol: str,
  volume: float,
  profit: float,
  comment: str
}
```

**Use Case:** Close entire or partial positions.

### position_close_all

Close ALL open positions (destructive operation).

```
Method: position_close_all
Parameters:
  confirm: bool                 # Must be true (safety confirmation)
  symbol: str (optional)        # Filter to specific symbol
Returns: {
  closed_count: int,
  failed_count: int,
  total_profit: float
}
```

**Use Case:** Emergency close-all (use carefully).

### position_close_partial

Close a partial amount from an open position.

```
Method: position_close_partial
Parameters:
  ticket: int
  volume: float                 # Amount to close
  deviation: int (optional)
Returns: {
  ...position data
}
```

**Use Case:** Scale out of positions.

### position_modify

Modify stop loss and/or take profit of an open position.

```
Method: position_modify
Parameters:
  ticket: int
  sl: float (optional)
  tp: float (optional)
Returns: {
  retcode: int,
  comment: str
}
```

**Use Case:** Adjust risk levels on open positions.

### positions_get

Get all open positions (optionally filtered).

```
Method: positions_get
Parameters:
  symbol: str (optional)        # Filter by symbol
  ticket: int (optional)        # Get specific position
Returns: [
  {
    ticket: int,
    symbol: str,
    type: str,
    volume: float,
    price_open: float,
    price_current: float,
    sl: float,
    tp: float,
    profit: float,
    comment: str,
    magic: int,
    time_open: int
  },
  ...
]
```

**Use Case:** Monitor open positions, get P&L.

**Example:**
```
Request: positions_get("EURUSD")
Response: [
  {
    "ticket": 12345,
    "symbol": "EURUSD",
    "type": "BUY",
    "volume": 0.1,
    "price_open": 1.0850,
    "price_current": 1.0860,
    "profit": 100,
    "sl": 1.0840,
    "tp": 1.0870
  }
]
```

### positions_total

Get count of open positions.

```
Method: positions_total
Returns: int
```

---

## Trading History

### history_deals_get

Get historical deals within a date range.

```
Method: history_deals_get
Parameters:
  date_from: str                # ISO start date
  date_to: str                  # ISO end date
  symbol: str (optional)        # Filter by symbol
  position: int (optional)      # Filter by position ticket
  group: str (optional)         # Filter by symbol group
Returns: [
  {
    ticket: int,
    symbol: str,
    time: int,
    type: str,
    volume: float,
    price: float,
    profit: float,
    commission: float,
    comment: str,
    position_id: int
  },
  ...
]
```

**Use Case:** Analyze past trades, calculate statistics.

### history_deals_total

Get count of historical deals.

```
Method: history_deals_total
Parameters:
  date_from: str
  date_to: str
Returns: int
```

### history_orders_get

Get historical orders within a date range.

```
Method: history_orders_get
Parameters:
  date_from: str
  date_to: str
  symbol: str (optional)
  group: str (optional)
Returns: [
  {
    ticket: int,
    symbol: str,
    time_setup: int,
    type: str,
    state: str,
    price_open: float,
    volume: float,
    comment: str,
    position_id: int
  },
  ...
]
```

**Use Case:** Review order execution history.

### history_orders_total

Get count of historical orders.

```
Method: history_orders_total
Parameters:
  date_from: str
  date_to: str
Returns: int
```

---

## Chart Control

### chart_open

Open a new chart.

```
Method: chart_open
Parameters:
  symbol: str
  timeframe: str                # M1, M5, M15, M30, H1, H4, D1, W1, MN1
Returns: {
  chart_id: int,
  symbol: str,
  timeframe: str
}
```

**Use Case:** Open trading charts programmatically.

### chart_close

Close a chart.

```
Method: chart_close
Parameters:
  chart_id: int
Returns: {
  success: bool
}
```

### chart_set_symbol_timeframe

Change chart symbol and/or timeframe.

```
Method: chart_set_symbol_timeframe
Parameters:
  chart_id: int
  symbol: str (optional)
  timeframe: str (optional)
Returns: {
  success: bool,
  symbol: str,
  timeframe: str
}
```

**Use Case:** Navigate between charts and timeframes.

### chart_navigate

Navigate chart to a position.

```
Method: chart_navigate
Parameters:
  chart_id: int
  position: str                 # "begin" | "end" | "current"
  shift: int (optional)         # Bars to shift
Returns: {
  success: bool
}
```

### chart_screenshot

Capture chart as PNG.

```
Method: chart_screenshot
Parameters:
  chart_id: int
  width: int (optional)
  height: int (optional)
  align_to_right: bool (optional)
Returns: {
  filename: str,                # PNG file path
  size_kb: float
}
```

**Use Case:** Generate trading charts for reports.

### chart_attach_ea

Attach an Expert Advisor to a chart.

```
Method: chart_attach_ea
Parameters:
  chart_id: int
  ea_name: str                  # EA name without .ex5
Returns: {
  success: bool,
  message: str
}
```

**Use Case:** Run EAs on specific charts.

### chart_remove_ea

Remove/detach an Expert Advisor from a chart.

```
Method: chart_remove_ea
Parameters:
  chart_id: int
Returns: {
  success: bool,
  message: str
}
```

**Use Case:** Stop EAs from running.

### chart_indicator_add

Attach an indicator to a chart.

```
Method: chart_indicator_add
Parameters:
  chart_id: int
  indicator_path: str           # Full indicator name (e.g., "Moving Average")
  parameters: dict (optional)   # Input overrides (e.g., {"length": 20})
  window: int (optional)        # Chart window (0=main, 1+=subwindow)
Returns: {
  entity_id: str,               # Indicator entity ID
  name: str,
  parameters: dict
}
```

**Use Case:** Add technical indicators to charts.

**Example:**
```
Request: chart_indicator_add(12345, "Moving Average", {"length": 50, "source": "close"})
Response: {
  "entity_id": "ma_50_close",
  "name": "Moving Average",
  "parameters": {"length": 50}
}
```

### chart_indicator_list

List indicators on a chart.

```
Method: chart_indicator_list
Parameters:
  chart_id: int
  window: int (optional)        # Specific window or all
Returns: [
  {
    entity_id: str,
    name: str,
    parameters: dict,
    window: int
  },
  ...
]
```

**Use Case:** See what indicators are attached.

### chart_apply_template

Apply a .tpl template to a chart.

```
Method: chart_apply_template
Parameters:
  chart_id: int
  template_name: str
Returns: {
  success: bool,
  message: str
}
```

**Use Case:** Apply saved chart setups instantly.

### chart_save_template

Save chart as a .tpl template.

```
Method: chart_save_template
Parameters:
  chart_id: int
  template_name: str
Returns: {
  success: bool,
  path: str
}
```

**Use Case:** Save chart configurations for reuse.

---

## MQL5 Development

### mql5_write_file

Write MQL5 source code to terminal directory.

```
Method: mql5_write_file
Parameters:
  filename: str                 # Path relative to terminal (e.g., "Experts/MyEA.mq5")
  source_code: str              # MQL5 source code
  overwrite: bool (optional)    # Allow overwrite
Returns: {
  success: bool,
  path: str,
  size_bytes: int
}
```

**Use Case:** Create or update MQL5 files programmatically.

### mql5_read_file

Read MQL5 source file content.

```
Method: mql5_read_file
Parameters:
  filename: str
Returns: {
  source_code: str,
  size_bytes: int,
  path: str
}
```

**Use Case:** Read source code for analysis or modification.

### mql5_list_files

List MQL5 source and compiled files.

```
Method: mql5_list_files
Parameters:
  directory: str (optional)     # Experts, Indicators, Libraries
  extension: str (optional)     # .mq5 or .ex5
Returns: [
  {
    name: str,
    path: str,
    size_bytes: int,
    modified: int
  },
  ...
]
```

**Use Case:** Discover available MQL5 files.

### mql5_compile

Compile .mq5 source with MetaEditor.

```
Method: mql5_compile
Parameters:
  filename: str                 # Path to .mq5 file
  include_path: str (optional)  # Additional include paths
Returns: {
  success: bool,
  errors: int,
  warnings: int,
  output_file: str,             # .ex5 path if successful
  messages: [str]
}
```

**Use Case:** Compile MQL5 files, get error messages.

**Example:**
```
Request: mql5_compile("Experts/MyEA.mq5")
Response: {
  "success": true,
  "errors": 0,
  "warnings": 0,
  "output_file": "Experts/MyEA.ex5"
}
```

### mql5_get_compile_errors

Retrieve MetaEditor compilation errors.

```
Method: mql5_get_compile_errors
Parameters:
  filename: str (optional)      # Specific file or all
Returns: [
  {
    file: str,
    line: int,
    column: int,
    severity: str,              # "error" | "warning"
    message: str
  },
  ...
]
```

**Use Case:** Get detailed compilation errors for debugging.

### mql5_run_script

Run an MQL5 script once.

```
Method: mql5_run_script
Parameters:
  script_name: str
  symbol: str (optional)
  period: int (optional)        # Timeframe in minutes
  parameters: dict (optional)   # Script inputs
Returns: {
  success: bool,
  message: str
}
```

**Use Case:** Execute one-time MQL5 scripts.

---

## Strategy Testing

### backtest_run

Run a backtest in Strategy Tester.

```
Method: backtest_run
Parameters:
  ea_name: str                  # EA name without .ex5
  symbol: str
  timeframe: str
  date_from: str                # ISO date
  date_to: str
  initial_deposit: float (optional)   # Default 10000
  leverage: int (optional)      # Default 100
  model: str (optional)         # every_tick | ohlc_m1 | open_prices
  optimization: bool (optional) # Run optimization pass
Returns: {
  job_id: str,
  symbol: str,
  period: str,
  status: str                   # "completed" | "running" | "failed"
}
```

**Use Case:** Test strategy profitability over historical data.

**Example:**
```
Request: backtest_run("SR_Simple", "EURUSD", "M5", "2026-03-20", "2026-04-20")
Response: {
  "job_id": "bt_20260420_1030",
  "status": "completed",
  "symbol": "EURUSD",
  "period": "M5"
}
```

### backtest_optimize

Run parameter optimization in Strategy Tester.

```
Method: backtest_optimize
Parameters:
  ea_name: str
  symbol: str
  timeframe: str
  date_from: str
  date_to: str
  parameters: [                 # Parameters to optimize
    {
      name: str,                # Parameter name
      start: float,             # Start value
      step: float,              # Step size
      stop: float               # End value
    },
    ...
  ]
  criterion: str (optional)     # Optimization criterion (default: balance)
Returns: {
  job_id: str,
  status: str,
  best_params: dict
}
```

**Use Case:** Find optimal parameter values.

### backtest_get_results

Get detailed backtest results.

```
Method: backtest_get_results
Parameters:
  job_id: str
Returns: {
  status: str,
  symbol: str,
  period: str,
  date_from: str,
  date_to: str,
  stats: {
    initial_deposit: float,
    final_balance: float,
    net_profit: float,
    gross_profit: float,
    gross_loss: float,
    max_drawdown_pct: float,
    profit_factor: float,
    recovery_factor: float,
    sharpe_ratio: float,
    trades_total: int,
    trades_profitable: int,
    trades_losing: int,
    win_rate_pct: float,
    avg_profit_per_trade: float,
    avg_loss_per_trade: float,
    consecutive_wins: int,
    consecutive_losses: int
  },
  trades: [                     # Individual trades
    {
      ticket: int,
      symbol: str,
      type: str,
      open_time: int,
      close_time: int,
      entry_price: float,
      exit_price: float,
      volume: float,
      profit: float
    },
    ...
  ]
}
```

**Use Case:** Analyze backtest performance, profitability metrics.

**Example:**
```
Response: {
  "status": "completed",
  "stats": {
    "final_balance": 13725.33,
    "net_profit": 3725.33,
    "max_drawdown_pct": 8.2,
    "profit_factor": 2.1,
    "win_rate_pct": 62.5,
    "trades_total": 24
  }
}
```

### backtest_list_results

List available backtest result files.

```
Method: backtest_list_results
Parameters:
  ea_name: str (optional)       # Filter by EA
Returns: [
  {
    job_id: str,
    ea_name: str,
    symbol: str,
    date_created: int,
    file_path: str
  },
  ...
]
```

**Use Case:** Find saved backtest results.

---

## Market Depth

### market_book_get

Get current market depth snapshot.

```
Method: market_book_get
Parameters:
  symbol: str
Returns: {
  symbol: str,
  asks: [
    {
      price: float,
      volume: int
    },
    ...
  ],
  bids: [
    {
      price: float,
      volume: int
    },
    ...
  ]
}
```

**Use Case:** Analyze order book, detect liquidity.

### market_book_subscribe

Subscribe to market depth (DOM) for a symbol.

```
Method: market_book_subscribe
Parameters:
  symbol: str
Returns: {
  success: bool,
  message: str
}
```

**Use Case:** Enable depth-of-market updates.

### market_book_unsubscribe

Unsubscribe from market depth.

```
Method: market_book_unsubscribe
Parameters:
  symbol: str
Returns: {
  success: bool
}
```

---

## Intelligence

### get_market_regime

Classify current market regime using ADX, ATR, and EMA200.

```
Method: get_market_regime
Parameters:
  symbol: str
  timeframe: str
  lookback: int (optional)      # Bars to analyze
Returns: {
  symbol: str,
  regime: str,                  # "trending" | "ranging" | "volatile"
  adx: float,
  atr_pct: float,
  ema200: float,
  price: float,
  bias: str                     # "bullish" | "bearish" | "neutral"
}
```

**Use Case:** Classify market conditions for strategy selection.

**Example:**
```
Request: get_market_regime("EURUSD", "H1")
Response: {
  "regime": "trending",
  "adx": 28.5,
  "atr_pct": 0.002,
  "bias": "bullish"
}
```

### get_correlation_matrix

Compute Pearson correlation between symbols.

```
Method: get_correlation_matrix
Parameters:
  symbols: [str]                # List of symbols
  timeframe: str
  lookback: int (optional)      # Bars to analyze
Returns: {
  matrix: {
    "EURUSD": {
      "GBPUSD": 0.85,
      "EURJPY": 0.72,
      ...
    },
    ...
  },
  warnings: [str]               # High correlation warnings
}
```

**Use Case:** Detect correlated symbols, manage portfolio risk.

**Example:**
```
Request: get_correlation_matrix(["EURUSD", "GBPUSD", "EURJPY"], "D1")
Response: {
  "matrix": {
    "EURUSD": {"GBPUSD": 0.88, "EURJPY": 0.75},
    "GBPUSD": {"EURUSD": 0.88, "EURJPY": 0.62}
  },
  "warnings": ["EURUSD and GBPUSD highly correlated (0.88)"]
}
```

### get_trading_statistics

Compute comprehensive trading statistics.

```
Method: get_trading_statistics
Parameters:
  date_from: str
  date_to: str
Returns: {
  trades_total: int,
  trades_profitable: int,
  trades_losing: int,
  win_rate_pct: float,
  gross_profit: float,
  gross_loss: float,
  net_profit: float,
  profit_factor: float,
  avg_profit: float,
  avg_loss: float,
  avg_trade_duration: int,
  max_consecutive_wins: int,
  max_consecutive_losses: int,
  largest_win: float,
  largest_loss: float,
  recovery_factor: float
}
```

**Use Case:** Analyze trading performance metrics.

### get_drawdown_analysis

Get drawdown analysis for a date range.

```
Method: get_drawdown_analysis
Parameters:
  date_from: str
  date_to: str
Returns: {
  max_drawdown_pct: float,
  max_drawdown_value: float,
  current_drawdown_pct: float,
  recovery_time_days: int,
  drawdown_events: [
    {
      start_time: int,
      end_time: int,
      peak_equity: float,
      trough_equity: float,
      drawdown_pct: float
    },
    ...
  ]
}
```

**Use Case:** Analyze equity curve, recovery patterns.

---

## Risk Management

### get_risk_limits

View all configured risk limits.

```
Method: get_risk_limits
Returns: {
  max_risk_per_trade_pct: float,
  max_total_exposure_pct: float,
  max_positions_per_symbol: int,
  max_total_positions: int,
  require_sl: bool,
  min_sl_pips: int,
  min_rr_ratio: float,
  circuit_breaker: {
    max_session_drawdown_pct: float,
    max_daily_drawdown_pct: float,
    cooldown_seconds: int
  }
}
```

**Use Case:** Verify risk configuration is as intended.

### get_risk_status

Get current risk subsystem status.

```
Method: get_risk_status
Returns: {
  circuit_breaker_state: str,   # "CLOSED" | "OPEN" | "RECOVERY"
  current_drawdown_pct: float,
  max_session_drawdown_pct: float,
  max_daily_drawdown_pct: float,
  positions_open: int,
  total_exposure_pct: float,
  risk_per_trade_pct: float,
  last_check_time: int
}
```

**Use Case:** Monitor real-time risk status.

---

## Account Management

### account_info

Get account information and statistics.

```
Method: account_info
Returns: {
  login: int,
  trade_mode: int,              # 0=demo, 1=real
  leverage: int,
  limit_orders: int,
  currency_digits: int,
  fifo_close: bool,
  balance: float,
  credit: float,
  profit: float,
  equity: float,
  margin: float,
  margin_free: float,
  margin_level: float,
  margin_so_call: float,
  margin_so_so: float,
  deals_limit: int,
  company: str,
  name: str,
  server: str,
  currency: str,
  path: str,
  phone: str,
  email: str,
  address: str,
  comment: str,
  id: str,
  status: str,
  notifications: bool,
  mqid: bool
}
```

**Use Case:** Get account details, equity, margin levels.

**Example:**
```
Response: {
  "login": 1234567,
  "trade_mode": 0,              # Demo
  "balance": 10000.00,
  "profit": 150.50,
  "equity": 10150.50,
  "margin_free": 10150.50,
  "leverage": 100
}
```

---

## Utility Functions

### symbol_select

Add or remove a symbol from MarketWatch.

```
Method: symbol_select
Parameters:
  symbol: str
  select: bool                  # true to add, false to remove
Returns: {
  success: bool,
  message: str
}
```

**Use Case:** Manage symbols in MarketWatch.

### get_agent_memory

Retrieve a named memory value.

```
Method: get_agent_memory
Parameters:
  key: str
Returns: str                    # Stored value
```

**Use Case:** Retrieve persistent agent state.

### set_agent_memory

Store a named memory value (disk-backed).

```
Method: set_agent_memory
Parameters:
  key: str
  value: str
Returns: {
  success: bool
}
```

**Use Case:** Store persistent agent state (survives restarts).

### get_strategy_context

Retrieve the current strategy context memo.

```
Method: get_strategy_context
Returns: str                    # Current context (max 2000 chars)
```

**Use Case:** Get agent's current strategy plan.

### set_strategy_context

Set the strategy context memo.

```
Method: set_strategy_context
Parameters:
  context: str                  # New context (max 2000 chars)
Returns: {
  success: bool
}
```

**Use Case:** Update agent's current strategy notes.

### get_audit_summary

Get audit log summary for a time period.

```
Method: get_audit_summary
Parameters:
  hours: int (optional)         # Last N hours
  event_filter: str (optional)  # Filter pattern
Returns: [
  {
    timestamp: int,
    event: str,
    tool: str,
    success: bool,
    message: str
  },
  ...
]
```

**Use Case:** Review audit log, audit compliance.

### verify_audit_chain

Verify audit log chain integrity.

```
Method: verify_audit_chain
Returns: {
  valid: bool,
  entries_verified: int,
  first_entry_time: int,
  last_entry_time: int,
  any_tampering: bool
}
```

**Use Case:** Verify audit log hasn't been modified.

---

## Tool Count Summary

**Total: 68 MCP Tools**

- Terminal Management: 4 tools
- Market Data: 8 tools
- Orders & Execution: 8 tools
- Positions: 5 tools
- Trading History: 4 tools
- Chart Control: 11 tools
- MQL5 Development: 6 tools
- Strategy Testing: 4 tools
- Market Depth: 2 tools
- Intelligence: 4 tools
- Risk Management: 2 tools
- Account Management: 1 tool
- Utility: 6 tools

## See Also

- [Setup Guide](SETUP.md) — Initial configuration
- [Configuration Reference](CONFIG.md) — Tool options
- [Risk Management Guide](RISK.md) — Risk parameters
- [Troubleshooting](TROUBLESHOOTING.md) — Common issues
