# SYNX-MT5-MCP Setup Guide

## Prerequisites

- **Python 3.11+** — Download from [python.org](https://www.python.org/downloads/)
- **MetaTrader 5** — Windows terminal (not Mac/Linux native)
- **Git** — For cloning and version control
- **MCP-compatible agent** — Claude Code, Claude Desktop, Gemini CLI, OpenCode Desktop, or OpenCode CLI

## Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/ghost-p-l/synx_mt5_mcp.git
cd synx_mt5_mcp
```

### Step 2: Install Dependencies

```bash
# Install in development mode with all dependencies
pip install -e .
```

This installs:
- `MetaTrader5` Python package
- `structlog` for structured logging
- `pyyaml` for configuration
- `pydantic` for validation

### Step 3: Create Configuration Directory

```bash
# Create config directory
mkdir -p ~/.synx-mt5

# Copy example configuration
cp ~/.synx-mt5/synx.yaml.example ~/.synx-mt5/synx.yaml
```

### Step 4: Configure SYNX-MT5

Edit `~/.synx-mt5/synx.yaml`:

```yaml
# Start with defaults from config/risk/standard.yaml for production
# Or use config/risk/testing.yaml for demo account testing
# Or use config/risk/aggressive.yaml for aggressive strategy testing
```

See [Configuration Reference](CONFIG.md) for detailed options.

### Step 5: Set Up Credentials

#### Option A: OS Keyring (Recommended - Never in env vars)

Credentials are stored securely in the OS keyring vault:

```bash
# Store MT5 account credentials
python -m synx_mt5.security.vault set-credential mt5_login <your-login>
python -m synx_mt5.security.vault set-credential mt5_password <your-password>
python -m synx_mt5.security.vault set-credential mt5_server <broker-server>
```

#### Option B: Environment Variables (Development Only)

```bash
export MT5_LOGIN=<your-login>
export MT5_PASSWORD=<your-password>
export MT5_SERVER=<broker-server>
```

**WARNING:** Never store credentials in config files or version control.

### Step 6: Verify Installation

```bash
# Test MT5 connection
python -c "from synx_mt5.bridge import create_bridge; import asyncio; asyncio.run(create_bridge('python_com', {}).test_connection())"
```

Expected output: `MT5 connection successful`

### Step 7: Configure Claude Code Integration

#### For Claude Desktop

Add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "synx_mt5": {
      "command": "python",
      "args": ["-m", "synx_mt5.server"],
      "env": {
        "SYNX_CONFIG": "~/.synx-mt5/synx.yaml"
      }
    }
  }
}
```

#### For Claude Code CLI

The MCP server will be auto-discovered if installed in development mode.

#### For Gemini CLI

Configure similar to Claude Desktop with your Gemini CLI config file.

#### For OpenCode Desktop

Add to your OpenCode configuration file (check OpenCode docs for config location):

```json
{
  "mcpServers": {
    "synx_mt5": {
      "command": "python",
      "args": ["-m", "synx_mt5.server"],
      "env": {
        "SYNX_CONFIG": "~/.synx-mt5/synx.yaml"
      }
    }
  }
}
```

#### For OpenCode CLI

Configure similar to Gemini CLI with your OpenCode CLI config file.

### Step 8: Start Server

```bash
# Start MCP server
python -m synx_mt5.server

# Or with explicit config
SYNX_CONFIG=~/.synx-mt5/synx.yaml python -m synx_mt5.server
```

Monitor logs:
```
[INFO] SYNX-MT5-MCP v1.1.0 starting...
[INFO] Bridge mode: composite
[INFO] Profile: executor
[INFO] Tools registered: 68
[INFO] Ready for connections
```

## Bridge Setup

### Python COM Bridge (Primary)

Used for fast data operations (symbol info, rates, ticks, orders, positions).

**Requirements:**
- MetaTrader5 Python package installed
- MT5 terminal running on Windows
- Terminal path auto-detected or specified in config

**Configuration:**

```yaml
bridge:
  mode: composite
  python_com:
    terminal_path: null          # Auto-detect
    reconnect_interval_seconds: 30
    max_retries: 5
    backoff_factor: 2.0
```

### EA File Bridge (Secondary)

Used for chart operations, MQL5 compilation, backtesting via SYNX_EA service.

**Requirements:**
- SYNX_EA.mq5 service running in MT5 (installed in Services folder)
- Write access to `Common\Files` directory

**Setup SYNX_EA Service:**

1. Place `SYNX_EA.mq5` in:
   ```
   C:\Users\<User>\AppData\Roaming\MetaQuotes\Terminal\<TerminalID>\MQL5\Services\
   ```

2. In MT5, right-click the Services folder and compile SYNX_EA.mq5
   - Should compile with 0 errors
   - Service will auto-start

3. Verify service is running:
   - Check Services folder shows SYNX_EA in alphabetical list
   - Monitor logs for "Service initialized"

**Configuration:**

```yaml
bridge:
  mode: composite
  ea_file:
    timeout_seconds: 30          # Command timeout
    files_dir: null              # Auto-detect Common\Files
```

### Composite Bridge (Recommended)

Uses both bridges with intelligent routing and fallback.

**Configuration:**

```yaml
bridge:
  mode: composite
```

**Routing:**
- Fast operations → python_com (symbol_info, copy_rates, orders, positions)
- Chart/MQL5 operations → ea_file (chart_*, mql5_*, backtest_*)
- Fallback → tries secondary bridge if primary fails

See [Architecture Guide](ARCHITECTURE.md) for detailed routing strategy.

## Capability Profiles

Choose the appropriate profile based on your use case:

### read_only
Market data analysis only. No order execution.
```yaml
profile: read_only
```

### analyst
Data analysis + intelligence. No order execution.
```yaml
profile: analyst
```

### executor
Order execution + chart control. Recommended for live trading.
```yaml
profile: executor
```

### full
All operations including destructive ones. Use for admin/testing.
```yaml
profile: full
```

## Risk Management Setup

### Standard Profile (Production)

```yaml
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
```

### Testing Profile (Demo Accounts)

```yaml
risk:
  require_sl: false
  min_sl_pips: 2
  min_rr_ratio: 0.5
  max_risk_per_trade_pct: 3.0
  max_total_exposure_pct: 30.0
  max_positions_per_symbol: 10
  max_total_positions: 20
  circuit_breaker:
    max_session_drawdown_pct: 20.0
    max_daily_drawdown_pct: 30.0
    cooldown_seconds: 30
```

### Aggressive Profile (Strategy Optimization)

```yaml
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
```

See [Risk Management Guide](RISK.md) for detailed configuration.

## Human-in-the-Loop Setup

HITL (Human-in-the-Loop) approval is required for certain operations in production.

### Enable HITL

```yaml
hitl:
  enabled: true
  tools:
    - order_send
    - position_close
  timeout_seconds: 300
  sink: terminal          # or webhook
  webhook_url: null       # Set if using webhook sink
  webhook_secret: null    # HMAC secret for webhook verification
```

### Disable HITL (Testing Only)

```yaml
hitl:
  enabled: false
  tools: []
```

### HITL via Terminal

When enabled, approval prompts appear in Claude terminal. User must type `yes` to approve order execution.

### HITL via Webhook

For remote approval:

```yaml
hitl:
  enabled: true
  sink: webhook
  webhook_url: https://your-approval-service.com/approve
  webhook_secret: your-secret-key
```

## Testing Connection

After setup, verify everything is working:

```bash
# Test Python COM bridge
python -m synx_mt5 test-connection

# Test with specific symbol
python -m synx_mt5 test-connection --symbol EURUSD

# Test EA File bridge (requires SYNX_EA running)
python -m synx_mt5 test-ea-bridge

# Run full integration tests
pytest tests/ -v
```

## Troubleshooting Setup

### MT5 Terminal Not Found

**Error:** `Failed to locate MetaTrader5 terminal`

**Solution:**
1. Verify MT5 is installed and running
2. Specify terminal path in config:
   ```yaml
   bridge:
     python_com:
       terminal_path: "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
   ```

### SYNX_EA Service Not Running

**Error:** `EA File bridge connection failed`

**Solution:**
1. Place `SYNX_EA.mq5` in Services folder (see EA File Bridge Setup above)
2. Compile in MT5 MetaEditor
3. Check MT5 journal for startup errors

### Credentials Not Found

**Error:** `Authentication failed: Invalid credentials`

**Solution:**
1. Store credentials in OS keyring vault (recommended)
2. Or set environment variables (development only)
3. Never put credentials in config files

### Python Package Import Errors

**Error:** `ModuleNotFoundError: No module named 'MetaTrader5'`

**Solution:**
```bash
# Reinstall in development mode
pip install -e .

# Or install MetaTrader5 directly
pip install MetaTrader5
```

See [Troubleshooting Guide](TROUBLESHOOTING.md) for additional issues.

## Next Steps

1. **Read Configuration Guide** — Understand all available settings in [CONFIG.md](CONFIG.md)
2. **Learn Risk Management** — Set up drawdown limits and position sizing in [RISK.md](RISK.md)
3. **Review Architecture** — Understand dual-bridge design in [ARCHITECTURE.md](ARCHITECTURE.md)
4. **API Reference** — See all 68+ available tools in [API.md](API.md)
5. **Troubleshooting** — Common issues and solutions in [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## Support

For additional help:
- Check [Troubleshooting Guide](TROUBLESHOOTING.md) for common issues
- Review logs in `~/.synx-mt5/logs/`
- See [Contributing Guide](CONTRIBUTING.md) for bug reports
