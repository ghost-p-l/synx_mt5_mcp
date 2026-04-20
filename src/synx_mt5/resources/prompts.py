"""MCP prompt templates - Structured prompts for trading agent workflows."""

SESSION_START_PROMPT = """\
You are connected to SYNX-MT5-MCP, a production-grade MT5 MCP server.

## First Session Actions

 1. Read mt5://synx/getting_started
 2. Read mt5://synx/python_api_boundary
 3. Call account_info to verify connection
 4. Use set_strategy_context to document your trading plan

## Safety Features

- Execution tools require HITL approval
- Risk limits are enforced deterministically
- All operations are audit logged

## Tools Available

Market Data: get_symbols, copy_rates_from_pos, get_market_regime, get_correlation_matrix
Account: account_info, positions_get, orders_get
Execution: order_send, position_close (with approval)
Intelligence: get_strategy_context, get_agent_memory

## Best Practices

- Always check risk_status before trading
- Use order_check before order_send
- Document strategy with set_strategy_context
- Use set_agent_memory to persist important data
"""

RISK_ACKNOWLEDGMENT_PROMPT = """\
## Risk Acknowledgment

Before executing orders, acknowledge:

1. Trading involves substantial risk of financial loss
2. Past performance does not guarantee future results
3. Circuit breaker may suspend execution if drawdown exceeds limits
4. HITL approval required for all execution tools
5. Verify all order parameters before approval

Proceed only if you understand and accept these risks.
"""

STRATEGY_DOCUMENTATION_PROMPT = """\
## Strategy Documentation Template

When using set_strategy_context, include:

- **Objective**: What are you trying to achieve?
- **Timeframe**: Intraday, swing, or position?
- **Instruments**: Which symbols and why?
- **Entry Criteria**: What conditions trigger entry?
- **Exit Criteria**: SL, TP, or time-based?
- **Risk Management**: Position sizing, max exposure?
- **Monitoring**: How will you track performance?

Example:
```
Objective: Trend following on EUR pairs
Timeframe: H4 swing trades
Entries: Break of 20-day high with ATR confirmation
Exits: 2x ATR trailing SL or 1:2 R:R
Risk: 1% per trade, max 3 positions
```
"""

EXECUTION_WORKFLOW_PROMPT = """\
## Order Execution Workflow

Always follow this sequence:

1. **Validate** - Use get_risk_status to confirm breaker is CLOSED
2. **Check** - Use order_check to verify broker accepts the order
3. **Calculate** - Use order_calc_margin to confirm sufficient margin
4. **Submit** - Use order_send with HITL approval
5. **Confirm** - Verify ticket in positions_get

Never skip order_check before order_send.
"""

REGIME_ANALYSIS_PROMPT = """\
## Market Regime Analysis

Use get_market_regime before selecting a strategy:

- TRENDING_UP / TRENDING_DOWN: Trend-following strategies
- RANGING: Mean-reversion strategies
- HIGH_VOLATILITY: Reduce position size, widen SL
- LOW_VOLATILITY: Potential breakout setups

Always check correlation matrix before opening correlated positions.
"""
