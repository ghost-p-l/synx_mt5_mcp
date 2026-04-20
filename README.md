# SYNX-MT5-MCP

> **SYNX** — Production-grade Dual-Bridge MCP Server for MetaTrader 5

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Protocol](https://img.shields.io/badge/MCP-Nov%202025-green.svg)](https://modelcontextprotocol.io)

## Overview

SYNX-MT5-MCP is a production-ready MCP server for MetaTrader 5 that enables AI agents to interact with MT5 terminals securely, reliably, and at scale. Compatible with Claude Code, Claude Desktop, Gemini CLI, OpenCode Desktop, and OpenCode CLI:

- **Dual-Bridge Architecture** — Seamless python_com (fast ops) + ea_file (EA operations) integration
- **Security-first design** — Credential vault, prompt injection shield, tool poisoning defenses
- **Risk management** — Pre-flight validation, position sizing, drawdown circuit breaker, human-in-the-loop approval
- **Intelligence layer** — Market regime detection, correlation tracking, strategy context, MQL5 code generation
- **Audit trail** — Tamper-evident append-only logging with cryptographic verification
- **Idempotent execution** — Magic number dedup prevents duplicate orders from LLM retries

## Features

### Core Capabilities
- **Full MT5 Coverage** — 68+ MCP tools covering all MT5 operations
- **Dual-Bridge Operation** — python_com for fast reads, ea_file for EA operations, automatic failover
- **Chart Control** — Open, close, screenshot, attach EAs, apply/save templates, add indicators
- **MQL5 Development** — Write, compile with error tracking, deploy indicators/EAs, run scripts
- **Strategy Testing** — Backtest, optimize, analyze results, view equity curves
- **Market Data** — OHLCV bars, tick data, market depth (DOM), real-time quotes
- **Position Management** — Open, modify, close positions with intelligent sizing

### Security
- **Credentials** — OS keyring vault (never in env vars or logs)
- **Validation** — Prompt injection shield, tool metadata verification
- **Profiles** — 4 graduated capability levels (read_only → analyst → executor → full)
- **Audit** — Cryptographically verified transaction log
- **Risk Guards** — Pre-flight checks, position sizing, drawdown limits

### Intelligent Trading
- **Market Regime** — Trending, ranging, volatility classification
- **Correlation** — Cross-symbol correlation matrix with warnings
- **Agent Memory** — Disk-backed persistent strategy context
- **Code Generation** — Auto-generate MQL5 for custom logic
- **Risk Control** — Circuit breaker, drawdown tracking, HITL approval

## Quick Start

### Prerequisites
- Python 3.11+
- MetaTrader 5 terminal (Windows)
- AI agent with MCP support (Claude Code, Claude Desktop, Gemini CLI, OpenCode Desktop, OpenCode CLI)

### Quick Prompt

Paste this directly into your AI agent to get started:

```
Set up SYNX-MT5-MCP from https://github.com/ghost-p-l/synx_mt5_mcp. 
Clone the repository, install dependencies, configure credentials, and integrate with my MCP configuration.
```

### Installation

```bash
# Clone repository
git clone https://github.com/ghost-p-l/synx_mt5_mcp.git
cd synx_mt5_mcp

# Install development dependencies
pip install -e .
```

### Configuration

```bash
# Copy and configure
cp ~/.synx-mt5/synx.yaml.example ~/.synx-mt5/synx.yaml
# Edit config with your preferences
```

See [Configuration Guide](docs/SETUP.md) for detailed setup instructions.

### AI Agent Integration

Add to your MCP configuration file:

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

Works with Claude Code, Claude Desktop, Gemini CLI, OpenCode Desktop, and OpenCode CLI. See [Setup Guide](docs/SETUP.md) for platform-specific configuration.

## Documentation

### Getting Started
- [Setup Guide](docs/SETUP.md) — Installation, configuration, credential setup
- [Configuration Reference](docs/CONFIG.md) — All configuration options explained
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md) — Solutions to common issues

### Architecture & Design
- [Dual-Bridge Architecture](docs/ARCHITECTURE.md) — How python_com + ea_file work together
- [Implementation Specification](docs/IMPLEMENTATION.md) — Technical deep dive
- [API Reference](docs/API.md) — Complete tool reference (68 tools)

