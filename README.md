# XAUUSD Algorithmic Trading Platform

> A professional, modular, research-driven algorithmic trading platform for XAUUSD built with Python.

---

## Overview

The XAUUSD Algorithmic Trading Platform is a professional trading framework designed for developing, testing, validating, and deploying systematic trading strategies.

Unlike traditional MetaTrader Expert Advisors, this platform separates trading intelligence from execution. Python performs all market analysis and trading decisions, while MetaTrader 5 is used solely as an execution adapter.

The platform emphasizes:

- Clean Architecture
- Domain-Driven Design (DDD)
- Modular Components
- Deterministic Trading Pipeline
- Research-Based Development
- Extensibility
- Maintainability
- Testability

---

# Goals

The primary objective is **consistent profitability through high-quality market analysis**, rather than creating another simple MT5 trading bot.

The platform is designed to support:

- Historical Backtesting
- Live Trading
- Market Structure Analysis
- Feature Engineering
- Probability Estimation
- Signal Generation
- Risk Management
- Performance Analytics
- Future AI Integration

---

# Key Features

## Market Structure

- Swing Detection
- Break of Structure (BOS)
- Change of Character (CHOCH)
- Liquidity Detection
- Market Structure Measurements

## Feature Engineering

- Market Structure Features
- Liquidity Features
- Confluence Features
- Statistical Features

## Probability Engine

- Feature Validation
- Probability Calculation
- Confidence Estimation

## Signal Generation

- Trading Opportunity Ranking
- Signal Filtering
- Trade Validation

## Risk Management

- Position Sizing
- Stop Loss
- Take Profit
- Risk-to-Reward Validation

## Trading Pipeline

- Deterministic Processing
- Modular Components
- Clean Data Flow

---

# High-Level Architecture

```

Historical Market Data
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

---

# Project Structure

```

core/
market_structure/
feature_engineering/
probability_engine/
signal_generator/
regime_detector/
risk_manager/
trading_pipeline/
backtesting/
research_analytics/

```

---

# Technology Stack

- Python 3.14
- MetaTrader 5
- Pytest
- Dataclasses
- Type Hints

---

# Design Philosophy

This platform follows several important engineering principles:

- Separation of Concerns
- Single Responsibility Principle
- Domain-Driven Design
- Immutable Result Objects
- Streaming Processing
- Modular Architecture
- Deterministic Execution

---

# Testing

The project uses **pytest** for automated testing.

Run all tests:

```bash
python -m pytest