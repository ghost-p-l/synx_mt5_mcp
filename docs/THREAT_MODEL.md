# SYNX-MT5-MCP Threat Model

## Scope

SYNX-MT5-MCP operates at the intersection of:
- Financial account credentials
- AI agent tool invocation
- Windows-native proprietary protocol

## Adversary Classes

### T1: Passive Credential Harvester
**Capability:** Low  
**Vector:** Shell history, env var leakage, log scraping  
**Mitigation:** OS keyring storage, SecureString memory zeroing

### T2: Prompt Injection Attacker
**Capability:** Medium  
**Vector:** Malicious market data, broker messages, EA comments  
**Mitigation:** Injection Shield, NFKC normalization, control char stripping

### T3: Tool Poisoning Agent
**Capability:** Medium  
**Vector:** Modified tool metadata in forked/cached MCP registries  
**Mitigation:** Schema integrity hash, static tool descriptions

### T4: Supply Chain Attacker
**Capability:** High  
**Vector:** Compromised dependencies, malicious PyPI packages  
**Mitigation:** Dependency pinning, hash verification

### T5: Insider / Misconfigured Agent
**Capability:** High  
**Vector:** Hallucinating LLM issues destructive orders  
**Mitigation:** Risk Guard Middleware, HITL gates, circuit breakers

### T6: Race Condition Exploiter
**Capability:** High  
**Vector:** Duplicate order injection via retry storms  
**Mitigation:** Idempotency Engine with TTL dedup

## Attack Surface Map

```
[Agent Process]
    │
    ├─► stdio / HTTP ──► [MCP Server Process]
    │                           │
    │                    [SYNX Security Layer]
    │                           │
    │                    [Risk Guard Middleware]
    │                           │
    │                    [MT5 Bridge]
    │                           │
    │                    [terminal64.exe / EA REST]
    │                           │
    │                    [Broker SSL/TLS Channel]
    │                           │
    └─────────────────── [Broker Server / FIX Gateway]
```

Every arrow is an attack surface. Every layer is a control point.

## Security Boundaries

### Python API Boundary (32 Functions)
The official MetaTrader5 Python package exposes exactly 32 functions. Operations beyond this boundary require MQL5 Service or MetaEditor subprocess.

### What CAN be done via Python API:
- Market data (rates, ticks, DOM)
- Trading (orders, positions, history)
- Account & terminal info
- Symbol management

### What CANNOT be done via Python API:
- Chart open/close/navigate
- Chart screenshots
- Indicator add/remove
- Template apply/save
- Strategy Tester control
- MQL5 compilation

These require SYNX_EA REST bridge or MetaEditor subprocess.
