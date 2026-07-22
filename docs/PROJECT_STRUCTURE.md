# Project Structure

> This document describes the directory layout of the XAUUSD Algorithmic Trading Platform and the responsibility of each major package.

---

# Overview

The project is organized into modular packages, where each package has a single responsibility. This structure improves maintainability, scalability, testing, and future expansion.

```
Trading Intelligence PlatformV2/
│
├── core/
├── configs/
├── data/
├── docs/
├── tests/
├── scripts/
├── logs/
├── reports/
├── README.md
└── requirements.txt
```

---

# Root Directory

The root directory contains the project entry points, configuration files, and documentation.

Examples:

- README.md
- requirements.txt
- pyproject.toml
- run_backtest.py
- run_live.py

---

# core/

The `core` package contains the trading engine.

Every package inside `core` represents an independent subsystem.

```
core/
```

---

## market_structure/

Responsible for understanding market behavior.

Contains:

- Swing Detection
- Break of Structure (BOS)
- Change of Character (CHOCH)
- Liquidity Detection
- Market Structure Measurements

Output:

- Structural events
- Measurements
- Feature-ready information

---

## feature_engineering/

Converts raw market information into numerical trading features.

Examples:

- Structure confidence
- Liquidity quality
- Trend strength
- Confluence features

Output:

- Feature vector

---

## probability_engine/

Responsible for estimating trade probability.

Responsibilities:

- Probability calculation
- Confidence estimation
- Feature weighting

Output:

- Probability score

---

## signal_generator/

Creates trading opportunities.

Responsibilities:

- Signal generation
- Opportunity ranking
- Trade filtering

Output:

- Trading signals

---

## regime_detector/

Determines the current market regime.

Examples:

- Trending
- Ranging
- High volatility
- Low volatility

Output:

- Market regime

---

## risk_manager/

Creates executable trade plans.

Responsibilities:

- Position sizing
- Stop-loss
- Take-profit
- Risk validation

Output:

- Trade plan

---

## trading_pipeline/

Coordinates the complete workflow.

Responsibilities:

- Execute components
- Pass results
- Produce deterministic output

Contains no trading strategy logic.

---

## backtesting/

Evaluates strategies using historical data.

Responsibilities:

- Trade simulation
- Performance statistics
- Reporting

---

## research_analytics/

Provides research tools for improving trading performance.

Examples:

- Feature importance
- Win/Loss analysis
- Research reports
- Performance analytics

---

# configs/

Stores configuration files.

Examples:

- Trading settings
- Risk settings
- Environment configuration

---

# data/

Contains project data.

Examples:

- Historical market data
- Cached data
- Imported datasets

---

# docs/

Contains all project documentation.

Examples:

- Architecture
- Roadmap
- Code Style
- Design Principles
- Contributing Guide
- Changelog

---

# tests/

Contains automated tests.

Examples:

- Unit tests
- Integration tests
- Regression tests

Testing framework:

- pytest

---

# scripts/

Utility scripts used during development.

Examples:

- Data import
- Data conversion
- Maintenance tools

---

# logs/

Application logs.

Examples:

- Runtime logs
- Debug logs
- Error logs

---

# reports/

Generated reports.

Examples:

- Backtest reports
- Research reports
- Performance summaries

---

# Design Philosophy

The project structure follows several principles:

- One package, one responsibility.
- Clear dependency direction.
- Independent subsystems.
- Easy testing.
- Easy maintenance.
- Future scalability.

---

# Dependency Overview

```
Market Structure
        │
        ▼
Feature Engineering
        │
        ▼
Probability Engine
        │
        ▼
Signal Generator
        │
        ▼
Risk Manager
        │
        ▼
Trading Pipeline
        │
        ▼
Execution
```

---

# Summary

The project structure is designed to keep trading logic modular, maintainable, and scalable.

Each package has a clearly defined responsibility and communicates with other packages through well-defined interfaces, enabling independent development and future expansion.