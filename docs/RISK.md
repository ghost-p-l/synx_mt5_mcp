# SYNX-MT5-MCP Risk Management Guide

Comprehensive guide to SYNX risk management features including position sizing, drawdown limits, pre-flight validation, and circuit breaker configuration.

## Risk Management Architecture

```
Risk Management Layer
├─ Pre-Flight Validator
│  ├─ Symbol tradability check
│  ├─ Volume validation
│  ├─ Stop loss distance check
│  ├─ Risk:reward ratio validation
│  └─ Account SL requirement check
│
├─ Position Sizer
│  ├─ Calculate max volume based on risk
│  ├─ Respect position limits
│  ├─ Enforce exposure limits
│  └─ Account for existing positions
│
├─ Circuit Breaker
│  ├─ Track daily/session drawdown
│  ├─ Trigger on threshold breach
│  ├─ Enforce cooldown period
│  └─ Log all state changes
│
└─ Audit & Logging
   ├─ All decisions logged
   ├─ Tamper-evident audit trail
   ├─ Drawdown snapshots
   └─ Risk limit monitoring
```

## Pre-Flight Validation

Every order is validated before execution.

### Validation Steps

1. **Symbol Tradability**
   - Symbol exists in MT5
   - Trade mode allows trading (not suspended)
   - Symbol in MarketWatch

2. **Volume Validation**
   - Volume >= broker minimum
   - Volume <= broker maximum
   - Volume is multiple of broker's lot step

3. **Stop Loss Validation** (if SL provided)
   - SL distance >= min_sl_pips
   - SL distance > 0 (must be non-zero)
   - For demo accounts: optional
   - For live accounts: required (configurable)

4. **Risk:Reward Validation** (if TP provided)
   - Reward:Risk >= min_rr_ratio
   - For each pip risked, reward must be proportional

5. **Account SL Check**
   - Demo accounts: SL optional
   - Live accounts: SL required (if configured)

### Configuration

```yaml
risk:
  require_sl: true                 # Require SL for live accounts
  min_sl_pips: 10                  # Minimum SL distance (pips)
  min_rr_ratio: 1.0                # Minimum reward:risk ratio
```

### Example Validation

```
Order Request: EURUSD, BUY_MARKET, 0.1 lot, Entry 1.0850, SL 1.0840, TP 1.0870

Validation Steps:
1. Symbol Check
   └─ EURUSD exists ✓
   └─ Trade mode = Bidirectional ✓

2. Volume Check
   └─ Min volume: 0.01, Max volume: 100 ✓
   └─ 0.1 lot within range ✓

3. SL Validation
   └─ SL distance = 1.0850 - 1.0840 = 10 pips
   └─ Min required: 10 pips ✓

4. R:R Validation
   └─ Reward = 1.0870 - 1.0850 = 20 pips
   └─ Risk = 10 pips
   └─ R:R = 20/10 = 2.0:1 ✓
   └─ Min required: 1.0:1 ✓

Result: PASS ✓
Order allowed to execute
```

## Position Sizing

Intelligent position sizing respects risk limits.

### Risk-Based Sizing

**Formula:**
```
max_volume = (max_risk_pct × equity) / (entry_price - sl_price) × point_value
```

**Example:**
```
Equity: $10,000
Max risk per trade: 1% = $100
Entry: 1.0850 (EURUSD)
SL: 1.0840 (10 pips)
Risk per pip: $10 per lot (standard account)

Max volume = $100 / (1.0850 - 1.0840) / $100
           = $100 / $100
           = 1 lot (but capped at max broker limit)

Actual volume = min(1.0, broker_max_volume)
```

### Exposure Limits

Configuration:
```yaml
risk:
  max_risk_per_trade_pct: 1.0       # Max % of equity risked per trade
  max_total_exposure_pct: 10.0      # Max % total exposed
  max_positions_per_symbol: 3       # Max concurrent positions per symbol
  max_total_positions: 10           # Max total open positions
```

**Enforcement:**
- Pre-flight validator calculates risk for new order
- Checks against existing open positions
- Rejects if any limit would be exceeded
- Logs rejection reason

**Example Enforcement:**

