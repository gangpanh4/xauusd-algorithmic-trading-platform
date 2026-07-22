# Contributing Guide

> This document defines the development workflow, coding standards, and contribution process for the XAUUSD Algorithmic Trading Platform.

---

# Purpose

This guide ensures that every contribution maintains the quality, consistency, and architecture of the project.

Whether fixing bugs, adding new features, or improving documentation, contributors should follow the same workflow.

---

# Development Philosophy

The project values:

- Correctness over speed
- Maintainability over cleverness
- Readability over complexity
- Research before implementation
- Testing before merging

Every contribution should improve the project without introducing unnecessary complexity.

---

# Before You Start

Before implementing any feature:

- Understand the existing architecture.
- Read the relevant documentation.
- Identify the correct package.
- Avoid duplicate implementations.
- Reuse existing components whenever possible.

---

# Development Workflow

Every feature should follow this process:

```
Research
      ↓
Design
      ↓
Implementation
      ↓
Testing
      ↓
Code Review
      ↓
Merge
```

Do not skip steps.

---

# Branch Strategy

Create a dedicated branch for each feature or bug fix.

Example:

```
feature/bos-measurement
feature/liquidity-engine
bugfix/probability-calculation
docs/update-readme
```

Avoid making unrelated changes in the same branch.

---

# Commit Messages

Use clear and descriptive commit messages.

Good examples:

```
Add BOS measurement engine

Improve liquidity detector validation

Fix probability calculation bug

Refactor market structure engine

Update project documentation
```

Avoid vague messages such as:

```
Update

Fix

Changes

Work

Test
```

---

# Coding Standards

All code must follow the project's coding standards.

See:

- CODE_STYLE.md
- DESIGN_PRINCIPLES.md

Requirements include:

- Type hints
- Small functions
- Clear naming
- Single responsibility
- Proper documentation

---

# Testing Requirements

Every change should be tested before merging.

Run:

```bash
python -m pytest
```

Verify:

- All tests pass
- No regressions
- No new warnings
- Existing behavior remains unchanged unless intentionally modified

---

# Documentation

Documentation should be updated whenever:

- New modules are added
- Public APIs change
- Architecture changes
- New workflows are introduced

Documentation is considered part of the project, not an optional extra.

---

# Pull Request Checklist

Before opening a pull request, verify:

- Code follows the project style guide.
- Tests pass successfully.
- Documentation has been updated if necessary.
- No unused imports remain.
- No dead code has been introduced.
- No duplicated logic has been added.
- Public interfaces remain stable unless intentionally changed.

---

# Review Guidelines

Reviewers should evaluate:

- Correctness
- Readability
- Maintainability
- Test coverage
- Architectural consistency
- Compliance with project principles

Suggestions should improve the project while preserving its overall design.

---

# Adding New Features

When adding a new feature:

1. Determine the correct package.
2. Avoid breaking existing interfaces.
3. Reuse existing models where appropriate.
4. Add unit tests.
5. Update documentation.
6. Verify the complete test suite.

Features should integrate naturally into the existing architecture.

---

# Bug Fixes

Bug fixes should:

- Address the root cause.
- Avoid introducing side effects.
- Include regression tests when appropriate.
- Preserve public behavior unless a behavioral change is intended.

---

# Refactoring

Refactoring should improve:

- Readability
- Maintainability
- Structure

Refactoring must **not** change trading logic unless explicitly planned and reviewed.

---

# Architecture

Respect package responsibilities.

Examples:

- Market Structure analyzes markets.
- Feature Engineering extracts features.
- Probability Engine estimates probability.
- Signal Generator creates signals.
- Risk Manager creates trade plans.
- Trading Pipeline coordinates execution.

Avoid moving business logic into unrelated packages.

---

# Code Reviews

During review, ask:

- Is the code correct?
- Is it easy to understand?
- Does it follow the architecture?
- Is it properly tested?
- Can it be maintained easily?

---

# Project Principles

All contributions should support:

- Modular architecture
- Domain-driven design
- Deterministic processing
- Separation of concerns
- Extensibility
- Maintainability
- Production readiness

---

# Thank You

Thank you for contributing to the XAUUSD Algorithmic Trading Platform.

Every improvement, whether code, tests, documentation, or research, helps make the project more reliable, maintainable, and valuable for future development.