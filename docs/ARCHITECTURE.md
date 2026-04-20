# SYNX-MT5-MCP Dual-Bridge Architecture

## Overview

The **Composite Bridge** enables both `python_com` and `ea_file` bridges to work together seamlessly, providing optimal performance with enterprise-grade reliability.

### Why Dual-Bridge?

- **Performance** — Fastest bridge for each operation type
- **Reliability** — Automatic failover when one bridge fails
- **Completeness** — Access all MT5 features (both data and chart operations)
- **Flexibility** — Run on any platform/environment with proper fallback

## Architecture Components

```
SYNX-MT5-MCP
│
├─ CompositeBridge (orchestrator)
│  │
│  ├─ PythonCOMBridge (primary)
│  │  └─ Direct MT5 COM interface
│  │     ├─ Fast data fetching
│  │     ├─ Order execution
│  │     └─ Position management
│  │
│  └─ EAFileBridge (secondary)
│     └─ File-based IPC to SYNX_EA service
│        ├─ Chart control
│        ├─ MQL5 compilation
│        ├─ Backtesting
│        └─ Fallback for all operations
│
├─ Risk Management Layer
│  ├─ Pre-flight validation
│  ├─ Position sizing
│  ├─ Circuit breaker
│  └─ Drawdown tracking
│
├─ Security Layer
│  ├─ Credential vault (OS keyring)
│  ├─ Prompt injection shield
│  ├─ Audit logging
│  └─ Tool validation
│
└─ Intelligence Layer
   ├─ Market regime detection
   ├─ Correlation analysis
   ├─ Strategy context
   └─ Code generation
```

## Bridge Characteristics

### Primary Bridge: PythonCOMBridge

**Strengths:**
- Sub-100ms latency for data operations
- Direct COM interface to MT5
- No external dependencies
- Highest performance

**Supported Operations:**
- `symbol_info` — Symbol metadata
- `copy_rates_*` — OHLCV bars
- `copy_ticks_*` — Tick data
- `account_info` — Account details
- `positions_*` — Open positions
- `orders_*` — Pending orders
- `order_send/cancel/modify` — Order execution
- `position_close/modify` — Position management
- `market_book_*` — Market depth

**Requirements:**
- Windows OS
- MetaTrader 5 terminal running
- MetaTrader5 Python package installed

**Connection Time:** ~2 seconds

### Secondary Bridge: EAFileBridge

**Strengths:**
- File-based IPC (no API dependencies)
- Reliable command execution via SYNX_EA service
- Works across any terminal configuration
- Good fallback mechanism

**Supported Operations:**
- `chart_open/close` — Chart management
- `chart_set_symbol/timeframe` — Chart navigation
- `chart_attach_ea/remove_ea` — EA management
- `chart_indicator_add/list` — Indicator control
- `chart_apply_template/save_template` — Template management
- `mql5_compile/list_files/read_file/write_file` — MQL5 development
- `backtest_run/optimize/get_results` — Strategy testing
- Fallback for all python_com operations

**Requirements:**
- SYNX_EA.mq5 service in MT5 Services folder
- Write access to Common\Files directory
- SYNX_EA service running

**Connection Time:** ~0.5 seconds

## Routing Strategy

### Operation Routing Table

| Operation | Primary | Secondary | Fallback Enabled |
|-----------|---------|-----------|------------------|
| **Market Data** | | | |
| symbol_info | python_com | ea_file | Yes |
| symbol_info_tick | python_com | ea_file | Yes |
| copy_rates_from/range/pos | python_com | ea_file | Yes |
| copy_ticks_from/range | python_com | ea_file | Yes |
| market_book_get | python_com | ea_file | Yes |
| **Orders & Positions** | | | |
| order_send | python_com | ea_file | Yes |
| order_cancel | python_com | ea_file | Yes |
| order_modify | python_com | ea_file | Yes |
| orders_get | python_com | ea_file | Yes |
| position_close | python_com | ea_file | Yes |
| position_modify | python_com | ea_file | Yes |
| positions_get | python_com | ea_file | Yes |
| **Account** | | | |
| account_info | python_com | ea_file | Yes |
| **Chart Operations** | | | |
| chart_open/close | ea_file only | — | No |
| chart_set_symbol/timeframe | ea_file only | — | No |
| chart_attach_ea/remove_ea | ea_file only | — | No |
| chart_indicator_* | ea_file only | — | No |
| chart_apply_template/save_template | ea_file only | — | No |
| **MQL5 Development** | | | |
| mql5_compile | ea_file only | — | No |
| mql5_* (all) | ea_file only | — | No |
| **Backtesting** | | | |
| backtest_run/optimize/get_results | ea_file only | — | No |
| **Terminal Management** | | | |
| terminal_get_info/path | python_com | ea_file | Yes |