```
Current Account State:
- Equity: $10,000
- Current exposure: 8% (5% risked in open trades)

New Order Request:
- Symbol: EURUSD
- Volume: 0.1 lot
- Entry: 1.0850
- SL: 1.0840 (10 pips = $100 risk on 0.1 lot)
- Risk: 1% of equity

Validation:
- New total risk: 5% + 1% = 6% ✓ (below 10% max)
- Positions on EURUSD: 1 ✓ (below 3 max per symbol)
- Total positions: 5 ✓ (below 10 max total)

Result: Order allowed
```

## Circuit Breaker

Automatically stops trading when drawdown exceeds configured limits.

### Drawdown Tracking

**Types:**
1. **Session Drawdown** — From session start to current equity
2. **Daily Drawdown** — From daily open to current equity
3. **Peak-to-Trough** — From highest equity this session to current

**Example:**

```
Day Start Equity: $10,000

Events:
- Trade 1: +$200 (equity: $10,200)
- Trade 2: -$400 (equity: $9,800)  ← Peak $10,200
- Trade 3: -$200 (equity: $9,600)

Current Drawdown:
- Session: $10,000 → $9,600 = 4.0% ✓ (below 5% trigger)
- Daily: $10,000 → $9,600 = 4.0% ✓ (below 10% trigger)
- Peak: $10,200 → $9,600 = 5.9% ✓ (below 5% trigger)

Status: Trading continues
```

### Circuit Breaker States

**CLOSED** (Normal)
- Equity above thresholds
- Orders allowed
- No restrictions

**OPEN** (Triggered)
- Drawdown exceeded threshold
- Orders rejected
- Cooldown period active

**RECOVERY** (Recovering)
- Cooldown period active
- Equity improving
- Orders still rejected until cooldown expires

### Configuration

```yaml
risk:
  circuit_breaker:
    max_session_drawdown_pct: 5.0      # Trigger at 5% session loss
    max_daily_drawdown_pct: 10.0       # Hard stop at 10% daily loss
    cooldown_seconds: 60               # Pause 60 seconds before retry
```

### Triggering Example

```
Configuration:
- max_session_drawdown_pct: 5.0
- max_daily_drawdown_pct: 10.0
- cooldown_seconds: 60

Event Timeline:
10:00 AM - Session starts at $10,000
10:30 AM - Equity drops to $9,520 (4.8% drawdown) ✓ Still OK
10:45 AM - Equity drops to $9,490 (5.1% drawdown) ✗ TRIGGER!

Action Taken:
1. Circuit breaker state changes to OPEN
2. All pending orders canceled
3. No new orders accepted
4. Cooldown timer started (60 seconds)
5. Event logged: "Circuit breaker triggered, session_drawdown=5.1%"

10:46 AM (after cooldown):
- Equity recovered to $9,600 (4.0% drawdown) ✓
- Circuit breaker state changes to RECOVERY
- Orders allowed to resume

Status Messages:
- "Circuit breaker OPEN - trading paused"
- "Circuit breaker RECOVERY - resume in 45 seconds"
- "Circuit breaker CLOSED - trading resumed"
```

## Risk Profile Configurations

### Standard (Production Trading)

Safe defaults for live trading.

```yaml
profile: executor

risk:
  require_sl: true                    # SL mandatory
  min_sl_pips: 10                     # Minimum 10 pip SL
  min_rr_ratio: 1.0                   # 1:1 minimum R:R
  max_risk_per_trade_pct: 1.0         # Risk 1% per trade
  max_total_exposure_pct: 10.0        # 10% total exposure
  max_positions_per_symbol: 3         # 3 per symbol
  max_total_positions: 10             # 10 total
  
  circuit_breaker:
    max_session_drawdown_pct: 5.0     # Stop at 5% loss
    max_daily_drawdown_pct: 10.0      # Hard stop at 10%
    cooldown_seconds: 60              # 1 minute cooldown

hitl:
  enabled: true
  tools: [order_send, position_close]
```

**Best for:**
- Live trading with real money
- Risk-conscious traders
- Professional accounts

### Conservative (Safety-First)

Ultra-safe for precious capital.

