# SYNX-MT5-MCP Configuration Reference

Complete reference for all configuration options in `~/.synx-mt5/synx.yaml`.

## Server Configuration

```yaml
server:
  name: "synx_mt5_mcp"                # Server name (displayed in logs)
  version: "1.1.0"                    # Version (auto-managed)
  log_level: "INFO"                   # DEBUG | INFO | WARNING | ERROR
  log_format: "json"                  # json | text
  storage_path: "~/.synx-mt5"         # Path for audit logs, agent memory, strategy context
```

### Log Levels

- **DEBUG** — Verbose output, all function calls, data structures
- **INFO** — Normal operation, important events
- **WARNING** — Potential issues, unusual conditions
- **ERROR** — Errors only, fatal issues

### Log Format

- **json** — Structured logs (recommended for production)
- **text** — Human-readable format (good for development)

## Transport Configuration

```yaml
transport:
  mode: "stdio"                       # stdio (terminal) | http (multi-client)
  http_host: "127.0.0.1"             # HTTP server host (if mode: http)
  http_port: 8765                    # HTTP server port
  api_key_required: true             # Require API key for HTTP access
```

### Modes

- **stdio** — Single client via standard input/output (recommended for Claude Code)
- **http** — HTTP/SSE transport for multiple clients

## Bridge Configuration

### Bridge Mode

```yaml
bridge:
  mode: "composite"                   # python_com | ea_file | composite
```

- **python_com** — Fast Python COM bridge (Windows only)
- **ea_file** — File-based IPC to SYNX_EA service
- **composite** — Both bridges with intelligent routing (recommended)

### Python COM Bridge

```yaml
bridge:
  python_com:
    terminal_path: null              # Auto-detect if null; override with explicit path
    reconnect_interval_seconds: 30    # Reconnection attempt interval
    max_retries: 5                    # Max reconnection attempts
    backoff_factor: 2.0               # Exponential backoff multiplier
```

**Example explicit path:**
```yaml
python_com:
  terminal_path: "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
```

### EA File Bridge

```yaml
bridge:
  ea_file:
    timeout_seconds: 30               # Command execution timeout
    files_dir: null                   # Auto-detect Common\Files if null
```

**For explicit file directory:**
```yaml
ea_file:
  files_dir: "C:\\Users\\<User>\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files"
```

### MetaEditor Configuration

```yaml
bridge:
  metaeditor:
    path: null                        # Auto-detect from terminal path if null
    timeout_seconds: 60               # Compilation timeout
```

### Order Execution

```yaml
bridge:
  filling_mode: "return"              # ioc | fok | return (broker dependent)
  slippage_points: 20                 # Max slippage tolerance in points
```

**Filling modes:**
- **ioc** (Immediate or Cancel) — Execute immediately or cancel
- **fok** (Fill or Kill) — Execute full amount or cancel
- **return** (Return) — Return unexecuted portion

## Capability Profile

```yaml
profile: "executor"                   # read_only | analyst | executor | full
```

### Profile Permissions

| Profile | Market Data | Intelligence | Order Execution | Chart Control | Destructive Ops |
|---------|-------------|--------------|-----------------|---------------|-----------------|
| read_only | ✓ | - | - | - | - |
| analyst | ✓ | ✓ | - | - | - |
| executor | ✓ | ✓ | ✓ | ✓ | - |
| full | ✓ | ✓ | ✓ | ✓ | ✓ |

## Risk Management Configuration

```yaml
risk:
  require_sl: true                    # Require stop loss for all orders
  min_sl_pips: 10                     # Minimum stop loss distance (pips)
  min_rr_ratio: 1.0                   # Minimum risk:reward ratio
  max_risk_per_trade_pct: 1.0         # Max risk per trade (% of equity)
  max_total_exposure_pct: 10.0        # Max total exposure (% of equity)
  max_positions_per_symbol: 3         # Max concurrent positions per symbol
  max_total_positions: 10             # Max total open positions
  
  circuit_breaker:
    max_session_drawdown_pct: 5.0     # Session drawdown trigger
    max_daily_drawdown_pct: 10.0      # Daily drawdown trigger
    cooldown_seconds: 60              # Cooldown after trigger
```

### Risk Parameters Explained

#### require_sl
If `true`, all orders must have a stop loss. Set `false` only for demo testing.

#### min_sl_pips
Minimum distance from entry to stop loss (in pips).
- Forex: 10-50 pips typical
- Crypto: 0.5-2% of price
- Demo testing: Can be 2-5 pips

#### min_rr_ratio
Minimum reward:risk ratio. For every 1 pip risked, earn at least this much.
- 1.0 = equal risk:reward
- 2.0 = 2x reward for 1x risk
- Demo testing: 0.5-0.8 acceptable

