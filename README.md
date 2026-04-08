# MnesOS

> MnesOS is fully Agentic RPG Game Engine.

[![PyPI version](https://badge.fury.io/py/MnesOS.svg)](https://badge.fury.io/py/MnesOS)
[![Documentation](https://img.shields.io/badge/docs-gh--pages-blue)](https://neolaw84.github.io/MnesOS/)

## Installation

```bash
pip install MnesOS
```

Or install the latest development build directly from GitHub Releases:

```bash
pip install https://github.com/neolaw84/MnesOS/releases/latest/download/MnesOS-latest-py3-none-any.whl
```

## Quick Start

```python
import MnesOS

# Your code here
```

## Development

### Set up the environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,docs]"
```

### Bootstrap GitHub branch rules and labels

Use the script below once after creating a new repository from this template.

```bash
python -m venv script-venv
source script-venv/bin/activate   # Windows: script-venv\Scripts\activate
pip install --upgrade pip
pip install -r scripts/requirements-github-rules.txt

export GITHUB_TOKEN="<your-admin-token>"
python scripts/setup_github_rules.py --repo neolaw84/MnesOS
```

The script configures:
- branch protection for `main` and `dev`
- required labels (`bump:major`, `bump:minor`, `bump:patch`)
- Actions workflow permissions (`GITHUB_TOKEN` read/write)

### Run tests

```bash
pytest
```

### Build documentation locally

```bash
mkdocs serve
```

## Contributing

1. Fork the repository and create your feature branch from **dev**.
2. Add tests for every new behaviour.
3. Open a Pull Request targeting **dev** — CI will gate on tests + coverage.
4. Label your PR with `bump:major`, `bump:minor` (default), or `bump:patch` to control the version bump.

## License

MIT — see [LICENSE](LICENSE) for details.
