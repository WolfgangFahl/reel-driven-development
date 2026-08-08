# Agent Guidelines for reel-driven-development

This file provides guidelines and commands for agentic coding agents working in this repository.

## Project Overview

Reel Driven Development (RDD) turns recorded user walks (reels) into domain stories and outcome objects. This package provides the RDD tooling, starting with HopDetection: finding every hop boundary in a screen-share reel and capturing a representative evidence frame.

- **Main package**: `rdd/`
- **Tests**: `tests/`
- **Python**: 3.10+

Method reference: https://wiki.bitplan.com/index.php/Reel_Driven_Development

Schema reference: https://contexts.bitplan.com/index.php/Meeting

## Agent to apply
The python expert Agent/Guido is to be consulted if available in the current context

## Core Method Rules

- A hop is every context switch (page, browser tab, application) and every relevant interaction (submenu, filter, zoom, sort).
- Completeness is defined over hops, never over frames.
- Frame capture is transcript-anchored multi-phase bisection, never a uniform grid.
- "No screenshot" is only valid as a proven result (frame-level refinement showed the content never appeared) or a deliberate redaction - never as a sampling artifact.
- Assert only with evidence; abstain on conflict.

## Build & Installation

```bash
# Install package in development mode
pip install . -U

# Or use the script
./scripts/install
```

## Testing

```bash
# Using unittest discover (default)
python3 -m unittest discover

# Using the test script
./scripts/test

# Single test file / class / method
python -m unittest tests.test_hop
python -m unittest tests.test_hop.TestHop
python -m unittest tests.test_hop.TestHop.test_hop

# Other runners
./scripts/test --green
./scripts/test --tox
./scripts/test --module
```

- Test files: `tests/test_*.py`, classes `TestXxx`, methods `test_xxx`
- All test classes inherit from `Basetest` (`basemkit.basetest`)
- No pytest fixtures, no conftest.py - unittest style only
- `Basetest.inPublicCI()` gates tests that need local resources (e.g. video files)

## Code Formatting

```bash
# black + isort + docformatter - run before every commit
./scripts/blackisort
```

- Maximum line length: 88 characters (black default)
- Imports: three groups (standard library, third-party, local), sorted by isort

## CLI Standard

The `hopdetect` CLI follows the BITPlan house standard a main class with superclass
`basemkit.base_cmd.BaseCmd`, which provides `-a/--about`,
`-d/--debug`, `--debugServer`, `-f/--force`, `-q/--quiet`, `-v/--verbose`,
`-V/--version` and the exit codes 0 = OK, 1 = KeyboardInterrupt,
2 = Exception. Any new CLI in this project subclasses `BaseCmd` - never
plain `argparse`. Pattern reference: the
[CLI Tooling section of the pybasemkit README](https://github.com/WolfgangFahl/pybasemkit#cli-tooling).

## Code Style Guidelines

- Google-style docstrings on every public function and class
- Type hints on all function signatures; prefer `Optional[X]` over `X | None`
- Module header docstring with creation date and `@author: wf`
- Functions/methods `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`
- Named return variable, single return at the end - never direct expression returns
- Top-level imports only; optional dependencies via `try/except ImportError` at module level
- No custom exception hierarchy - plain or standard exceptions
- Dependencies must be justified - prefer the standard library

## Version Bumping

Version lives in `rdd/__init__.py`:

```python
__version__ = "0.0.1"
```

## Git Workflow

1. Read the issue to work on
2. Make changes following the code style guidelines
3. Run formatters: `./scripts/blackisort`
4. Run tests: `./scripts/test`
5. Commit with a descriptive message referencing the issue
6. Push

## Release

```bash
# Builds docs and commits + pushes
./scripts/release
```
