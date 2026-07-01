# XAUUSD Algorithmic Trading Platform
## Architecture Overview (Version 3.2)

---

# System Architecture

```text
                  ┌──────────────────────────┐
                  │      Market Data         │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │   Trading Pipeline       │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │    Pipeline Result       │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │  Live Trading Engine     │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │   MT5 Execution Layer    │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │      MetaTrader 5        │
                  └──────────────────────────┘
```

---

# Layer Responsibilities

## 1. Market Analysis Layer

Responsible for transforming raw market data into a market regime.

Modules:

- Indicators
- Feature Extraction
- Market Regime Detector

Output:

- `MarketRegime`

---

## 2. Signal Generation Layer

Responsible for generating BUY, SELL or HOLD signals.

Modules:

- Signal Generator

Output:

- `TradingSignal`

---

## 3. Risk Management Layer

Responsible for deciding whether a trade is allowed.

Modules:

- Risk Manager

Output:

- `TradePlan`

---

## 4. Trading Pipeline

Coordinates:

- Market Regime Detection
- Signal Generation
- Risk Management

Output:

- `PipelineResult`

---

## 5. Live Trading Engine

Coordinates the complete trading workflow.

Responsibilities:

- Receive completed market bars
- Run Trading Pipeline
- Decide whether execution is allowed
- Coordinate MT5 Execution
- Maintain runtime state

Output:

- `LiveTradingResult`

---

## 6. MT5 Execution Layer

Responsible for broker interaction only.

Modules:

- MT5 Connection
- Order Validation
- Price Levels
- Order Execution
- Position Management

Output:

- Executed MT5 trades

---

# Design Principles

- Single Responsibility Principle
- Layered Architecture
- Immutable Data Models
- Dependency Injection
- Broker-independent Strategy Layer
- Test-first Development

---

# Current Version Status

## ✅ Completed

- Market Regime Detection
- Signal Generation
- Risk Management
- Trading Pipeline
- Backtesting Foundation
- MT5 Execution Engine
- Live Trading Engine Foundation

---

## 🚧 In Progress

- Live Trading Integration
- MT5 Execution Integration

---

## 📅 Planned

- Automatic Demo Trading
- Position Monitoring
- Trailing Stop Management
- Continuous Candle Processing
- Production Deployment