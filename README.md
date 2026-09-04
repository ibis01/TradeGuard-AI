# 🛡️ TradeGuard AI

**A Risk-Governed AI Trading Agent for Binance Agent OS (Track B)**

> _"AI investigates. Deterministic controls verify. Humans govern. Binance executes. TradeGuard records."_

[![Tests](https://img.shields.io/badge/tests-118%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()

---

## 🎯 The Problem

Most AI trading agents are dangerous black boxes. If the LLM hallucinates a risk metric, ignores a stop-loss, or bypasses safety rules, the user loses capital. Autonomous execution without governance is a critical vulnerability.

## 💡 The Solution

TradeGuard AI is **not** an autonomous trading bot. It is a **governed AI agent** that demonstrates how AI can participate in trading decisions _without_ being trusted with unrestricted control over capital.

We separate concerns:

1. **AI Investigates & Proposes**: The agent analyzes market context and proposes a structured trade.
2. **Deterministic Rules Validate**: Hardcoded risk engines (2% risk cap, exposure limits) independently evaluate the proposal. The AI _cannot_ override this.
3. **Humans Authorize**: Explicit, cryptographically-bound human approval is required.
4. **Binance Executes**: Only validated, approved intents reach the Binance execution adapter.

---

## 🏗️ Track B Architecture

TradeGuard integrates with the Binance ecosystem through a strict, isolated adapter boundary and MCP tooling.

```text
                    USER OBJECTIVE
                          │
                          ▼
                 🤖 AGENT / MCP LAYER
          (Analyzes market data, proposes trade)
                          │
                          ▼
                  TRADE PROPOSAL
                          │
                          ▼
              🔒 DETERMINISTIC RISK ENGINE
                 /                    \
              PASS                    REJECT
                │                       │
                ▼                       ▼
          ⚖️ GOVERNANCE              AUDIT LOG
                │
                ▼
          👤 HUMAN APPROVAL
     (Cryptographic token, hash-bound)
                │
                ▼
       🔐 HASH / INTEGRITY CHECK
                │
                ▼
        🔗 BINANCE EXECUTION ADAPTER
      (Paper / Testnet / Mainnet isolation)
                │
                ▼
              AUDIT LOG
```