### Smart Routing Algorithm

```
When operation requested:

1. Check if operation is "ea_file_only" (chart/mql5/backtest)
   └─ Route to ea_file directly, no fallback to python_com

2. Otherwise (data/orders/positions)
   └─ Try python_com first (fastest)
   └─ If success → return result
   └─ If error and fallback enabled → try ea_file
   └─ If both fail → raise exception

3. Log routing decision for diagnostics
   └─ composite_bridge_primary_success
   └─ composite_bridge_primary_failed_fallback
   └─ composite_bridge_secondary_success (fallback)
   └─ composite_bridge_both_failed
```

## Connection Management

### Initialization

```
CompositeBridge.connect()
├─ Create PythonCOMBridge instance
├─ Create EAFileBridge instance
├─ Try connect to python_com (may fail, not fatal)
├─ Try connect to ea_file (may fail, not fatal)
├─ Log individual bridge states
└─ Return success if at least one bridge connected
```

### Connection State

```python
# Query overall connection
status = await bridge.is_connected()
# Returns True if at least one bridge connected

# Get detailed status
info = await bridge.account_info()
# Returns data from whichever bridge is connected
```

### Reconnection Strategy

Each bridge has independent reconnection logic:

**PythonCOMBridge:**
```yaml
python_com:
  reconnect_interval_seconds: 30   # Retry every 30 seconds
  max_retries: 5                   # Give up after 5 failures
  backoff_factor: 2.0              # Exponential backoff: 30s, 60s, 120s...
```

**EAFileBridge:**
```yaml
ea_file:
  timeout_seconds: 30              # Command timeout
  files_dir: null                  # Auto-detect
```

## Fallback Behavior

### Example: Data Operation Fallback

```
Operation: copy_rates_from(EURUSD, H1, 2026-04-20, 100)
│
├─ Step 1: Try PythonCOMBridge
│  └─ Send request to MT5 COM interface
│  └─ Timeout after 5 seconds
│  └─ Log: composite_bridge_primary_failed_fallback
│
├─ Step 2: Try EAFileBridge (fallback enabled)
│  └─ Drop command file in Common\Files
│  └─ Wait for SYNX_EA response
│  └─ Receive result (150ms)
│  └─ Log: composite_bridge_secondary_success
│
└─ Step 3: Return result to user
   └─ User gets data, doesn't know about fallback
```

### Example: Chart Operation (No Fallback)

```
Operation: chart_attach_ea(chart_id=1, ea_name="MyEA")
│
├─ Check if operation is "ea_file_only"
│  └─ Yes, chart operations only work via ea_file
│
├─ Step 1: Route directly to EAFileBridge
│  └─ Drop command file in Common\Files
│  └─ Wait for SYNX_EA response
│  └─ Timeout 30 seconds
│
├─ Step 2: If fails, no fallback available
│  └─ Log: composite_bridge_ea_file_failed
│  └─ Raise exception
│
└─ User gets error (chart operations not available without ea_file)
```

## Performance Characteristics

### Latency Comparison

| Operation | python_com | ea_file | Composite |
|-----------|-----------|---------|-----------|
| symbol_info | ~10ms | ~100ms | ~10ms |
| copy_rates (100 bars) | ~20ms | ~150ms | ~20ms |
| account_info | ~15ms | ~120ms | ~15ms |
| order_send | ~50ms | ~200ms | ~50ms |
| position_close | ~60ms | ~220ms | ~60ms |
| order_cancel | ~45ms | ~180ms | ~45ms |
| **Fallback cost** | — | — | +100ms (retry) |

### Throughput

- **python_com** — 100+ operations/second
- **ea_file** — 5-10 operations/second
- **composite** — 100+ ops/sec (python_com) + fallback for ea_file ops

### Connection Time

| Bridge | Time |
|--------|------|
| python_com | ~2.0s |
| ea_file | ~0.5s |
| composite | ~2.5s (both in parallel) |

## Graceful Degradation

### Scenario 1: Both Bridges Working (Ideal)

```yaml
Primary: connected=True
Secondary: connected=True
Effect: Full functionality, best performance
```

- Fast operations use python_com (~10-60ms)
- Chart/MQL5 operations use ea_file (~100-200ms)
- Automatic fallback if primary fails

### Scenario 2: Primary Down, Secondary Up

```yaml
Primary: connected=False
Secondary: connected=True
Effect: All operations via ea_file (slower)
```

