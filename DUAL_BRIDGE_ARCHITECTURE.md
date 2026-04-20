# Dual-Bridge Composite Architecture

## Overview

The **Composite Bridge** enables both `python_com` and `ea_file` bridges to work together seamlessly, providing:

- **Reliability**: Fallback when one bridge fails
- **Performance**: Optimal routing of operations to the fastest bridge
- **Flexibility**: Access to all features from both bridges
- **Graceful Degradation**: Server continues operating if one bridge fails

## Architecture

```
CompositeBridge
├─ Primary: PythonCOMBridge (fast, direct MT5 API)
│  └ Operations: symbol_info, copy_rates, copy_ticks, positions, orders
└─ Secondary: EAFileBridge (reliable file-based IPC via SYNX_EA)
   └ Operations: chart_*, mql5_*, backtest_*, fallback for primary failures
```

## Bridge Characteristics

### Primary Bridge: PythonCOMBridge
- **Advantage**: Direct COM/IPC to MT5, fastest execution
- **Operations**: All market data, orders, positions, account info
- **Requirement**: Windows + MetaTrader5 Python package
- **Fallback**: Automatically tries EA bridge if fails

### Secondary Bridge: EAFileBridge
- **Advantage**: Reliable file-based IPC, no additional packages needed
- **Operations**: Chart control, MQL5 compilation, backtest integration
- **Requirement**: SYNX_EA service running in MT5
- **Fallback**: Available if primary bridge unavailable

## Routing Strategy

### Smart Routing Table

| Operation | Primary | Secondary | Fallback |
|-----------|---------|-----------|----------|
| `symbol_info` | python_com | ea_file | Yes |
| `copy_rates_*` | python_com | ea_file | Yes |
| `copy_ticks_*` | python_com | ea_file | Yes |
| `account_info` | python_com | ea_file | Yes |
| `positions_*` | python_com | ea_file | Yes |
| `orders_*` | python_com | ea_file | Yes |
| `order_send` | python_com | ea_file | Yes |
| `order_cancel` | python_com | ea_file | Yes |
| `position_close` | python_com | ea_file | Yes |
| `position_modify` | python_com | ea_file | Yes |
| `market_book_*` | python_com | ea_file | Yes |
| `chart_*` | ea_file only | - | No |
| `mql5_*` | ea_file only | - | No |
| `backtest_*` | ea_file only | - | No |

## Enabling Composite Mode

### Step 1: Update Configuration

Edit `~/.synx-mt5/synx.yaml`:

```yaml
bridge:
  mode: composite          # Set to "composite" instead of "python_com" or "ea_file"
  terminal_path: null
  ea_host: "localhost"
  ea_port: 9000
  ea_timeout_seconds: 30
  ea_files_dir: null
```

### Step 2: Verify Both Services

**Primary Bridge (Python COM):**
```bash
synx-mt5 test-connection
# Should output: MT5 connection successful
```

**Secondary Bridge (SYNX_EA):**
```bash
# Verify SYNX_EA.mq5 is running in MT5 Services
# Check: C:\Users\<User>\AppData\Roaming\MetaQuotes\Terminal\<TerminalID>\MQL5\Services\SYNX_EA.mq5
```

### Step 3: Start Server with Composite Mode

```bash
synx-mt5 start
# or with explicit config
synx-mt5 start --config ~/.synx-mt5/synx.yaml
```

Monitor logs for:
```
composite_bridge_primary_status connected=True
composite_bridge_secondary_status connected=True
composite_bridge_connected overall=True primary=True secondary=True
```

## Fallback Behavior

When an operation fails with the primary bridge:

```
Operation: order_send(EURUSD, BUY, 0.1)
├─ Try Primary (python_com) → Connection lost
├─ Log: "composite_bridge_primary_failed_fallback"
└─ Try Secondary (ea_file) → Success ✓
```

If both bridges fail:
```
Operation: copy_rates_from(EURUSD, H1, ...)
├─ Try Primary (python_com) → Error
├─ Try Secondary (ea_file) → Error
└─ Log: "composite_bridge_both_failed" → Raise exception
```

## Connection State Management

The composite bridge tracks individual bridge states:

```python
# Query connection status
status = await bridge.is_connected()  # True if at least one bridge connected

# Get detailed status via account_info
info = await bridge.account_info()
# Result from whichever bridge connected first
```

