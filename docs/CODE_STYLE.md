# Code Style Guide

> This document defines the coding standards used throughout the XAUUSD Algorithmic Trading Platform.

---

# Purpose

The purpose of this guide is to ensure that every module follows the same coding conventions, making the project easier to understand, maintain, test, and extend.

All contributors should follow these standards.

---

# Python Version

The project targets:

- Python 3.14+

New language features may be used when they improve readability and maintainability.

---

# General Principles

Every piece of code should prioritize:

- Correctness
- Readability
- Maintainability
- Testability
- Performance (when justified)

Avoid writing clever code that reduces readability.

---

# Naming Conventions

## Variables

Use descriptive snake_case names.

Good:

```python
market_structure
trade_probability
current_trend
```

Bad:

```python
x
tmp
abc
```

---

## Functions

Functions should use verbs.

Examples:

```python
calculate_probability()
detect_bos()
generate_signal()
validate_trade()
```

---

## Classes

Use PascalCase.

Examples:

```python
MarketStructureEngine
ProbabilityEngine
SignalGenerator
TradePlan
```

---

## Constants

Use UPPER_CASE.

Example:

```python
DEFAULT_LOOKBACK
MAX_HISTORY
MIN_CONFIDENCE
```

---

# Type Hints

All public functions should use type hints.

Good:

```python
def calculate_probability(features: FeatureVector) -> ProbabilityResult:
```

Avoid missing annotations.

---

# Dataclasses

Prefer dataclasses for immutable models.

Example:

```python
@dataclass(frozen=True, slots=True)
class ProbabilityResult:
```

Use `slots=True` where appropriate to reduce memory usage.

---

# Functions

Functions should:

- Have one responsibility.
- Be small and focused.
- Return predictable results.
- Avoid hidden side effects.

Prefer:

```python
detect_bos()
```

instead of:

```python
process_everything()
```

---

# Classes

Classes should follow the Single Responsibility Principle.

A class should have one reason to change.

Avoid large "God Objects."

---

# Imports

Standard order:

```python
# Standard library

# Third-party packages

# Local project imports
```

Avoid wildcard imports.

Good:

```python
from dataclasses import dataclass
```

Bad:

```python
from module import *
```

---

# Documentation

Every public class should include a docstring.

Example:

```python
class BOSDetector:
    """Detects Break of Structure events."""
```

Public methods should also be documented when the behavior is not obvious.

---

# Exceptions

Raise specific exceptions.

Good:

```python
raise ValueError(...)
```

Avoid:

```python
except:
```

Catch only expected exceptions.

---

# Logging

Use the logging framework.

Avoid:

```python
print(...)
```

Logging should include useful context without exposing sensitive information.

---

# Configuration

Configuration values should live in configuration classes or configuration files.

Avoid hard-coded values scattered throughout the codebase.

---

# Immutability

Result objects should be immutable whenever practical.

Example:

```python
@dataclass(frozen=True)
```

This prevents accidental modification after creation.

---

# Dependencies

Dependencies should flow in one direction.

```
Market Structure
        ↓
Feature Engineering
        ↓
Probability Engine
        ↓
Signal Generator
        ↓
Risk Manager
        ↓
Trading Pipeline
```

Higher-level packages should not be imported into lower-level packages.

---

# Testing

Every new feature should include appropriate tests.

Testing includes:

- Unit tests
- Integration tests
- Regression tests (when applicable)

Run before committing:

```bash
python -m pytest
```

---

# Code Review Checklist

Before committing code, verify:

- Correctness
- Readability
- Type hints
- Documentation
- Tests pass
- No unused imports
- No dead code
- No duplicated logic
- No hard-coded magic values

---

# Design Philosophy

The project follows:

- Domain-Driven Design (DDD)
- SOLID Principles
- Composition over inheritance
- Deterministic processing
- Modular architecture
- Separation of concerns

---

# Summary

The goal of this code style guide is consistency.

Readable, maintainable, and well-tested code is preferred over overly clever or unnecessarily complex implementations.