#### max_risk_per_trade_pct
Maximum equity risked per individual trade.
- Production: 0.5-1.0% (risk 0.5-1% of account per trade)
- Conservative: 0.25%
- Aggressive: 2-3% (demo only)

#### max_total_exposure_pct
Maximum total equity at risk across all open positions.
- Production: 5-10%
- Conservative: 3-5%
- Aggressive: 20-30% (demo only)

#### max_positions_per_symbol
Maximum concurrent positions on single symbol.
- Single strategy: 1
- Multi-entry strategy: 3-5
- Aggressive scalping: 10+ (demo only)

#### max_total_positions
Maximum total open positions across all symbols.
- Conservative: 5-10
- Standard: 10-20
- Aggressive: 20-50 (demo only)

### Circuit Breaker

Automatically stops trading when drawdown exceeds limits.

#### max_session_drawdown_pct
Triggers when daily session loses this % of equity.
- Production: 5.0 (stop after 5% loss)
- Conservative: 3.0
- Aggressive: 20-50% (demo testing)

#### max_daily_drawdown_pct
Hard stop for the day when equity loss reaches this %.
- Production: 10.0 (stop after 10% loss)
- Conservative: 5.0
- Aggressive: 30-80% (demo testing)

#### cooldown_seconds
Pause duration after circuit breaker triggers before resuming trading.
- Production: 60-300 seconds
- Testing: 30 seconds

## Human-in-the-Loop Configuration

```yaml
hitl:
  enabled: true                       # Enable/disable HITL approval
  tools:                              # Tools requiring approval
    - order_send
    - position_close
  timeout_seconds: 300                # Approval timeout
  sink: "terminal"                    # terminal | webhook
  webhook_url: null                   # Webhook URL (if sink: webhook)
  webhook_secret: null                # HMAC secret for webhook verification
```

### HITL Tools

Most restrictive tools require approval:
- `order_send` — Place new order
- `position_close` — Close open position
- `position_modify` — Modify SL/TP of position
- `order_cancel` — Cancel pending order

**Example restrictive configuration:**
```yaml
hitl:
  enabled: true
  tools:
    - order_send
    - position_close
```

**Example permissive (testing):**
```yaml
hitl:
  enabled: false
  tools: []
```

### HITL Sinks

#### Terminal Sink
Approval prompts appear in Claude Code terminal. User types `yes` to approve.

```yaml
hitl:
  sink: "terminal"
```

#### Webhook Sink
Approval requests sent to external service for response.

```yaml
hitl:
  sink: "webhook"
  webhook_url: "https://your-service.com/approve"
  webhook_secret: "shared-secret-for-hmac"
```

Webhook payload:
```json
{
  "tool": "order_send",
  "params": {...},
  "timestamp": "2026-04-20T10:30:00Z"
}
```

Response must include `approved: true/false`.

## Idempotency Configuration

```yaml
idempotency:
  ttl_seconds: 300                    # Cache entry time-to-live
  max_cache_size: 10000               # Maximum cache entries
```

Prevents duplicate orders from LLM retries within the TTL window.

### Tuning Idempotency

**For aggressive scalping:**
```yaml
idempotency:
  ttl_seconds: 5                      # Short window for rapid orders
  max_cache_size: 100                 # Smaller cache
```

**For standard trading:**
```yaml
idempotency:
  ttl_seconds: 300                    # 5-minute window
  max_cache_size: 10000               # Large cache
```

## Security Configuration

```yaml
security:
  prompt_injection_shield: true       # Always true, cannot be disabled
  audit_log:
    enabled: true                     # Enable audit logging
    path: "~/.synx-mt5/audit.jsonl"  # Audit log path
    chain_verification: true          # Verify cryptographic hash chain
    rotate_size_mb: 100               # Rotate log at this size
```

### Audit Logging

All operations are logged with:
- Timestamp
- User/agent
- Operation
- Parameters
- Result/error

**Audit log example:**
```json
{
  "timestamp": "2026-04-20T10:30:15Z",
  "user": "claude-code",
  "tool": "order_send",
  "params": {"symbol": "EURUSD", "volume": 0.1, "order_type": "BUY_MARKET"},
  "result": {"ticket": 12345},
  "hash": "sha256:..."
}
```

### Chain Verification

When `chain_verification: true`, each log entry includes hash of previous entry, creating tamper-evident chain.

## Intelligence Configuration

```yaml
intelligence:
  cache_ttl_seconds: 300              # Cache TTL for correlation/matrix
  regime_detector:
    adx_threshold: 25.0               # ADX threshold for trend detection
    volatility_high: 0.005            # High volatility threshold (ATR%)
    volatility_low: 0.001             # Low volatility threshold
  correlation:
    high_threshold: 0.75              # Warning threshold for high correlation
```

### Market Regime Detection

Used by intelligent risk management:

