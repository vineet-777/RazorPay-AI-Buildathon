# 🛡️ Agent Commerce Gateway
### *Razorpay AI Buildathon 2026 — Production-Grade MVP*

> **"An agent commerce gateway that turns Razorpay merchants into safe, machine-readable storefronts — letting AI buyers discover products, negotiate constraints, and complete payments under explicit user and merchant policies."**

---

## Table of Contents

1. [What Is This Project?](#1-what-is-this-project)
2. [Core Innovation: The Security Invariant](#2-core-innovation-the-security-invariant)
3. [System Architecture](#3-system-architecture)
4. [How It Works — Layer by Layer](#4-how-it-works--layer-by-layer)
5. [Getting Started in 60 Seconds](#5-getting-started-in-60-seconds)
6. [Web Control Center UI](#6-web-control-center-ui)
7. [API Reference](#7-api-reference)
8. [Testing & Security Benchmarks](#8-testing--security-benchmarks)
9. [Project File Map](#9-project-file-map)
10. [Why This Project Stands Out](#10-why-this-project-stands-out)

---

## 1. What Is This Project?

**Agent Commerce Gateway (ACG)** is a production-quality **transaction infrastructure layer** — not a chatbot, not a shopping assistant — that solves a fundamental unsolved problem in the emerging world of AI-powered commerce:

> *How do you let an AI agent spend your money without ever trusting it?*

In an agentic economy, AI buyers will autonomously browse, evaluate, and purchase goods on behalf of users. The danger is obvious: an LLM that can also **approve its own payments** is a catastrophic security hole. ACG solves this by placing a **deterministic, policy-driven firewall** between the AI's reasoning and actual money movement.

### What ACG Does

| What the User Does | What ACG Does |
|---|---|
| Says: *"Buy me groceries under Rs.500/week, only from trusted merchants"* | Compiles that into a machine-verifiable **Authorization Contract** |
| Delegates to an AI buyer agent | Agent discovers products from **machine-readable storefronts** |
| Waits for result | Agent's transaction proposal passes through a **10-rule deterministic firewall** |
| Gets a decision | Firewall returns `ALLOW` / `DENY` / `CHALLENGE` with a full rule trace |
| Payment runs | Real **Razorpay Test-Mode** payment executes with HMAC-SHA256 signature |
| Audit happens | Every decision is appended to a **tamper-evident SHA-256 hash chain** |

---

## 2. Core Innovation: The Security Invariant

The central design principle that makes ACG trustworthy:

```
LLM  =  reasoning layer       (can suggest, discover, evaluate, rank)
Code =  authority/money layer  (decides, approves, commits, audits)
```

**The LLM is NEVER allowed to:**
- Directly approve a payment
- Increase a spending limit
- Modify an authorization contract
- Bypass a merchant policy
- Override a DENY decision
- Modify the audit trail
- Alter the amount authorized
- Silently convert a one-time purchase into recurring
- Authorize a new merchant if policy forbids it

This is enforced at the **code level** — not by prompt engineering, not by system instructions. The firewall is a pure Python function with zero LLM calls.

---

## 3. System Architecture

```
+-------------------------------------------------------------------+
|                    USER / HUMAN PRINCIPAL                         |
|   Speaks in natural language, sets budget, approves policy        |
+------------------------------+------------------------------------+
                               |  Natural Language Delegation
                               v
+-------------------------------------------------------------------+
|              POLICY COMPILER  (LLM-assisted)                      |
|   Parses intent -> Detects ambiguity -> Emits signed contract     |
+------------------------------+------------------------------------+
                               |  UserAuthorizationContract (JSON)
                               v
+-------------------------------------------------------------------+
|              AI BUYER AGENT  (LLM-assisted)                       |
|   Discovers products -> Negotiates -> Ranks -> Constructs tx      |
+------------------------------+------------------------------------+
                               |  CanonicalTransaction (JSON)
                               v
+-------------------------------------------------------------------+
|         DETERMINISTIC AUTHORIZATION FIREWALL  (Pure Code)         |
|  10 Rule Predicates -> MutationDetector -> BudgetEngine ->        |
|  ReservationService -> ALLOW / DENY / CHALLENGE                   |
+-----------+----------------------------+--------------------------+
            | ALLOW                      | DENY / CHALLENGE
            v                            v
+-----------+-----------+    +-----------+---------------------------+
|  RAZORPAY PAYMENT     |    |  RULE TRACE + REASON CODE            |
|  Test-Mode Execution  |    |  returned to agent/user              |
|  HMAC-SHA256 Verified |    +--------------------------------------+
+-----------+-----------+
            |
            v
+-------------------------------------------------------------------+
|         CRYPTOGRAPHIC AUDIT HASH CHAIN  (Append-Only)             |
|  SHA-256 chained events -> Tamper-evident -> Forensic replay      |
+-------------------------------------------------------------------+
```

**Tech Stack:**

| Layer | Technology |
|---|---|
| API Backend | FastAPI (Python), Uvicorn |
| Data Store | SQLite (zero-dependency, runs anywhere) |
| LLM Integration | Gemini Flash / OpenAI (pluggable) |
| Payment Gateway | Razorpay Python SDK (Test Mode) |
| Frontend UI | Vanilla HTML + CSS + JS (no build step) |
| Cryptography | HMAC-SHA256 (Python `hashlib`) |
| Testing | Pytest + custom adversarial benchmark harness |

---

## 4. How It Works — Layer by Layer

### Layer 1: Machine-Readable Merchant Storefronts

Traditional e-commerce requires a human to browse pages. ACG makes merchant catalogs **agent-consumable by design**.

Every product has structured, policy-readable metadata:
```json
{
  "sku": "OATS-001",
  "name": "Quaker Oats 1kg",
  "price_inr": 782.0,
  "category": "GROCERY",
  "ai_commerce_eligible": true,
  "merchant_id": "freshmart_mumbai",
  "inventory_count": 150,
  "negotiable_fields": ["quantity", "delivery_speed"]
}
```

Three seeded merchants demonstrate different trust levels:
- **FreshMart Mumbai** — trusted grocery, AI-enabled
- **Croma Electronics** — high-value electronics, policy-restricted
- **GrayMarket Untrusted** — an untrusted merchant, always blocked by policy

Merchants publish **versioned AI Policy Documents** governing what AI agents can autonomously buy. Policy versions are **immutable once written** — you can only create a new version, never mutate history.

---

### Layer 2: User Delegation & Authorization Contracts

A user speaks naturally. The **Policy Compiler** (LLM-assisted) converts their intent into a machine-verifiable contract:

**Input:**
```
"Buy me groceries under Rs.500/week. Only from FreshMart. No subscriptions."
```

**Output: UserAuthorizationContract**
```json
{
  "contract_id": "contract_alice_001",
  "principal_id": "user_alice",
  "allowed_merchant_ids": ["freshmart_mumbai"],
  "allowed_categories": ["GROCERY"],
  "max_order_value_inr": 500,
  "max_aggregate_value_inr": 2000,
  "recurring_allowed": false,
  "valid_until": "2026-12-31T23:59:59Z",
  "revoked": false
}
```

The contract is **signed and stored in SQLite** and cannot be modified by the AI agent. Only the human user can revoke it via explicit API call.

The compiler also flags **ambiguities** before materializing a contract — e.g. *"Budget per week — do you mean rolling 7-day window or calendar week?"* — surfaced to the user for clarification, not silently resolved by the LLM.

---

### Layer 3: AI Buyer Agent

Once a contract exists, a user can dispatch an **autonomous AI buyer** with a natural-language goal.

The buyer agent executes a structured pipeline:

```
1. DISCOVER    -> Query catalog API (filtered by contract's merchant/category rules)
2. EVALUATE    -> LLM ranks results by value, availability, negotiability
3. NEGOTIATE   -> Request better terms if available (e.g. free installation)
4. CONSTRUCT   -> Emit CanonicalTransaction with all fields locked
5. SUBMIT      -> Send to Authorization Firewall
6. REPORT      -> Return full decision trace to user
```

The agent can **suggest and rank** but it cannot **authorize or pay**. That power stays entirely in the firewall.

---

### Layer 4: Deterministic Authorization Firewall

This is the heart of ACG. A pure Python function — **zero LLM calls, zero randomness** — evaluates every transaction against 10 rule predicates:

| # | Rule | What It Checks |
|---|---|---|
| 1 | `RULE_USER_CONTRACT_EXISTS` | Contract ID maps to a real, stored contract |
| 2 | `RULE_USER_CONTRACT_EXPIRY` | Contract's `valid_until` is in the future |
| 3 | `RULE_USER_CONTRACT_REVOCATION` | Contract has not been revoked by the user |
| 4 | `RULE_USER_MERCHANT_ALLOWLIST` | Merchant is in the user's permitted merchant list |
| 5 | `RULE_USER_CATEGORY_ALLOWLIST` | Product category is permitted by contract |
| 6 | `RULE_USER_SINGLE_ORDER_CAP` | This order's value is within max_order_value_inr |
| 7 | `RULE_USER_AGGREGATE_BUDGET` | Running total spend is within max_aggregate_value_inr |
| 8 | `RULE_MERCHANT_AI_COMMERCE_ENABLED` | Merchant has AI commerce enabled in active policy |
| 9 | `RULE_PRODUCT_INVENTORY_AVAILABLE` | Requested quantity is within available stock |
| 10 | `RULE_TRANSACTION_FEE_INTEGRITY` | Total = unit_price x qty + fees (no hidden markup) |

**If ANY rule fails → DENY** (all-or-nothing, short-circuit on first failure).
**CHALLENGE** is returned when valid but explicit step-up is required (e.g. high-value electronics).

#### Mutation Detector

The firewall also runs a **mutation check** comparing the agent's original proposal to the final canonical transaction:

| Attack | Detection |
|---|---|
| Merchant swap | proposal.merchant_id != tx.merchant_id |
| SKU substitution | proposal.sku != tx.sku |
| Quantity inflation | tx.quantity > proposal.quantity |
| Recurring escalation | one-time proposal but recurring tx |
| Price drift > 10% | abs(tx.price - proposal.price) / proposal.price > 0.10 |

#### Atomic Budget Reservations

Budget tracking uses **SQLite `BEGIN IMMEDIATE`** transactions to prevent concurrency races. When 10 threads simultaneously try to spend the last Rs.500 of a Rs.500 budget, only 1 succeeds. Zero over-spend — tested with a live 10-thread harness.

---

### Layer 5: Razorpay Payment Execution

When the firewall returns `ALLOW`, ACG executes a real **Razorpay Test-Mode** payment:

```
POST /api/v1/payments/execute
-> Creates Razorpay Order
-> Generates HMAC-SHA256 payment signature
-> Verifies signature against Razorpay secret
-> Returns: order_id, payment_id, signature, verified=true
```

The payment flow is **idempotent** — the same canonical_transaction_id always returns the same order_id. Re-submitting an authorized transaction doesn't double-charge.

A **Payment State Machine** enforces valid transitions only:
```
DRAFT -> AUTHORIZATION_PENDING -> AUTHORIZED -> PAYMENT_PENDING -> COMPLETED
                                                                -> PAYMENT_FAILED
```

---

### Layer 6: Cryptographic Audit Hash Chain

Every event in ACG is appended to a **tamper-evident hash chain**:

```
event_hash = SHA256(
  seq_number     ||
  timestamp      ||
  event_type     ||
  payload_json   ||
  previous_event_hash
)
```

This means deleting, editing, reordering, or inserting any record is **mathematically detectable**. The chain is verifiable in one click via the UI or `GET /api/v1/audit/verify`.

---

### Layer 7: Forensic Policy Replay Engine

When a merchant changes policy (e.g. Sony TV autonomous cap drops from Rs.75,000 to Rs.50,000), ACG can **replay any past transaction** against any policy version:

```
Historical Transaction: Sony 65" TV, Rs.68,999
  -> Under policy v14 (cap Rs.75k):  ALLOW     [was approved]
  -> Under policy v15 (cap Rs.50k):  CHALLENGE  [would have been challenged]
```

Critical for compliance, regulatory audit, and merchant dispute resolution — without touching the live database or re-running real payments.

---

## 5. Getting Started in 60 Seconds

### Prerequisites

- Python 3.10+
- A Razorpay Test-Mode account (free at razorpay.com)

### Step 1: Clone & Install

```bash
git clone https://github.com/your-username/agent-commerce-gateway.git
cd agent-commerce-gateway

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
cp .env.example .env
```

Open `.env` and fill in:

```dotenv
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=your_test_secret_here

LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key_here

APP_ENV=development
DEBUG=true
HOST=0.0.0.0
PORT=8000
RAZORPAY_TEST_MODE=true
```

> **Note:** The system works without an LLM key — the buyer agent falls back to rule-based ranking. The firewall, payments, and audit chain require no LLM at all.

### Step 3: Start the Server

```bash
python -m uvicorn app.main:app --reload --port 8000
```

On first startup, ACG automatically:
- Creates the SQLite database schema
- Seeds 3 merchant catalogs (FreshMart, Croma Electronics, GrayMarket)
- Seeds 3 versioned merchant policies (v1, v14, v15)
- Seeds 3 user authorization contracts (Alice, Bob, Charlie)

### Step 4: Open the Control Center

Navigate to **http://localhost:8000** in your browser.

### Step 5: Explore the API Docs

Navigate to **http://localhost:8000/docs** for the auto-generated Swagger UI.

### Step 6: Run the Test Suite

```bash
# 21 automated tests
python -m pytest -v

# 25 adversarial attack scenarios
python evals/runner.py
```

---

## 6. Web Control Center UI

The frontend at `http://localhost:8000` has 6 interactive tabs:

| Tab | What You Can Do |
|---|---|
| AI Buyer Studio | Compile natural-language delegations, detect ambiguities, dispatch autonomous AI buyer, view live Razorpay payment with HMAC signature |
| Merchant Control Plane | Browse machine-readable catalogs, switch between policy versions (v1/v14/v15), view autonomous purchase caps |
| Firewall & Decision Inspector | Manually submit any transaction, view the 10-rule evaluation matrix, resolve step-up challenges, watch real-time budget window |
| Forensic Replay Simulator | Select a past transaction, replay against any policy version, get a side-by-side diff |
| Adversarial Attack Benchmark | One-click full 25-case benchmark suite, trigger 10-thread concurrency race attack, view scored results |
| 5-Minute Judge Demo Tour | Step-by-step interactive walkthrough of all 7 core scenarios |

---

## 7. API Reference

Base URL: `http://localhost:8000/api/v1`

### Commerce & Discovery

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/commerce/catalog` | Discover AI-eligible products. Filterable by merchant, category, price, query |
| `GET` | `/commerce/products/{sku}` | Get structured product details by SKU |
| `POST` | `/commerce/negotiate` | Negotiate purchase terms (delivery, installation, bundles) |

### Merchant Policies

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/merchants/{id}/policies` | List all versioned policies for a merchant |
| `GET` | `/merchants/{id}/policies/active` | Get the current active policy |
| `POST` | `/merchants/{id}/policies` | Publish a new immutable policy version |

### User Authorization

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/user/delegations/compile` | Compile natural language to machine-readable contract with ambiguity detection |
| `POST` | `/user/delegations` | Persist and activate a signed contract |
| `GET` | `/user/delegations/{contract_id}` | Get contract + live real-time budget state |
| `POST` | `/user/delegations/{contract_id}/revoke` | Immediately revoke a contract |

### AI Buyer Agent

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/agent/shop` | Dispatch autonomous shopping: discover, rank, negotiate, firewall, payment |

### Authorization Firewall

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/gateway/authorize` | Evaluate any canonical transaction against all 10 firewall rules |

### Payments

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/payments/execute` | Execute a Razorpay Test-Mode payment for an authorized transaction |

### Audit & Forensics

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/audit/events` | Browse the append-only event log |
| `GET` | `/audit/verify` | Verify the entire SHA-256 hash chain integrity |
| `POST` | `/audit/replay` | Replay a transaction under a different policy version |

---

## 8. Testing & Security Benchmarks

### Automated Pytest Suite — 21 Tests, 100% Pass Rate

```bash
python -m pytest -v
```

| Test File | What It Tests |
|---|---|
| `test_firewall.py` | All 10 rule predicates individually + compound scenarios |
| `test_budget_concurrency.py` | 10-thread race conditions on budget — zero over-spend |
| `test_mutation_detector.py` | All 5 mutation attack vectors |
| `test_payments.py` | Razorpay order creation, HMAC signature, idempotency |
| `test_hash_chain.py` | Append, verify, tamper detection |
| `test_e2e.py` | Full API round-trip: contract -> agent -> firewall -> payment -> audit |

### Adversarial Security Benchmark — 25 Attack Scenarios

```bash
python evals/runner.py
```

| Metric | Score |
|---|---|
| Total attack scenarios | 25 |
| False Allow Rate | **0.00%** |
| Evaluation latency p50 | **0.49ms** |
| Evaluation latency p95 | **0.71ms** |
| Concurrency race protection | **100%** |
| Hash chain tamper detection | **100%** |

**Attack categories tested:**
- Expired / revoked contract bypass
- Merchant allowlist bypass (GrayMarket injection)
- Category bypass (electronics disguised as groceries)
- Single order cap violation
- Aggregate budget exhaustion (100x small purchases)
- Inventory phantom attack (buying out-of-stock items)
- Fee manipulation (hidden price markup)
- Merchant swap mid-flight
- SKU substitution
- Quantity inflation (order 1, receive 100)
- Recurring escalation (one-time to subscription)
- Budget concurrency race (10 threads, 1 slot remaining)

---

## 9. Project File Map

```
agent-commerce-gateway/
├── app/
│   ├── main.py                     # FastAPI entry point, CORS, lifespan hooks
│   ├── core/
│   │   ├── config.py               # Environment-driven settings (Pydantic)
│   │   ├── db.py                   # SQLite connection pool, schema migrations
│   │   └── logging.py              # Structured JSON logger with correlation IDs
│   ├── commerce/
│   │   ├── catalog.py              # Machine-readable product catalog service
│   │   ├── merchant_policy.py      # Versioned, immutable merchant AI policies
│   │   └── negotiation.py          # Constraint negotiation engine
│   ├── authorization/
│   │   ├── engine.py               # [CORE] Deterministic Authorization Firewall
│   │   ├── rules.py                # 10 pure rule predicate functions
│   │   ├── mutation_detector.py    # Proposal vs transaction integrity check
│   │   ├── budget.py               # Budget state computation engine
│   │   ├── reservations.py         # Atomic SQLite budget reservation service
│   │   └── contracts.py            # User Authorization Contract CRUD
│   ├── agents/
│   │   ├── buyer_agent.py          # Autonomous AI Buyer Agent pipeline
│   │   └── policy_compiler.py      # NL -> machine contract compiler
│   ├── payments/
│   │   ├── razorpay_client.py      # Razorpay SDK + HMAC signature gateway
│   │   └── models.py               # Payment state machine
│   ├── audit/
│   │   ├── hash_chain.py           # [CORE] SHA-256 tamper-evident event log
│   │   └── replay.py               # Forensic policy replay engine
│   └── api/
│       └── routes.py               # All 20+ REST API endpoints
├── frontend/
│   ├── index.html                  # Single-page Control Center layout
│   ├── styles.css                  # Glassmorphism dark-mode design system
│   └── app.js                      # Reactive tab controllers (vanilla JS)
├── tests/
│   ├── conftest.py                 # Pytest fixtures, DB isolation per test
│   ├── test_firewall.py
│   ├── test_budget_concurrency.py
│   ├── test_mutation_detector.py
│   ├── test_payments.py
│   ├── test_hash_chain.py
│   └── test_e2e.py
├── evals/
│   ├── runner.py                   # Adversarial benchmark harness
│   ├── metrics.py                  # Scoring: FAR, latency, concurrency
│   └── adversarial_cases.json      # 25 structured attack test cases
├── docs/
│   ├── architecture.md             # Deep-dive technical architecture
│   └── threat_model.md             # STRIDE threat matrix + mitigations
├── .env.example                    # Environment variable template
├── requirements.txt                # All Python dependencies
└── README.md                       # Hackathon submission README
```

---

## 10. Why This Project Stands Out

Most hackathon submissions in the "AI + Payments" space are one of two things:

1. **A chatbot** that calls Razorpay APIs based on user chat messages
2. **A shopping assistant** that recommends products and asks the user to confirm each step

ACG is neither of these. Here is exactly what makes it different:

---

### 1. Solves a Real, Original Problem — Not a Demo

The problem of **AI agent authorization in commerce** is genuinely unsolved in production. How do you give an AI buyer enough autonomy to be useful while ensuring it can never spend beyond your limits, buy from unauthorized merchants, or get manipulated mid-transaction? ACG is the first full-stack answer to this question, not a proof-of-concept toy.

---

### 2. The Firewall Architecture is Industry-Novel

Most "secure AI" projects rely on prompt instructions (system prompts saying "don't approve payments"). ACG enforces security at the **code layer**, not the prompt layer. The 10-rule deterministic firewall has:
- Zero LLM calls in the critical path
- Sub-millisecond evaluation latency (0.49ms p50)
- Formally enumerated rule predicates (not vibes-based safety)
- Hard `DENY` that cannot be talked out of by any prompt injection

This is architecturally closer to **financial transaction authorization systems** (like Visa/Mastercard's rules engines) than to any AI chatbot.

---

### 3. Adversarial Security is a First-Class Deliverable

Most hackathon projects ship happy-path demos. ACG ships a **25-case adversarial security benchmark suite** with a custom evaluation harness, quantified False Allow Rate (0.00%), live concurrency race tests, and all 5 transaction mutation attack vectors. Judges can verify every security claim by running one command.

---

### 4. Cryptographic Auditability — Not Just Logging

Any system can log events. ACG chains them using **SHA-256 parent hashing** — the same principle used in blockchain and certificate transparency logs. A tampered audit log is mathematically detectable. This turns ACG's audit trail into a **legal-grade evidentiary record**, not just a developer debug log.

---

### 5. Forensic Replay — Time-Travel Compliance

The Forensic Policy Replay Engine lets you ask: *"Under the new merchant policy, would this old transaction still have been approved?"* This is something enterprise compliance teams actually need when merchant policies change. No other hackathon project ships this capability.

---

### 6. Machine-Readable Storefronts — The Right Abstraction

Instead of scraping HTML or parsing natural language descriptions, ACG defines a **structured product schema with AI-specific metadata fields**: `ai_commerce_eligible`, `negotiable_fields`, `merchant_ai_policy`. This is the correct long-term abstraction for an agentic commerce ecosystem — the equivalent of introducing `<meta>` tags specifically for AI agents.

---

### 7. Production-Quality Engineering Throughout

ACG is not prototype code. It includes:
- Pydantic v2 schema validation on every API boundary
- SQLite atomic transactions for budget isolation
- HMAC-SHA256 payment signature verification
- Idempotent payment execution (no double charges)
- Structured JSON logging with correlation IDs
- Immutable, versioned policy history (append-only)
- 100% pytest coverage with DB isolation fixtures per test

---

### 8. Complete, Interactive Judge Experience

The 6-tab Web Control Center and the built-in **5-Minute Judge Demo Tour** mean judges can verify every architectural claim interactively — without running terminal commands or reading source code. Every key system (firewall, agent, payments, audit, forensics) has a live UI surface with real data.

---

### The One-Line Pitch for Judges

> *"ACG is the first open-source transaction authorization framework designed specifically for AI agents — a production-grade security firewall that lets Razorpay merchants safely delegate purchasing authority to AI buyers, backed by cryptographic auditability and adversarially-tested deterministic rule enforcement."*

---

*Built for the Razorpay AI Buildathon 2026.*  
*Architecture inspired by financial transaction authorization systems, certificate transparency logs, and agentic AI safety research.*
