# SYNX-MT5-MCP Troubleshooting Guide

Comprehensive solutions for common issues and error conditions.

## Connection Issues

### Bridge Connection Failed

**Error:** `Failed to connect to MT5 terminal` or `Bridge connection failed`

**Root Causes:**
- MT5 terminal not running
- Python package not installed
- Terminal path misconfigured
- Port conflicts

**Solutions:**

1. **Verify MT5 is Running**
   ```bash
   # Windows
   tasklist | findstr terminal64.exe
   ```
   If not found, launch MetaTrader 5 manually.

2. **Check Python Package**
   ```bash
   pip show MetaTrader5
   ```
   If not installed:
   ```bash
   pip install MetaTrader5
   ```

3. **Verify Terminal Path**
   ```bash
   # In Python
   from MetaTrader5 import terminal_info
   info = terminal_info()
   print(info.path)
   ```
   
   Update config if needed:
   ```yaml
   bridge:
     python_com:
       terminal_path: "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
   ```

4. **Test Connection**
   ```bash
   python -m synx_mt5 test-connection
   ```

### SYNX_EA Service Not Responding

**Error:** `EA File bridge connection failed` or `SYNX_EA timeout`

**Root Causes:**
- SYNX_EA.mq5 not in Services folder
- SYNX_EA not compiled
- Common\Files not accessible
- Timeout too short

**Solutions:**

1. **Verify SYNX_EA Installation**
   
   Check if file exists:
   ```
   C:\Users\<User>\AppData\Roaming\MetaQuotes\Terminal\<TerminalID>\MQL5\Services\SYNX_EA.mq5
   ```
   
   If not, copy it there.

