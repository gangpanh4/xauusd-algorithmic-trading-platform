# Architecture

> This document describes the architecture of the XAUUSD Algorithmic Trading Platform, the responsibilities of each subsystem, and how data flows through the trading pipeline.

---

# Overview

The XAUUSD Algorithmic Trading Platform is built using a modular, domain-driven architecture where each package has a single responsibility.

The system separates market analysis, decision making, risk management, and execution into independent components. This design improves maintainability, testability, extensibility, and long-term scalability.

MetaTrader 5 is used only as the execution layer. All trading intelligence is implemented in Python.

---

# Design Goals

The architecture is designed around the following principles:

- Modular design
- Separation of concerns
- Single responsibility
- Deterministic execution
- Extensible components
- Testable business logic
- Maintainable codebase
- Production-ready architecture

---

# High-Level Architecture

```
                Historical / Live Market Data
                            │
                            ▼
                  Market Structure Engine
                            │
                            ▼
                 Feature Engineering Engine
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
                  Execution Adapter
                            │
                            ▼
                      MetaTrader 5
```

---

# Core Components

## Market Structure

Responsible for understanding the current market state.

Main responsibilities:

- Swing Detection
- Break of Structure (BOS)
- Change of Character (CHOCH)
- Liquidity Detection
- Market Structure Measurements

Output:

- Market structure events
- Market structure measurements
- Feature-ready information

---

## Feature Engineering

Transforms raw market structure information into numerical features suitable for probability estimation.

Examples:

- Structure confidence
- BOS strength
- Liquidity quality
- Trend strength
- Confluence features

Output:

- Feature vector

---

## Probability Engine

Estimates the probability that a trade setup is likely to succeed.

Responsibilities:

- Feature validation
- Probability calculation
- Confidence estimation
- Feature weighting

Output:

- Probability score
- Confidence score

---

## Signal Generator

Converts probabilities into trading opportunities.

Responsibilities:

- Signal generation
- Opportunity ranking
- Trade filtering
- Signal validation

Output:

- Trading signal

---

## Risk Manager

Creates a complete trade plan.

Responsibilities:

- Position sizing
- Stop-loss calculation
- Take-profit calculation
- Risk-to-reward validation

Output:

- Trade plan

---

## Trading Pipeline

Coordinates every subsystem.

Responsibilities:

- Execute components in order
- Pass data between modules
- Produce deterministic results
- Handle pipeline orchestration

The trading pipeline contains no market logic. It only coordinates the workflow.

---

## Execution Adapter

Responsible for broker communication.

Responsibilities:

- Convert trade plans into broker orders
- Submit orders
- Monitor execution
- Return execution results

The execution adapter is isolated from trading logic.

---

## MetaTrader 5

MetaTrader 5 is used exclusively for:

- Order execution
- Position management
- Account information
- Market data access

Trading decisions are never made inside MetaTrader.

---

# Data Flow

```
Market Data
      │
      ▼
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
Execution Adapter
      │
      ▼
MetaTrader 5
```

Each stage produces structured output consumed by the next stage.

---

# Package Responsibilities

| Package | Responsibility |
|----------|----------------|
| core.market_structure | Market analysis and structural interpretation |
| core.feature_engineering | Feature extraction |
| core.probability_engine | Probability estimation |
| core.signal_generator | Trade signal generation |
| core.regime_detector | Market regime classification |
| core.risk_manager | Risk and trade planning |
| core.trading_pipeline | Workflow orchestration |
| core.backtesting | Historical strategy evaluation |
| core.research_analytics | Research and performance analysis |

---

# Design Principles

The architecture follows these principles:

- Single Responsibility Principle
- Separation of Concerns
- Domain-Driven Design
- Composition over inheritance
- Immutable result models
- Typed interfaces
- Deterministic processing
- Modular subsystems

---

# Dependency Direction

Dependencies always flow in one direction.

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
        ↓
Execution
```

Lower layers never depend on higher layers.

This prevents circular dependencies and keeps the architecture maintainable.

---

# Future Expansion

The architecture is designed to support future additions without major restructuring.

Examples include:

- Portfolio management
- Multi-symbol trading
- Walk-forward testing
- Machine learning models
- Reinforcement learning research
- Cloud deployment
- Distributed backtesting

---

# Summary

The XAUUSD Algorithmic Trading Platform is designed as a modular, deterministic trading system where each subsystem has a clearly defined responsibility.

This separation enables easier testing, maintenance, research, and future expansion while keeping trading logic independent from execution infrastructure.