```yaml
profile: executor

risk:
  require_sl: true
  min_sl_pips: 20                     # Large SL buffer
  min_rr_ratio: 2.0                   # 2:1 minimum R:R
  max_risk_per_trade_pct: 0.5         # Risk only 0.5% per trade
  max_total_exposure_pct: 5.0         # 5% total (very low)
  max_positions_per_symbol: 1         # Only 1 position at a time
  max_total_positions: 5              # 5 total max
  
  circuit_breaker:
    max_session_drawdown_pct: 3.0     # 3% trigger
    max_daily_drawdown_pct: 5.0       # 5% hard stop
    cooldown_seconds: 300             # 5 minute cooldown

hitl:
  enabled: true
  tools: [order_send, position_close]
```

**Best for:**
- Capital preservation focus
- First-time traders
- Risk-averse accounts

### Testing (Demo Account)

Permissive for strategy testing.

```yaml
profile: executor

risk:
  require_sl: false                   # SL optional
  min_sl_pips: 0                      # No minimum
  min_rr_ratio: 0.01                  # Ultra-low requirement
  max_risk_per_trade_pct: 5.0         # 5% per trade
  max_total_exposure_pct: 50.0        # 50% total
  max_positions_per_symbol: 10        # 10 per symbol
  max_total_positions: 50             # 50 total
  
  circuit_breaker:
    max_session_drawdown_pct: 50.0    # 50% session
    max_daily_drawdown_pct: 80.0      # 80% daily
    cooldown_seconds: 30              # Short cooldown

hitl:
  enabled: false
  tools: []

idempotency:
  ttl_seconds: 5                      # Short TTL for rapid trading
  max_cache_size: 100
```

**Best for:**
- Demo/backtesting
- Strategy validation
- Aggressive testing

### Aggressive (Optimization)

Maximum flexibility for optimization.

```yaml
profile: full

risk:
  require_sl: true
  min_sl_pips: 3                      # Small SL
  min_rr_ratio: 0.8                   # Low R:R requirement
  max_risk_per_trade_pct: 2.0         # 2% per trade
  max_total_exposure_pct: 20.0        # 20% total
  max_positions_per_symbol: 5         # 5 per symbol
  max_total_positions: 20             # 20 total
  
  circuit_breaker:
    max_session_drawdown_pct: 50.0
    max_daily_drawdown_pct: 80.0
    cooldown_seconds: 60

hitl:
  enabled: false
```

**Best for:**
- Parameter optimization
- Backtesting
- Aggressive demo trading

## Calculating Risk

### Formula

```
Risk = (Entry Price - Stop Loss Price) × Volume × Point Value × Pip Value
Risk % = Risk / Account Equity × 100
```

### Example: EURUSD

```
Account Equity: $10,000
Entry: 1.0850
Stop Loss: 1.0840
Volume: 0.1 lot

Risk Calculation:
- SL Distance = 1.0850 - 1.0840 = 0.0010 = 10 pips
- Risk per pip per lot = $10
- Total Risk = 10 pips × 0.1 lot × $10/pip = $100
- Risk % = $100 / $10,000 × 100 = 1%

Result: Risking 1% of equity (acceptable for max_risk_per_trade_pct: 1%)
```

### Example: GBPUSD

```
Account Equity: $10,000
Entry: 1.2750
Stop Loss: 1.2720
Volume: 0.1 lot

Risk Calculation:
- SL Distance = 1.2750 - 1.2720 = 0.0030 = 30 pips
- Risk per pip per lot = $10
- Total Risk = 30 pips × 0.1 lot × $10/pip = $300
- Risk % = $300 / $10,000 × 100 = 3%

Result: Risking 3% of equity (exceeds max_risk_per_trade_pct: 1%)
Action: Order rejected, volume needs reduction
```

## Position Sizing Examples

### Conservative Position Sizing

```
Account: $10,000
Max Risk Per Trade: 1% = $100

Trade Setup 1 (Forex):
- Entry: 1.0850, SL: 1.0840
- SL Distance: 10 pips
- Max Volume = $100 / (10 pips × $10/pip) = 0.1 lot ✓

Trade Setup 2 (Forex with larger SL):
- Entry: 1.0850, SL: 1.0800
- SL Distance: 50 pips
- Max Volume = $100 / (50 pips × $10/pip) = 0.02 lot ✓
```