2. **Compile SYNX_EA**
   
   In MT5:
   - Open Services folder
   - Right-click SYNX_EA.mq5
   - Select "Compile"
   - Should show "0 errors"
   
   If errors, see [MQL5 Compilation Errors](#mql5-compilation-errors).

3. **Check Common\Files Permissions**
   
   ```bash
   # Verify directory exists and is writable
   dir "%APPDATA%\MetaQuotes\Terminal\Common\Files"
   ```
   
   If missing, MT5 will create it on next restart.

4. **Increase Timeout**
   
   If running on slow hardware:
   ```yaml
   bridge:
     ea_file:
       timeout_seconds: 60  # Increase from default 30
   ```

5. **Monitor SYNX_EA Service**
   
   In MT5:
   - View → Toolbars → Services
   - Look for SYNX_EA in service list
   - Check MT5 Journal for startup messages

### Bridge Mode Not Switching

**Error:** Changed config but bridge still uses old mode

**Root Causes:**
- MCP server didn't reload config
- Python cache (.pyc files)
- Server still running in background

**Solutions:**

1. **Clear Python Cache**
   ```bash
   # Clear all __pycache__ directories
   find . -type d -name __pycache__ -exec rm -rf {} +
   
   # Clear pip cache
   pip cache purge
   ```

2. **Restart MCP Server**
   ```bash
   # Stop server
   Ctrl+C
   
   # Wait 5 seconds for clean shutdown
   sleep 5
   
   # Start again with new config
   python -m synx_mt5.server
   ```

3. **Verify Config Loaded**
   
   Check logs for:
   ```
   [INFO] Loading configuration from ~/.synx-mt5/synx.yaml
   [INFO] Bridge mode: composite
   ```

## HITL (Human-in-the-Loop) Issues

### Orders Stuck in HITL Approval

**Error:** Trade pending indefinitely with "HITL timeout"

**Root Causes:**
- HITL approval not provided in time
- HITL disabled but tool still requires approval
- User didn't see approval prompt

**Solutions:**

1. **Provide Approval**
   
   When HITL enabled, Claude will prompt:
   ```
   [HITL] Approval required for order_send
   [HITL] Symbol: EURUSD, Volume: 0.1, Type: BUY_MARKET
   [HITL] Risk: 1.0% of equity
   [HITL] Approve? (yes/no)
   ```
   
   Type `yes` to approve, order executes immediately.

2. **Disable HITL for Testing**
   
   If HITL blocking automated testing:
   ```yaml
   hitl:
     enabled: false
     tools: []
   ```
   
   Orders execute immediately without approval.

3. **Increase HITL Timeout**
   
   If timeout too short for approval:
   ```yaml
   hitl:
     timeout_seconds: 600  # Increase from default 300 (5 minutes)
   ```

4. **Check HITL Configuration**
   
   Ensure tools requiring approval are listed:
   ```yaml
   hitl:
     enabled: true
     tools:
       - order_send       # Requires approval
       - position_close   # Requires approval
   ```
   
   Other tools don't require approval:
   - symbol_info (read-only)
   - copy_rates (read-only)
   - account_info (read-only)

### HITL Via Webhook Not Working

**Error:** Webhook endpoint not receiving requests or not responding

**Solutions:**

1. **Verify Webhook Configuration**
   ```yaml
   hitl:
     enabled: true
     sink: webhook
     webhook_url: https://your-service.com/approve
     webhook_secret: your-shared-secret
   ```

2. **Check Endpoint Availability**
   ```bash
   curl -X POST https://your-service.com/approve \
     -H "Content-Type: application/json" \
     -d '{"test": true}'
   ```

3. **Monitor Webhook Requests**
   
   Webhook payload format:
   ```json
   {
     "timestamp": "2026-04-20T10:30:15Z",
     "tool": "order_send",
     "params": {
       "symbol": "EURUSD",
       "volume": 0.1,
       "order_type": "BUY_MARKET"
     }
   }
   ```
   
   Required response:
   ```json
   {
     "approved": true,
     "reason": "Approved by user"
   }
   ```

4. **Verify HMAC Signature**
   
   Webhook includes `X-SYNX-Signature` header:
   ```
   HMAC-SHA256(payload, secret)
   ```
   
   Verify signature in your endpoint:
   ```python
   import hmac
   import hashlib
   
   signature = request.headers.get('X-SYNX-Signature')
   computed = hmac.new(
     secret.encode(),
     payload.encode(),
     hashlib.sha256
   ).hexdigest()
   
   if not hmac.compare_digest(signature, computed):
     return {"error": "Invalid signature"}, 401
   ```

### HITL Not Prompting

**Error:** No approval prompt shown, orders execute without asking

**Root Causes:**
- HITL disabled in config
- Tool not in approval list
- HITL sink misconfigured

**Solutions:**

1. **Verify HITL Enabled**
   ```yaml
   hitl:
     enabled: true  # Must be true
   ```

2. **Check Tool in List**
   ```yaml
   hitl:
     tools:
       - order_send       # Add tools requiring approval
       - position_close
   ```

3. **Check Sink Configuration**
   ```yaml
   hitl:
     sink: terminal    # terminal or webhook
   ```
   
   For terminal sink, prompts appear in Claude's console.

## Circuit Breaker Issues

### Circuit Breaker Triggered Unexpectedly

**Error:** `Circuit breaker in OPEN state, orders rejected`

**Root Causes:**
- Drawdown limits too tight
- Market lost more than expected
- Circuit breaker incorrectly triggered

**Solutions:**

1. **Check Drawdown Status**
   ```bash
   python -m synx_mt5 check-drawdown
   ```
   
   Output shows:
   - Current equity
   - Starting equity
   - Current drawdown %
   - Circuit breaker threshold

2. **Increase Drawdown Limits**
   
   Current config:
   ```yaml
   risk:
     circuit_breaker:
       max_session_drawdown_pct: 5.0
       max_daily_drawdown_pct: 10.0
   ```
   
   Adjust for your risk tolerance:
   ```yaml
   risk:
     circuit_breaker:
       max_session_drawdown_pct: 10.0  # Allow 10% drawdown
       max_daily_drawdown_pct: 20.0    # Hard stop at 20%
   ```

3. **Reset Circuit Breaker State**
   
   If incorrectly triggered:
   ```bash
   rm ~/.synx-mt5/circuit_breaker.state
   ```
   
   Then restart MCP server.

4. **Extend Cooldown**
   
   After trigger, trading paused for cooldown period:
   ```yaml
   risk:
     circuit_breaker:
       cooldown_seconds: 60  # Pause 60 seconds before retrying
   ```

### Circuit Breaker Never Triggers

**Error:** Portfolio in severe drawdown but circuit breaker still allows trades

**Root Causes:**
- Circuit breaker disabled
- Thresholds set too high
- Drawdown not being tracked correctly

**Solutions:**

1. **Verify Circuit Breaker Enabled**
   ```yaml
   risk:
     circuit_breaker:
       max_session_drawdown_pct: 5.0  # Must be set
   ```

2. **Check Thresholds**
   
   If drawdown 8% but max_session_drawdown_pct is 10.0, won't trigger.
   ```yaml
   risk:
     circuit_breaker:
       max_session_drawdown_pct: 5.0  # Lower to catch sooner
   ```

3. **Enable Debug Logging**
   ```yaml
   server:
     log_level: DEBUG
   ```
   
   Look for:
   ```
   [DEBUG] Circuit breaker check: drawdown=8.5%, threshold=5.0%
   [DEBUG] Circuit breaker TRIGGERED
   ```

4. **Monitor Starting Equity**
   
   Circuit breaker calculates from starting equity.
   Verify:
   ```bash
   python -c "from synx_mt5.risk import CircuitBreaker; cb = CircuitBreaker({}); print(cb.starting_equity)"
   ```

### Cooldown Too Long

**Error:** Trading paused too long after circuit breaker trigger

**Solution:**

Reduce cooldown duration:
```yaml
risk:
  circuit_breaker:
    cooldown_seconds: 30  # Resume after 30 seconds instead of 60
```

## Risk Management Issues

### Orders Rejected - "Risk Too High"

**Error:** `Pre-flight validation failed: Risk exceeds maximum`

**Root Causes:**
- Position size too large
- Risk per trade configured too low
- Total exposure already near limit

**Solutions:**

1. **Check Risk Configuration**
   ```yaml
   risk:
     max_risk_per_trade_pct: 1.0      # Max risk per trade
     max_total_exposure_pct: 10.0     # Max total exposure
   ```

2. **Calculate Actual Risk**
   
   Risk = (Entry - SL) × Volume × Point Value
   
   For EURUSD 0.1 lot with 50 pip SL:
   - Risk = 50 pips × 0.1 lot = 5 pips of equity
   - As % of $10,000 = 0.05%

3. **Reduce Position Size**
   
   If volume too large:
   ```
   max_volume = (max_risk_per_trade_pct × equity) / (entry_price - sl_price) / point_value
   ```

4. **Increase Risk Limits**
   
   For aggressive testing:
   ```yaml
   risk:
     max_risk_per_trade_pct: 5.0       # 5% per trade
     max_total_exposure_pct: 30.0      # 30% total
   ```

### Stop Loss Validation Failing

**Error:** `SL distance below minimum` or `SL too close to entry`

**Root Causes:**
- SL distance too small
- min_sl_pips configured too high
- Using wrong decimal places

**Solutions:**

1. **Check SL Configuration**
   ```yaml
   risk:
     min_sl_pips: 10  # Minimum SL distance in pips
   ```

2. **Calculate SL Distance**
   
   For EURUSD (4 decimal places):
   - Entry: 1.0850
   - SL: 1.0840
   - Distance = 1.0850 - 1.0840 = 0.0010 = 10 pips ✓
   
   If SL 1.0845:
   - Distance = 1.0850 - 1.0845 = 0.0005 = 5 pips ✗ (below 10 pip minimum)

3. **Reduce Minimum SL**
   
   For scalping (smaller SLs):
   ```yaml
   risk:
     min_sl_pips: 2  # Reduce for scalping
   ```

4. **Fix Decimal Places**
   
   Ensure SL prices have correct decimal places:
   - EURUSD: 4 decimals (1.0850)
   - Crypto: 2-8 decimals (50250.25)
   - Metals: 2 decimals (2050.50)

### Risk:Reward Ratio Warning

**Warning:** `R:R ratio below recommended`

**Causes:**
- Profit target too close to entry
- Stop loss too far from entry

**Solutions:**

1. **Check R:R Configuration**
   ```yaml
   risk:
     min_rr_ratio: 1.0  # Minimum 1:1 risk:reward
   ```

2. **Improve TP Placement**
   
   R:R = (TP - Entry) / (Entry - SL)
   
   For Entry 1.0850, SL 1.0840, TP needed:
   ```
   R:R = (TP - 1.0850) / (1.0850 - 1.0840)
   1.0 = (TP - 1.0850) / 0.0010
   TP = 1.0850 + 0.0010 = 1.0860
   ```

3. **Reduce R:R Requirement**
   
   For aggressive testing:
   ```yaml
   risk:
     min_rr_ratio: 0.5  # Allow 1:0.5 (more losses acceptable)
   ```

## MQL5 Compilation Errors

### SYNX_EA Compilation Fails

**Error:** `Compilation error in SYNX_EA.mq5` with many error messages

**Common Errors:**

1. **Undeclared Identifier**
   ```
   'undeclared identifier 'CHART_CURRENT'
   ```
   Fix: Use correct constant
   ```mql5
   // Wrong
   ChartWindowFind(0, CHART_CURRENT, ...)
   
   // Correct
   ChartWindowFind(0, CHART_CURRENT_POS, ...)
   ```

2. **Reserved Keyword**
   ```
   'template' unexpected token
   ```
   Fix: Rename variable (template is reserved)
   ```mql5
   // Wrong
   string template = "MyTemplate";
   
   // Correct
   string tpl_name = "MyTemplate";
   ```

3. **Type Mismatch**
   ```
   'implicit conversion from 'int' to 'bool'
   ```
   Fix: Add explicit cast
   ```mql5
   // Wrong
   if (value) { }
   
   // Correct
   if ((bool)value) { }
   ```

**Solutions:**

1. **Check MetaEditor Version**
   
   Update to latest MT5 to get compiler fixes.

2. **Verify MQL5 Syntax**
   
   In MetaEditor:
   - Ctrl+Shift+F7 (compile)
   - Review error list
   - Fix line by line

3. **Use Syntax Checker**
   ```bash
   python -m synx_mt5.tools.mql5_dev check-syntax SYNX_EA.mq5
   ```

4. **Retrieve Compilation Errors**
   
   Use SYNX tool:
   ```bash
   python -m synx_mt5 get-mql5-errors SYNX_EA.mq5
   ```

### Custom EA Won't Compile

**Error:** Compilation fails for user-created EA

**Solutions:**

1. **Check Includes**
   
   Ensure all #include files exist:
   ```mql5
   #include <Trade\Trade.mqh>  // Must exist in Include folder
   ```

2. **Verify Input Types**
   
   Use correct MT5 types:
   ```mql5
   // Correct
   input double InpRiskPercent = 1.0;
   input int InpRSIPeriod = 14;
   input string InpComment = "MyEA";
   ```

3. **Check Library Dependencies**
   
   If using external libraries, ensure they're installed.

4. **Enable Compiler Logging**
   ```bash
   python -m synx_mt5 compile-ea my_ea.mq5 --debug
   ```

## Backtesting Issues

### Backtest Hangs or Freezes

**Error:** Backtest starts but never completes

**Root Causes:**
- Too large date range
- Too many bars to process
- SYNX_EA service hung

**Solutions:**

1. **Reduce Date Range**
   
   Instead of 5 years, test 1 month first:
   ```bash
   python -m synx_mt5 backtest --symbol EURUSD --from 2026-04-01 --to 2026-04-20
   ```

2. **Check SYNX_EA Service**
   
   If service hung, restart it:
   ```bash
   # In MT5, stop SYNX_EA and restart
   ```

3. **Increase Timeout**
   ```yaml
   bridge:
     ea_file:
       timeout_seconds: 120  # Backtest may take time
   ```

4. **Monitor Progress**
   
   Check MT5 Strategy Tester window for progress.

### Backtest Results Not Saved

**Error:** Backtest completes but no results file

**Root Causes:**
- Results directory not accessible
- File permissions issue
- Results directory misconfigured

**Solutions:**

1. **Check Results Directory**
   ```bash
   python -m synx_mt5 get-results-dir
   ```
   
   Should output:
   ```
   C:\Users\<User>\AppData\Roaming\MetaQuotes\Terminal\<ID>\MQL5\Files\...
   ```

2. **Verify Directory Exists**
   ```bash
   ls "C:\Users\<User>\AppData\Roaming\MetaQuotes\Terminal\*\MQL5\Files"
   ```

3. **Check File Permissions**
   
   Ensure write access to results directory.

## Performance Issues

### Operations Very Slow

**Error:** Data queries taking >1 second, operations slow

**Root Causes:**
- Primary bridge unavailable, using fallback
- EA_FILE service slow
- Network issues

**Solutions:**

1. **Check Bridge Status**
   ```bash
   python -m synx_mt5 check-bridge-status
   ```
   
   Should show both bridges connected.

2. **Monitor Fallback Usage**
   
   In logs, look for:
   ```
   composite_bridge_primary_failed_fallback
   ```
   
   If frequent, primary bridge has issues.

3. **Profile Slow Operations**
   ```bash
   python -m synx_mt5 profile-operation --tool copy_rates
   ```

4. **Increase Timeout**
   
   If hardware slow:
   ```yaml
   bridge:
     ea_file:
       timeout_seconds: 60  # Increase from 30
   ```

## Log Analysis

### Enable Debug Logging

```yaml
server:
  log_level: DEBUG
  log_format: json  # Easier to parse
```

Logs saved to `~/.synx-mt5/logs/`

### Parse JSON Logs

```bash
# Find all order_send operations
grep "tool.*order_send" ~/.synx-mt5/logs/*.log | jq '.tool, .result'

# Find all errors
grep "ERROR" ~/.synx-mt5/logs/*.log | jq '.message'

# Timeline of events
cat ~/.synx-mt5/logs/*.log | jq '.timestamp, .event' | head -20
```

### Common Log Patterns

**Successful operation:**
```
[INFO] composite_bridge_primary_success op=symbol_info result={...}
```

**Fallback occurred:**
```
[INFO] composite_bridge_primary_failed_fallback op=order_send error="timeout"
[INFO] composite_bridge_secondary_success op=order_send result={ticket: 123}
```

**Risk validation failed:**
```
[WARNING] pre_flight_validation_failed reason="SL distance below minimum"
```

**Circuit breaker triggered:**
```
[WARNING] circuit_breaker_triggered drawdown=5.1% threshold=5.0%
```

## Getting Help

If issues persist:

1. **Check [Configuration Reference](CONFIG.md)** — Verify all settings correct
2. **Review [Architecture Documentation](ARCHITECTURE.md)** — Understand bridge operation
3. **Check System Logs** — `~/.synx-mt5/logs/`
4. **Test Components Individually** — Bridge, EA service, Python package
5. **Check [Contributing Guide](CONTRIBUTING.md)** — Report issues

## See Also

- [SETUP.md](SETUP.md) — Installation and setup
- [CONFIG.md](CONFIG.md) — Configuration reference
- [RISK.md](RISK.md) — Risk management configuration
- [ARCHITECTURE.md](ARCHITECTURE.md) — Dual-bridge architecture details
