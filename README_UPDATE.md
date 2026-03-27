# Development Guide

## Project Structure

```
localSendCli/
├── pylocalsend/               # Python package
│   ├── __init__.py            # Package version (__version__)
│   └── cli.py                 # Main program (entry point: main())
├── pyproject.toml             # Package metadata, dependencies, build config, entry points
├── requirements.txt           # Dependencies for quick install (pip install -r)
├── LICENSE                    # MIT License
├── README.md                  # User-facing documentation
├── DEVELOPMENT.md             # This file
├── localsendcli.py            # Standalone script (original single-file version)
└── .gitignore                 # Git ignore rules
```

### Key Files

| File | Purpose |
|------|---------|
| `pylocalsend/cli.py` | All application logic: HTTP server, mDNS discovery, interactive shell, file transfer, messaging |
| `pylocalsend/__init__.py` | Defines `__version__`, making it importable via `from pylocalsend import __version__` |
| `pyproject.toml` | Declares package name, version, dependencies, optional extras, CLI entry point (`pylocalsend` command) |
| `localsendcli.py` | Standalone copy for direct use without installation (`python3 localsendcli.py`) |

## First-Time Setup

### Prerequisites

```bash
pip install build twine
```

### PyPI Account

1. Register at https://pypi.org/account/register/
2. Create an API token at https://pypi.org/manage/account/#api-tokens
3. Configure `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi

[pypi]
username = __token__
password = pypi-YOUR_TOKEN_HERE
```

4. Secure the file:

```bash
chmod 600 ~/.pypirc
```

## Publishing a New Release

### Step 1: Update Version

Update the version number in **both** files:

**`pylocalsend/__init__.py`**:
```python
__version__ = "0.2.0"
```

**`pyproject.toml`**:
```toml
version = "0.2.0"
```

### Step 2: Sync Standalone Script

If `localsendcli.py` should stay in sync:

```bash
cp pylocalsend/cli.py localsendcli.py
```

### Step 3: Clean Previous Build

```bash
rm -rf dist/ build/ *.egg-info pylocalsend/*.egg-info
```

### Step 4: Build

```bash
python -m build
```

This creates two files in `dist/`:
- `pylocalsend-0.2.0.tar.gz` — source distribution
- `pylocalsend-0.2.0-py3-none-any.whl` — wheel (binary distribution)

### Step 5: Upload to PyPI

```bash
twine upload dist/*
```

### Step 6: Verify

```bash
pip install --upgrade pylocalsend
pylocalsend --help
```

## Quick Publish Script

All steps combined:

```bash
# Update version in __init__.py and pyproject.toml first, then:
cp pylocalsend/cli.py localsendcli.py
rm -rf dist/ build/ *.egg-info
python -m build
twine upload dist/*
```

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

| Change Type | Version Bump | Example |
|-------------|-------------|---------|
| Bug fix | Patch +1 | `0.1.0` → `0.1.1` |
| New feature (backward compatible) | Minor +1 | `0.1.0` → `0.2.0` |
| Breaking change | Major +1 | `0.2.0` → `1.0.0` |

## Testing Before Publish

### Test with TestPyPI

Upload to the test index first:

```bash
twine upload --repository testpypi dist/*
```

Install from TestPyPI to verify:

```bash
pip install --index-url https://test.pypi.org/simple/ pylocalsend
```

Note: TestPyPI requires a separate account at https://test.pypi.org/

### Local Editable Install

For development and testing without publishing:

```bash
pip install -e .
```

Changes to `pylocalsend/cli.py` take effect immediately without reinstalling.
