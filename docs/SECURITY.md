# SYNX-MT5-MCP Security Policy

## Overview

SYNX-MT5-MCP is designed with security-first principles for production trading environments.

## Security Model

### Defense Layers

1. **Credential Vault** - Credentials stored in OS keyring, never in env vars or logs
2. **Prompt Injection Shield** - All external input sanitized before agent context
3. **Capability Profiles** - Graduated tool access (read_only → analyst → executor → full)
4. **Risk Guard Middleware** - Pre-flight validation, circuit breakers, HITL gates
5. **Idempotency Engine** - Duplicate order prevention
6. **Audit Chain** - Tamper-evident append-only logging

### Threat Classes

| Class | Description | Mitigation |
|-------|-------------|------------|
| T1 | Credential Harvester | OS keyring, SecureString |
| T2 | Prompt Injection | Injection Shield |
| T3 | Tool Poisoning | Schema integrity hash |
| T4 | Supply Chain Attack | Dependency pinning |
| T5 | Hallucination Damage | Risk Guard, HITL |
| T6 | Retry Duplicates | Idempotency Engine |

## Security Axioms

1. Credentials never touch process arguments or logs
2. Execution tools are off by default; require explicit capability
3. All market data and broker messages are untrusted input
4. Every order carries a magic number for idempotency tracking
5. Risk limits are hard constraints, not advisory
6. Audit log is append-only and cryptographically chained
7. HITL gates are configurable per tool and per profile
8. Intelligence layer is stateless; no persistent memory of positions
9. Prompt injection is mitigated at every external input boundary

## Disclosure Policy

Report vulnerabilities to **security@synx-mt5.io** with subject `[SECURITY]`.

Response SLA:
- Acknowledgement: 24h
- Initial assessment: 72h
- Critical patch: 7 days
- High patch: 30 days

**Do not file public GitHub issues for security vulnerabilities.**