### Security & Risk
- [Security Policy](docs/SECURITY.md) — Security model and disclosure process
- [Threat Model](docs/THREAT_MODEL.md) — Detailed threat analysis
- [Risk Management](docs/RISK.md) — Circuit breaker, position sizing, HITL

### Development
- [Contributing Guide](docs/CONTRIBUTING.md) — How to contribute
- [Python API Boundary](docs/PYTHON_API_BOUNDARY.md) — Verified python-mt5 functions

## Capability Profiles

| Profile | Use Case | Key Restrictions |
|---------|----------|-----------------|
| **read_only** | Data analysis | Market data only |
| **analyst** | Strategy research | + Intelligence, no execution |
| **executor** | Live trading | + Order execution, chart control |
| **full** | Admin/testing | Everything including destructive ops |

## Bridge Modes

| Mode | Latency | Features | Use Case |
|------|---------|----------|----------|
| **python_com** | <100ms | Fast data, quotes, indicators | High-frequency data fetching |
| **ea_file** | <1s | Chart ops, EA attachment, backtesting | EA management, testing |
| **composite** | <100ms | Both with intelligent routing | Production (recommended) |

## Risk Management

### Position Sizing
```yaml
max_risk_per_trade_pct: 1.0      # Max risk as % of equity
max_total_exposure_pct: 30.0     # Total exposure limit
```

### Circuit Breaker
```yaml
max_session_drawdown_pct: 5.0    # Stop trading on drawdown
max_daily_drawdown_pct: 10.0     # Daily hard stop
cooldown_seconds: 60             # Cooldown after trigger
```

See [Risk Management Guide](docs/RISK.md) for detailed configuration.

## Common Issues & Solutions

### Circuit Breaker Triggered
**Problem:** Orders rejected with "Circuit breaker in OPEN state"

**Solution:** See [HITL & Circuit Breaker Troubleshooting](docs/TROUBLESHOOTING.md#circuit-breaker)

### HITL Approval Timeout
**Problem:** Trades pending indefinitely with "HITL timeout"

**Solution:** See [HITL Configuration](docs/TROUBLESHOOTING.md#hitl-approval)

### Bridge Connection Failed
**Problem:** "Failed to connect to MT5 terminal"

**Solution:** See [Bridge Setup & Troubleshooting](docs/SETUP.md#bridge-setup)

## Project Structure

```
synx_mt5_mcp/
├── docs/                    # Comprehensive documentation
│   ├── SETUP.md            # Installation & setup guide
│   ├── CONFIG.md           # Configuration reference
│   ├── ARCHITECTURE.md     # Dual-bridge design
│   ├── RISK.md             # Risk management guide
│   ├── TROUBLESHOOTING.md  # Problem solutions
│   └── ...
├── src/synx_mt5/           # Main source code
│   ├── bridge/             # python_com, ea_file, composite
│   ├── tools/              # 68+ MCP tools
│   ├── risk/               # Validation, circuit breaker
│   ├── security/           # Auth, audit, injection shield
│   └── intelligence/       # Market regime, correlation, codegen
├── config/                 # Default configurations
│   └── risk/              # Profile templates
└── tests/                 # Test suite
```

## Performance

- **Data Fetching** — <100ms for quotes/OHLCV
- **Order Execution** — <500ms to MT5
- **Chart Operations** — <1s via EA service
- **Compilation** — ~850ms for MQL5 files
- **Backtest** — ~60s per day tested (varies by EA)

## Security Considerations

1. **Credential Storage** — Never store credentials in env vars or config files
2. **HITL Approval** — Use for live/large trades
3. **Pre-flight Validation** — Prevents order mistakes
4. **Audit Logging** — All operations recorded and verified
5. **Profile Restrictions** — Use least-privilege profile

## License

MIT License — See LICENSE file for details

## Support

For issues, questions, or contributions:
- Check [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- Review [Architecture Documentation](docs/ARCHITECTURE.md)
- See [Contributing Guide](docs/CONTRIBUTING.md)

---

**SYNX-MT5-MCP** — Intelligent, secure, production-ready MetaTrader 5 integration
