# Contributing to SYNX-MT5-MCP

## Philosophy

SYNX-MT5-MCP is security-first, community-owned, and production-grade. Contributions that prioritize features over security will not be merged. The consequence of a bug is not a broken UI — it is financial loss.

## Contribution Categories

| Category | Review Requirement |
|----------|-------------------|
| Security module changes | 2 maintainer approvals + adversarial test additions |
| Risk module changes | 2 maintainer approvals + integration test additions |
| New tools | 1 maintainer approval + unit tests + doc update |
| Intelligence layer | 1 maintainer approval + benchmark comparison |
| SYNX_EA MQL5 changes | 2 maintainer approvals + EA integration test |
| Documentation | 1 maintainer approval |
| Bug fixes | 1 maintainer approval + regression test |

## Development Setup

```bash
# Clone repository
git clone https://github.com/ghost-p-l/synx_mt5_mcp.git
cd synx_mt5_mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/unit/ -v

# Lint code
ruff check src/

# Type check
mypy src/
```

## Branch Strategy

- `main` — Stable, production-ready code (default branch)
- Feature branches — For individual features, branched from `main`

## Pull Request Process

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes
4. Add/update tests
5. Ensure linting and type checks pass
6. Submit PR targeting `main`

## Code Style

- Follow PEP 8
- Use type hints
- Add docstrings to public functions
- Keep functions focused and small

## Testing Requirements

- Unit tests for all new functionality
- Integration tests for bridge layer
- Adversarial tests for security modules
- Minimum 85% code coverage