### Risk Adjustment

```
Scenario: Account down to $8,000

With Max Risk = 1%:
- Max Risk Amount = $80 per trade
- Fewer pips SL = smaller lot size
- Larger pips SL = even smaller lot size

Example:
- Entry: 1.0850, SL: 1.0840 (10 pips)
- Max Volume = $80 / (10 pips × $10/pip) = 0.08 lot

Position size automatically scales with account drawdown
```

## Monitoring Risk

### Real-Time Risk Monitoring

```bash
# Check current drawdown
python -m synx_mt5 check-drawdown

# Monitor circuit breaker status
python -m synx_mt5 check-circuit-breaker

# View risk configuration
python -m synx_mt5 show-risk-config
```

### Risk Audit Log

All risk decisions logged:

```json
{
  "timestamp": "2026-04-20T10:30:15Z",
  "event": "pre_flight_validation",
  "tool": "order_send",
  "symbol": "EURUSD",
  "volume": 0.1,
  "calculated_risk_pct": 1.0,
  "max_risk_pct": 1.0,
  "passed": true
}
```

```json
{
  "timestamp": "2026-04-20T10:45:30Z",
  "event": "circuit_breaker_triggered",
  "session_drawdown_pct": 5.1,
  "threshold_pct": 5.0,
  "action": "pause_trading",
  "cooldown_until": "2026-04-20T10:46:30Z"
}
```

## Best Practices

1. **Set Risk Limits First**
   - Define max_risk_per_trade_pct before trading
   - Match to your risk tolerance
   - Document your limits

2. **Use Appropriate Profile**
   - Production: Use "Standard" profile
   - Testing: Use "Testing" profile
   - Don't mix production and demo settings

3. **Monitor Drawdown Regularly**
   - Check equity daily
   - Review circuit breaker state
   - Adjust position sizes if equity changes significantly

4. **Honor Stop Losses**
   - Never move SL against your position
   - SL is your risk limit
   - Let the system enforce it

5. **Review Risk Logs**
   - Check audit logs weekly
   - Look for unexpected rejections
   - Verify circuit breaker is working

6. **Plan Position Sizing**
   - Calculate max volume before trading
   - Don't guess at position size
   - Let the validator check your math

## Risk Management Examples

### Day Trading (High Frequency)

```yaml
risk:
  require_sl: true
  min_sl_pips: 5
  min_rr_ratio: 0.5
  max_risk_per_trade_pct: 0.5
  max_total_exposure_pct: 5.0
  max_positions_per_symbol: 5
  max_total_positions: 20
```

**Reasoning:**
- Smaller SLs for day trading range
- Tighter exposure limits
- Multiple positions but careful tracking

### Swing Trading (Multi-Day)

```yaml
risk:
  require_sl: true
  min_sl_pips: 25
  min_rr_ratio: 1.5
  max_risk_per_trade_pct: 1.0
  max_total_exposure_pct: 10.0
  max_positions_per_symbol: 2
  max_total_positions: 5
```

**Reasoning:**
- Larger SLs for longer-term swings
- Higher R:R ratio for better risk:reward
- Fewer positions for simpler tracking

### Scalping (Very Short-Term)

```yaml
risk:
  require_sl: false              # Tight stops handled manually
  min_sl_pips: 1
  min_rr_ratio: 0.1
  max_risk_per_trade_pct: 0.3
  max_total_exposure_pct: 3.0
  max_positions_per_symbol: 1
  max_total_positions: 3

idempotency:
  ttl_seconds: 5
  max_cache_size: 50
```

**Reasoning:**
- Minimal SL required
- Very small position sizes
- Quick entry/exit
- Reduced idempotency window for rapid orders

## See Also

- [Configuration Reference](CONFIG.md) — Risk configuration options
- [Troubleshooting Guide](TROUBLESHOOTING.md) — Risk-related issues
- [Setup Guide](SETUP.md) — Initial risk profile selection