## Performance Characteristics

### Latency

| Operation | python_com | ea_file | Composite |
|-----------|-----------|---------|-----------|
| symbol_info | ~10ms | ~100ms | ~10ms (primary used) |
| copy_rates | ~20ms | ~150ms | ~20ms (primary used) |
| order_send | ~50ms | ~200ms | ~50ms (primary used) |
| Fallback cost | - | - | +100ms (retry) |

### Connection Time

| Mode | Time |
|------|------|
| python_com | ~2s |
| ea_file | ~0.5s |
| **composite** | **~2.5s** (both in parallel if possible) |

## Migration Path

### From `python_com` → `composite`

No breaking changes. All operations remain compatible:

```yaml
# Before
bridge:
  mode: python_com

# After (drop-in replacement)
bridge:
  mode: composite
```

### From `ea_file` → `composite`

Gain performance benefits with fallback reliability:

```yaml
# Before
bridge:
  mode: ea_file

# After (drop-in replacement)
bridge:
  mode: composite
```

## Monitoring & Debugging

### Health Checks

Query individual bridge status (internal):
```python
composite._primary_connected  # True if python_com is up
composite._secondary_connected  # True if ea_file is up
```

### Audit Logs

All routing decisions are logged:
```
composite_bridge_primary_success op=symbol_info
composite_bridge_primary_failed_fallback op=order_send error="Connection lost"
composite_bridge_secondary_success op=order_send (fallback)
composite_bridge_both_failed op=order_cancel
```

### Graceful Degradation

**Both bridges down:**
- Server still starts
- Calls fail with clear error message
- Log shows which bridge(s) unavailable

**Primary down, secondary up:**
- All operations route to ea_file
- Slight latency increase
- Full functionality maintained

**Primary up, secondary down:**
- Chart/mql5/backtest operations fail
- All other operations work at full speed
- Partial degradation only

## Testing

Run comprehensive test suite with composite mode:

```bash
pytest tests/ -k composite -v
```

Test individual bridges within composite:
```python
# tests/integration/test_composite_bridge.py
async def test_fallback_on_primary_failure():
    bridge = CompositeBridge(config)
    await bridge.connect()
    
    # Disconnect primary to force fallback
    await bridge._primary.disconnect()
    
    # Should still work via secondary
    result = await bridge.account_info()
    assert result is not None
```

## Configuration Reference

```yaml
bridge:
  mode: composite                    # Mode: "python_com", "ea_file", "composite"
  terminal_path: null               # Override MT5 terminal path (python_com)
  ea_host: "localhost"              # SYNX_EA service host (ea_file)
  ea_port: 9000                     # SYNX_EA service port (ea_file)
  ea_timeout_seconds: 30            # Command timeout (ea_file)
  ea_files_dir: null                # Command files directory (ea_file)
```

## Troubleshooting

### Both bridges show "connected=False"

**Primary (python_com):**
- Verify MT5 terminal is running
- Check credentials with `synx-mt5 test-connection`
- Review logs for MT5 initialization errors

**Secondary (ea_file):**
- Verify SYNX_EA service is running in MT5
- Check file permissions on `Common\Files` directory
- Verify `%APPDATA%\MetaQuotes\Terminal\Common\Files` exists

### Fallback happening too often

Check logs for error patterns:
```
composite_bridge_primary_failed_fallback op=order_send error="...specific error..."
```

Debug with:
1. Test primary bridge directly: `synx-mt5 test-connection`
2. Check secondary bridge file access
3. Increase `ea_timeout_seconds` if ea_file is slow

### Chart/MQL5 operations fail

These require ea_file bridge. Verify:
1. SYNX_EA service is running
2. ea_files_dir is accessible
3. chart_* operations aren't being called on primary-only setup

## Best Practices

1. **Always use composite mode** in production for maximum reliability
2. **Monitor both bridges** - check connection status periodically
3. **Handle fallback costs** - be aware of ~100ms latency when falling back
4. **Test both paths** - ensure EA commands work, not just python_com
5. **Log routing decisions** - helpful for debugging performance issues

## Future Enhancements

- [ ] Proactive bridge health checks
- [ ] Load balancing between bridges
- [ ] Bridge connection pooling for higher concurrency
- [ ] Automatic bridge selection based on operation type
- [ ] Metrics/telemetry for bridge performance