- **Trending** — ADX > threshold, low volatility
- **Ranging** — ADX < threshold, medium volatility
- **Volatile** — Any ADX, high volatility

### Correlation Warnings

When symbols have correlation > threshold:
- Log warning about correlated positions
- Recommend reducing concurrent positions
- Useful for understanding portfolio risk

## MQL5 Development Configuration

```yaml
mql5_dev:
  metaeditor_path: null              # Auto-detect; override if non-standard
  mql5_dir: null                     # Auto-detect from terminal data_path
  max_file_size_kb: 512              # Max source file size
  compile_timeout_seconds: 60        # Compilation timeout
```

## Strategy Tester Configuration

```yaml
strategy_tester:
  results_dir: null                  # Auto-detect from terminal data_path
  max_concurrent_tests: 4            # Parallel backtest runs
```

## Configuration Profiles

### Standard (Production)
Production-safe defaults for live trading.

```yaml
profile: executor
risk:
  require_sl: true
  min_sl_pips: 10
  min_rr_ratio: 1.0
  max_risk_per_trade_pct: 1.0
  max_total_exposure_pct: 10.0
  max_positions_per_symbol: 3
  max_total_positions: 10
  circuit_breaker:
    max_session_drawdown_pct: 5.0
    max_daily_drawdown_pct: 10.0
    cooldown_seconds: 60
hitl:
  enabled: true
  tools: [order_send, position_close]
```

### Testing (Demo Account)
Relaxed constraints for strategy testing.

```yaml
profile: executor
risk:
  require_sl: false
  min_sl_pips: 0
  min_rr_ratio: 0.01
  max_risk_per_trade_pct: 5.0
  max_total_exposure_pct: 50.0
  max_positions_per_symbol: 10
  max_total_positions: 50
  circuit_breaker:
    max_session_drawdown_pct: 50.0
    max_daily_drawdown_pct: 80.0
    cooldown_seconds: 30
hitl:
  enabled: false
  tools: []
idempotency:
  ttl_seconds: 5
  max_cache_size: 100
```

### Aggressive (Optimization)
Maximum flexibility for backtesting and optimization.

```yaml
profile: full
risk:
  require_sl: true
  min_sl_pips: 3
  min_rr_ratio: 0.8
  max_risk_per_trade_pct: 2.0
  max_total_exposure_pct: 20.0
  max_positions_per_symbol: 5
  max_total_positions: 20
  circuit_breaker:
    max_session_drawdown_pct: 50.0
    max_daily_drawdown_pct: 80.0
    cooldown_seconds: 60
hitl:
  enabled: false
```

## Example Configurations

### Live Forex Trading (Conservative)
```yaml
profile: executor
bridge:
  mode: composite
risk:
  require_sl: true
  min_sl_pips: 15
  min_rr_ratio: 1.5
  max_risk_per_trade_pct: 0.5
  max_total_exposure_pct: 5.0
  max_positions_per_symbol: 2
  max_total_positions: 5
hitl:
  enabled: true
  tools: [order_send, position_close]
```

### Scalping Demo (Aggressive)
```yaml
profile: executor
bridge:
  mode: composite
risk:
  require_sl: false
  min_sl_pips: 2
  min_rr_ratio: 0.5
  max_risk_per_trade_pct: 3.0
  max_total_exposure_pct: 30.0
  max_positions_per_symbol: 10
  max_total_positions: 20
hitl:
  enabled: false
idempotency:
  ttl_seconds: 5
  max_cache_size: 100
```

### Research/Backtesting
```yaml
profile: full
bridge:
  mode: composite
risk:
  require_sl: true
  min_sl_pips: 1
  min_rr_ratio: 0.1
  max_risk_per_trade_pct: 5.0
  max_total_exposure_pct: 100.0
hitl:
  enabled: false
```

## Configuration Validation

SYNX validates configuration on startup:

```
[INFO] Configuration validation:
[INFO]   ✓ Profile: executor (order_send allowed)
[INFO]   ✓ Risk: max_risk_per_trade_pct=1.0% ≤ 2.0% (safe)
[INFO]   ✓ Circuit breaker: max_session_drawdown_pct=5.0% (enabled)
[INFO]   ✓ HITL: enabled, tools=[order_send, position_close]
[INFO] Configuration OK
```

If configuration is invalid:
```
[ERROR] Configuration validation failed:
[ERROR]   max_risk_per_trade_pct=10.0% exceeds maximum 5.0%
[ERROR]   min_rr_ratio=0.1 below minimum 0.5
```

Fix and restart.

## See Also

- [Setup Guide](SETUP.md) — Installation instructions
- [Risk Management Guide](RISK.md) — Risk configuration strategies
- [Troubleshooting Guide](TROUBLESHOOTING.md) — Common configuration issues