- All operations route to ea_file
- ~5-10x slower, but fully functional
- Logs show: `composite_bridge_primary_disconnected`
- User can continue trading, chart operations still work

### Scenario 3: Primary Up, Secondary Down

```yaml
Primary: connected=True
Secondary: connected=False
Effect: Data operations work, chart operations fail
```

- Data/order operations work at full speed
- Chart/MQL5/backtest operations fail
- User must reconnect SYNX_EA or restart terminal
- Logs show: `composite_bridge_secondary_disconnected`

### Scenario 4: Both Bridges Down

```yaml
Primary: connected=False
Secondary: connected=False
Effect: Complete failure
```

- Server starts but all operations fail
- Logs show: `composite_bridge_both_disconnected`
- User must diagnose and fix both bridges

## Configuration

### Enable Composite Mode

```yaml
bridge:
  mode: "composite"
```

### Bridge-Specific Settings

```yaml
bridge:
  python_com:
    terminal_path: null              # Auto-detect
    reconnect_interval_seconds: 30
    max_retries: 5
    backoff_factor: 2.0

  ea_file:
    timeout_seconds: 30
    files_dir: null                  # Auto-detect
  
  # Shared settings
  filling_mode: "return"
  slippage_points: 20
```

See [Configuration Reference](CONFIG.md) for all options.

## Monitoring & Debugging

### Bridge Health

Check individual bridge status via account_info:

```python
info = await bridge.account_info()
# If from python_com, connection was successful
# If from ea_file, primary failed but secondary worked
```

### Audit Logs

All routing decisions logged:

```json
{
  "timestamp": "2026-04-20T10:30:15Z",
  "event": "composite_bridge_primary_failed_fallback",
  "op": "symbol_info",
  "symbol": "EURUSD",
  "error": "Connection timeout",
  "fallback_used": true
}
```

### Debug Logging

Enable DEBUG level for detailed routing:

```yaml
server:
  log_level: "DEBUG"
  log_format: "json"
```

Output:
```
composite_bridge_routing op=order_send, trying=primary
composite_bridge_primary_attempt op=order_send, symbol=EURUSD
composite_bridge_primary_failed_fallback op=order_send, error="timeout"
composite_bridge_secondary_attempt op=order_send, symbol=EURUSD
composite_bridge_secondary_success op=order_send, result={ticket: 12345}
```

## Testing Composite Mode

### Unit Tests

```bash
pytest tests/bridge/ -v
```

### Integration Tests

```bash
pytest tests/integration/test_composite_bridge.py -v
```

### Test Fallback

Simulate primary bridge failure:

```python
# In tests
bridge._primary.disconnect()

# All operations should still work via secondary
result = await bridge.account_info()
assert result is not None
```

## Migration Guide

### From `python_com` to `composite`

Drop-in replacement, no code changes:

```yaml
# Before
bridge:
  mode: python_com

# After (same code, better reliability)
bridge:
  mode: composite
```

### From `ea_file` to `composite`

Gain performance benefits with fallback:

```yaml
# Before
bridge:
  mode: ea_file

# After (same functionality, faster)
bridge:
  mode: composite
```

## Troubleshooting

### Primary Bridge Constantly Failing

Check Python COM connection:
```bash
python -m synx_mt5 test-connection
```

### Secondary Bridge Not Responding

Check SYNX_EA service:
1. Verify file in Services folder
2. Compile in MetaEditor (should have 0 errors)
3. Check MT5 journal for errors
4. Verify Common\Files permissions

### Fallback Happening Too Often

Review logs:
```bash
grep "primary_failed_fallback" ~/.synx-mt5/logs/server.log
```

Possible causes:
- MT5 connection unstable
- Network timeouts
- EA_FILE service too slow (increase timeout)

### Asymmetric Performance

If one bridge much slower than other, consider:
- **Slower python_com** — Check MT5 load, process hang
- **Slower ea_file** — Check SYNX_EA service, file I/O delays

## Best Practices

1. **Always use composite mode** in production
2. **Monitor both bridges** via logs
3. **Test fallback paths** regularly
4. **Set appropriate timeouts** based on your hardware
5. **Log all routing decisions** for troubleshooting

## Future Enhancements

- [ ] Proactive bridge health checks
- [ ] Load balancing between bridges
- [ ] Bridge connection pooling
- [ ] Automatic bridge selection based on load
- [ ] Performance metrics/telemetry

## See Also

- [Setup Guide](SETUP.md) — Bridge setup instructions
- [Configuration Reference](CONFIG.md) — Bridge configuration options
- [Troubleshooting Guide](TROUBLESHOOTING.md) — Common issues and fixes
