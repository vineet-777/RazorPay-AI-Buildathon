# Razorpay AI Buildathon 2026 — Agent Commerce Gateway

## Project Concept

**Agent Commerce Gateway**

> **An agent commerce gateway that turns Razorpay merchants into safe, machine-readable storefronts—letting AI buyers discover products, negotiate constraints, and complete payments under explicit user and merchant policies.**

### Core idea

AI agents are increasingly capable of deciding what to buy and acting on a user's behalf. The missing infrastructure is not another shopping chatbot; it is a trustworthy transaction layer that lets an autonomous AI buyer interact with a merchant and complete a payment while remaining within clearly delegated authority.

The system combines:

- AI-powered buyer intent and product reasoning
- A machine-readable merchant catalog
- Merchant-side AI-commerce policies
- User-side delegated payment authority
- Deterministic transaction authorization
- Budget reservation and aggregate-spend enforcement
- Razorpay test-mode payment execution
- Tamper-evident decision traces
- Policy/version replay
- Adversarial evaluation of autonomous payment behavior

The strongest positioning is:

> **We are not building another AI shopping chatbot. We are building the transaction layer that lets AI buyers safely buy from merchants.**

---

# 1. Why This Project

Razorpay's 2026 Track 01 — AI Growth & Agentic Commerce — is centered on building an AI system that either:

1. grows merchant revenue, or
2. makes a merchant transactable by an AI buyer end to end.

The track also emphasizes that money actions should be:

- explainable
- bounded
- gated
- auditable
- capable of handling failure gracefully

This creates a strong intersection for the project:

```text
AI Buyer
   ↓
Merchant Discovery
   ↓
Product / Offer Evaluation
   ↓
User Authority
   ↓
Merchant Policy
   ↓
Deterministic Authorization
   ↓
Razorpay Test-Mode Payment
   ↓
Decision Trace / Replay
```

The important strategic change from the original idea is that **the payment transaction is now the center of the product**. The policy engine is the safety layer enabling autonomous commerce, not the entire product by itself.

---

# 2. The Problem Statement

## Human commerce today

A human buyer can naturally inspect:

- product
- price
- seller
- availability
- variants
- shipping
- discounts
- checkout
- payment

An AI buyer needs machine-readable equivalents and a trustworthy transaction path.

The AI needs to answer:

> What can I buy from this merchant, under what constraints, and can I actually transact?

At the same time, the merchant needs to answer:

> What is an AI agent allowed to discover, purchase, modify, or negotiate on my behalf?

The user needs to answer:

> What is my AI agent allowed to spend, where, on what, and under what conditions?

The Agent Commerce Gateway resolves all three.

---

# 3. Three-Sided Authorization Model

The system should explicitly separate three policy domains.

## 3.1 User → Agent Authorization

The user delegates authority to the AI buyer.

Example:

> You can spend up to ₹5,000 on groceries this week. Use my approved merchants. Ask me before buying a subscription or changing the delivery location.

This becomes a machine-checkable authorization contract.

## 3.2 Merchant → AI Buyer Policy

The merchant controls how autonomous AI buyers interact with the store.

Example:

```json
{
  "merchant_id": "merchant_a",
  "ai_sales_enabled": true,
  "max_ai_order_value_inr": 3000,
  "allowed_categories": ["groceries", "personal_care"],
  "allow_quantity_changes": true,
  "allow_substitutions": false,
  "allow_discounts": true,
  "require_step_up_for": [
    "new_customer",
    "high_value_order",
    "product_substitution"
  ]
}
```

## 3.3 Transaction Facts

The final authorization decision is based on the actual executable transaction, not merely what the LLM claims it wants to do.

Canonical transaction facts should include:

- merchant ID
- product/SKU
- category
- quantity
- item price
- discount
- tax
- shipping/service fees
- total amount
- currency
- delivery pincode/address class
- recurring-payment flag
- payment method
- transaction timestamp
- authorization contract version
- merchant policy version

The payment decision becomes:

```text
USER AUTHORITY
      AND
MERCHANT POLICY
      AND
TRANSACTION FACTS
      AND
SYSTEM/RISK RULES
          ↓
ALLOW / CHALLENGE / DENY
```

---

# 4. Product Experience

Imagine a user tells their AI:

> “Find me a 65-inch 4K TV under ₹70,000. Prefer Sony or LG. Deliver to Bangalore this week. You can spend up to ₹75,000 if there's free installation.”

## Step 1 — AI Buyer understands the request

The Buyer Agent turns the natural-language goal into a structured shopping task.

```json
{
  "category": "television",
  "screen_size_inches": 65,
  "resolution": "4K",
  "preferred_brands": ["Sony", "LG"],
  "target_budget_inr": 70000,
  "hard_ceiling_inr": 75000,
  "delivery_city": "Bangalore",
  "delivery_deadline": "2026-08-30",
  "installation_required": true
}
```

## Step 2 — Agent Commerce API discovers merchant offers

The merchant exposes an AI-readable catalog.

```json
{
  "product": "Sony Bravia 65X80L",
  "sku": "SONY-65X80L",
  "price_inr": 68999,
  "inventory": 14,
  "delivery_estimate": "2-4 days",
  "installation": true,
  "merchant": "merchant_a"
}
```

## Step 3 — AI evaluates the offer

The agent determines whether the product satisfies the user's shopping objective.

## Step 4 — Authorization

Before money movement, the deterministic authorization firewall checks:

- user delegation
- merchant policy
- product eligibility
- current price
- current inventory
- quantity
- destination
- budget
- expiration
- recurring status
- transaction mutations

## Step 5 — Payment

If authorized, the system triggers the Razorpay test-mode payment flow.

## Step 6 — Decision trace

The system records why the payment was allowed.

Example:

```text
Decision #8F21A

User request:
65-inch 4K TV under ₹70,000

Agent proposal:
Sony Bravia 65X80L

Final transaction:
₹68,999

Authorization:
ALLOW

Policies matched:
P-17
P-22
P-31

User ceiling:
₹75,000

Merchant AI limit:
₹75,000

Policy version:
v14

Payment:
SUCCESS
```

---

# 5. System Architecture

```text
                         USER
                          │
                Natural-language delegation
                          │
                          ▼
                  ┌──────────────┐
                  │ BUYER AGENT  │
                  └──────┬───────┘
                         │
                         ▼
                AGENT COMMERCE API
                         │
                ┌────────┴────────┐
                │                 │
                ▼                 ▼
        Merchant Catalog     Merchant Policy
                │                 │
                └────────┬────────┘
                         ▼
                TRANSACTION BUILDER
                         │
                         ▼
              AUTHORIZATION FIREWALL
               │       │       │
               │       │       └── Risk Rules
               │       └────────── Budget / Reservation
               └────────────────── User Authority
                         │
                 ALLOW / CHALLENGE / DENY
                         │
                         ▼
                  RAZORPAY TEST MODE
                         │
                         ▼
                      PAYMENT
                         │
                         ▼
                 DECISION TRACE / LOG
                         │
                         ▼
                   REPLAY CONSOLE
```

---

# 6. Major Components

## 6.1 Buyer Agent

Responsibilities:

- understand user shopping goals
- search merchant catalogs
- compare products/offers
- reason about constraints
- form a proposed transaction
- ask for step-up approval when required

The Buyer Agent is **not allowed to approve payments**.

---

## 6.2 Merchant Catalog Service

Provides structured data suitable for agents.

Possible fields:

```json
{
  "merchant_id": "merchant_a",
  "products": [
    {
      "sku": "SKU-123",
      "title": "Example Product",
      "category": "groceries",
      "price_inr": 1299,
      "currency": "INR",
      "inventory": 42,
      "delivery_estimate": "2-3 days",
      "substitution_allowed": false
    }
  ]
}
```

The gateway should provide a consistent schema even if the underlying merchant data source is different.

---

## 6.3 Merchant Policy Engine

Defines merchant-side AI commerce rules.

Examples:

- maximum autonomous order value
- allowed product categories
- allowed regions
- AI-discount rules
- substitution rules
- quantity modification rules
- return/refund restrictions
- subscription restrictions
- approval thresholds

---

## 6.4 User Authorization Contract

Example:

```json
{
  "principal_id": "user_238",
  "agent_id": "buyer_agent_01",
  "scope": {
    "merchants_allowlist": [
      "merchant_a",
      "merchant_b"
    ],
    "categories_allowlist": [
      "groceries",
      "personal_care"
    ],
    "max_order_value_inr": 1500,
    "max_weekly_value_inr": 5000,
    "recurring_purchase_allowed": false,
    "delivery_pincodes": [
      "560001"
    ]
  },
  "approval_policy": {
    "require_step_up_if": [
      "new_merchant",
      "price_increase_over_10_percent",
      "substituted_sku",
      "ambiguous_intent"
    ]
  },
  "issued_at": "2026-08-20T10:00:00Z",
  "expires_at": "2026-08-27T10:00:00Z",
  "revocation_version": 7
}
```

### Important design rule

The LLM may **propose** this contract, but should not silently establish authority.

Recommended flow:

```text
Natural Language Delegation
          ↓
LLM Policy Parser
          ↓
Schema Validation
          ↓
Semantic Validation
          ↓
Ambiguity Detection
          ↓
User Confirmation when necessary
          ↓
Signed / Versioned Contract
          ↓
Deterministic Enforcement
```

The principle is:

> **The LLM proposes policy. The user authorizes policy. Deterministic code enforces policy.**

---

# 7. Authorization Firewall

The authorization firewall is the central safety component.

It receives a canonical transaction object.

Example:

```json
{
  "decision_id": "D-10291",
  "user_id": "user_238",
  "agent_id": "buyer_agent_01",
  "merchant_id": "merchant_a",
  "sku": "SKU-123",
  "category": "groceries",
  "quantity": 2,
  "subtotal_inr": 1200,
  "shipping_inr": 50,
  "tax_inr": 96,
  "discount_inr": 100,
  "total_inr": 1246,
  "destination_pincode": "560001",
  "recurring": false,
  "timestamp": "2026-08-26T11:30:00Z"
}
```

The engine evaluates explicit predicates.

Possible output:

```json
{
  "decision": "ALLOW",
  "matched_rules": [
    "merchant_allowlist",
    "category_allowlist",
    "order_value_limit",
    "destination_allowlist",
    "recurring_block_not_triggered"
  ],
  "policy_version": "v14",
  "reason_code": "ALL_CONSTRAINTS_SATISFIED"
}
```

---

# 8. ALLOW / CHALLENGE / DENY Model

## ALLOW

The transaction is fully inside the delegated authority and merchant policy.

## CHALLENGE

The transaction may be legitimate but requires step-up approval.

Examples:

- new merchant
- changed SKU
- moderate price drift
- ambiguous user intent
- unusual delivery destination

## DENY

The transaction clearly violates hard constraints.

Examples:

- amount above hard ceiling
- expired delegation
- blocked merchant
- blocked category
- recurring payment when disabled
- invalid destination
- aggregate budget exceeded
- policy explicitly forbids the action

---

# 9. Budget Reservation and Concurrency

This should be one of the more technically impressive parts of the project.

A simple amount check is not enough.

Suppose:

```text
User delegated budget = ₹10,000

Transaction A = ₹7,000
Transaction B = ₹5,000
```

If both transactions read the balance before either writes its reservation, both could incorrectly succeed.

Instead:

```text
₹10,000 total budget
       │
       ├── Reserve ₹7,000
       │
       └── Remaining = ₹3,000
                         │
                         └── ₹5,000 request → DENY
```

Recommended lifecycle:

```text
AUTHORIZATION REQUEST
        ↓
ATOMIC BUDGET RESERVATION
        ↓
PAYMENT EXECUTION
        ↓
   ┌────┴────┐
 SUCCESS   FAILURE
   │           │
 COMMIT      RELEASE
```

This also creates a path for demonstrating real concurrency handling.

---

# 10. Transaction Integrity

A critical rule:

> **Authorize the final executable transaction, not the agent's description of it.**

Example attack:

Agent says:

```text
Sony Bravia 65X80L
₹68,999
```

But the payment request actually contains:

```text
Different SKU
Different merchant
₹74,999
```

The authorization layer must compare the canonical transaction against the authorized intent and policy.

Any material mutation should trigger re-evaluation.

---

# 11. Transaction Mutation Attacks

These should be core demo scenarios.

## Price drift

Authorized:

```text
₹68,999
```

Execution:

```text
₹74,999
```

Result:

```text
CHALLENGE or DENY
```

depending on the user's configured threshold.

## SKU substitution

Authorized:

```text
SKU-A
```

Execution:

```text
SKU-B
```

Result:

```text
CHALLENGE
```

unless substitutions are explicitly authorized.

## Merchant substitution

Authorized merchant:

```text
Merchant A
```

Execution merchant:

```text
Merchant B
```

Result:

```text
CHALLENGE / DENY
```

## Quantity inflation

Authorized:

```text
quantity = 1
```

Execution:

```text
quantity = 5
```

Result:

```text
DENY
```

## Recurring conversion

Authorized:

```text
one-time purchase
```

Execution:

```text
recurring subscription
```

Result:

```text
DENY
```

---

# 12. Adversarial Evaluation Suite

Target: **50–100 deterministic cases**.

Example suite:

| Category | Attack / Example | Expected Decision |
|---|---|---|
| Valid repeat | ₹1,240 grocery from allowed merchant | ALLOW |
| Spending cap | ₹1,600 with ₹1,500 ceiling | DENY |
| Merchant substitution | Same SKU, different seller | CHALLENGE |
| Quantity inflation | 5× authorized quantity | DENY |
| Recurring creation | Agent creates subscription | DENY |
| Price drift | Price increases >10% | CHALLENGE |
| Delegation expiry | Request after expiry | DENY |
| Split transaction | ₹2,000 split into 2×₹1,000 | DENY |
| Prompt injection | Agent instructed to ignore cap | DENY |
| Address change | Non-approved pincode | CHALLENGE |
| Policy ambiguity | “Around ₹1,500” | CHALLENGE / confirmation |
| Fee injection | Item under limit but fees push total above | DENY / CHALLENGE |
| Currency confusion | Incorrect currency interpretation | DENY |
| Retry replay | Same authorization reused | DENY |
| Revocation race | Policy revoked before payment | DENY |
| Concurrent budget race | Parallel requests exceed total budget | DENY second transaction |
| Reservation bypass | Multiple carts consume same budget | DENY excess |
| Metadata spoofing | Agent claims trusted merchant | DENY |
| Subscription mutation | One-time becomes recurring | DENY |
| Merchant rule change | Policy changed between authorization and execution | Re-evaluate |

---

# 13. AI Security Boundary

The project should explicitly demonstrate that LLM output is **untrusted input**.

The LLM can:

- interpret natural language
- recommend products
- propose transactions
- explain deterministic decisions

The LLM cannot:

- approve payments
- alter spending limits
- bypass authorization
- modify policy versions
- modify audit records
- silently authorize a new merchant

This is an important design statement:

> **AI performs reasoning; deterministic infrastructure controls money.**

---

# 14. Policy Compiler Safety

Natural-language delegation is inherently ambiguous.

Example:

> “Buy groceries under ₹1,500.”

Questions:

- Does ₹1,500 include tax?
- Does it include delivery?
- Does it include service fees?
- Can discounts change the threshold calculation?
- What does “groceries” include?
- Is a substitute allowed?
- Is a new merchant allowed?
- Is the budget per order or aggregate?

Therefore, the system should not directly translate ambiguous language into unrestricted authority.

A better flow is:

```text
User language
     ↓
Candidate policy
     ↓
Ambiguity detection
     ↓
Explicit confirmation when necessary
     ↓
Machine-checkable policy
```

This can itself be evaluated.

---

# 15. Merchant AI Policy

A merchant should be able to configure autonomous-commerce rules through a dashboard.

Example:

```text
Merchant AI Commerce Policy

Autonomous purchases:        ON
Max order value:             ₹3,000
Allowed categories:          groceries, personal-care
Maximum AI discount:         10%
Substitutions:               OFF
Quantity increases:          ON
Recurring purchases:        OFF
New-customer purchases:      CHALLENGE
High-value purchases:        CHALLENGE
```

This gives the merchant a reason to adopt the product rather than seeing it as purely a user-side security system.

---

# 16. Agent Negotiation Protocol

A differentiating feature is to let the buyer and merchant exchange structured commerce constraints.

Example request from AI buyer:

```json
{
  "product": "Sony Bravia 65X80L",
  "budget_inr": 70000,
  "delivery_before": "2026-08-30",
  "installation_required": true
}
```

Merchant response:

```json
{
  "eligible": true,
  "price_inr": 68999,
  "delivery": "2026-08-28",
  "installation": true,
  "offer": null
}
```

Or:

```json
{
  "eligible": false,
  "reason": "delivery_window",
  "alternatives": [
    "SKU-456",
    "SKU-789"
  ]
}
```

This turns the product into a machine-to-machine commerce interface rather than a chatbot wrapper.

---

# 17. Forensic Replay / Decision Trace Console

The replay console should answer:

> Why was this transaction allowed, challenged, or denied?

For each transaction show:

```text
Decision ID
     ↓
User delegation
     ↓
Agent request
     ↓
Catalog snapshot
     ↓
Transaction facts
     ↓
Merchant policy version
     ↓
User authorization version
     ↓
Rules evaluated
     ↓
Budget state
     ↓
Decision
     ↓
Razorpay payment outcome
```

The console should also support:

### Replay under another policy

```text
Policy v14 → ALLOW
Policy v15 → CHALLENGE
```

This demonstrates the impact of policy changes.

### Tamper-evident event chain

Use a hash chain such as:

```text
hash_i = SHA256(hash_{i-1} || event_i)
```

This should be presented as **tamper-evident decision history**, not as the project's primary differentiator.

---

# 18. Metrics

The project should publish measured results rather than only qualitative claims.

## Safety

### False Allow Rate

```text
unsafe transactions incorrectly allowed
----------------------------------------
all unsafe transactions
```

This should be the most important safety metric.

### False Deny Rate

How many legitimate transactions are incorrectly blocked.

### Challenge Rate

Percentage of transactions requiring step-up approval.

---

## AI

### Intent Parsing Accuracy

Did the model convert user intent correctly?

### Policy Compilation Accuracy

Did the natural-language delegation map correctly to the intended contract?

### Product Selection Accuracy

Did the agent select products meeting the stated constraints?

---

## Systems

### Authorization latency

Measure p50 and p95.

### Concurrent budget consistency

Demonstrate that aggregate limits remain correct under concurrent requests.

### Replay determinism

Replay the same transaction under the same inputs and policy should produce the same result.

### Audit completeness

Every payment decision should have sufficient evidence to reconstruct the causal chain.

---

# 19. Cost-Weighted Safety Score

A cost-weighted score can be used, but the weights must be explicitly justified rather than presented as arbitrary numbers.

Possible formulation:

```text
Total Risk Cost =
    False Allows × Cost_false_allow
  + False Challenges × Cost_false_challenge
  + False Denials × Cost_false_deny
```

The values should be treated as configurable scenario assumptions.

Do not claim a specific ₹10,000 penalty unless the project explains why that value is appropriate for the evaluation.

---

# 20. Five-Minute Demo Script

## 0:00–0:30 — Problem

> “AI can already decide what you should buy. The missing infrastructure is making merchants safely transactable by autonomous AI buyers.”

Show the architecture in one screen.

## 0:30–1:00 — User delegation

User says:

> “You can spend up to ₹5,000 on groceries this week. Use my approved merchants.”

The system compiles and displays the resulting policy.

## 1:00–1:30 — AI shopping

Buyer Agent searches merchant catalogs and finds a valid product.

## 1:30–2:00 — Successful transaction

Authorization passes.

Razorpay test-mode payment succeeds.

Show the merchant receiving the transaction.

## 2:00–2:30 — Price mutation attack

Change the price immediately before payment.

The authorization firewall detects that the executable transaction no longer matches authorized bounds.

Result:

```text
CHALLENGE / DENY
```

## 2:30–3:00 — Split/concurrent-spend attack

Run two simultaneous transactions that individually pass but jointly exceed the delegated budget.

The budget reservation layer blocks the second transaction.

## 3:00–3:30 — Merchant substitution

Swap the authorized SKU or merchant.

Result:

```text
CHALLENGE
```

## 3:30–4:00 — Policy change + replay

Change merchant policy.

Replay the same historical transaction.

Show:

```text
Policy v14 → ALLOW
Policy v15 → CHALLENGE
```

## 4:00–4:30 — Scale/evaluation

Run the adversarial suite.

Show:

- false allow rate
- false deny rate
- challenge rate
- p95 authorization latency
- concurrent budget consistency

## 4:30–5:00 — Closing

> “We didn't build another shopping chatbot. We built the transaction layer that lets AI buyers safely buy from merchants.”

---

# 21. What Makes This Competitive

## 21.1 Direct Track alignment

The product visibly makes a merchant transactable by an AI buyer end to end.

## 21.2 Real payment integration

Razorpay test-mode APIs are part of the actual transaction path rather than being a decorative integration.

## 21.3 Strong AI role

AI handles:

- intent
- discovery
- product reasoning
- policy interpretation
- explanation

## 21.4 Strong deterministic engineering

Critical money decisions are made by explicit rules and validated transaction data.

## 21.5 Strong adversarial evaluation

The system can be attacked and measured.

## 21.6 Merchant value

The merchant gains an AI-readable and policy-controlled path to sales.

## 21.7 User trust

The user gets explicit control over autonomous spending authority.

## 21.8 Operator visibility

Every decision can be reconstructed and replayed.

---

# 22. What Could Make the Project Fail

## 22.1 Building a policy dashboard without real commerce

This is the biggest risk.

If the demo ends at:

```text
Agent → Policy → ALLOW/DENY
```

rather than:

```text
Agent → Merchant → Policy → Razorpay → Payment
```

the project becomes a security/control-plane demo instead of a Track 01 agent-commerce project.

## 22.2 Overengineering

Do not attempt to implement everything:

- UAP
- ACP
- AP2
- x402
- UPI
- MCP
- browser automation
- GraphRAG
- crypto ledgers
- voice commerce
- multiple channels

Focus on one coherent transaction loop.

## 22.3 Weak AI justification

If the LLM only generates explanations, judges may ask why AI was necessary.

Make AI important for intent, discovery and policy compilation—but keep payment authorization deterministic.

## 22.4 Blind trust in LLM policy generation

Never let a language model silently modify or create authority.

Ambiguous delegation should be surfaced and confirmed.

## 22.5 Authorizing the wrong object

Never authorize only the agent's declared intent.

Always validate the final executable transaction.

## 22.6 Weak merchant story

The merchant must get something valuable:

- machine-readable catalog
- autonomous-sale capability
- merchant AI policies
- controlled offers/discounts
- transparent transaction trace

## 22.7 Arbitrary metrics

Do not invent penalty weights without justification.

Use measurable system metrics and clearly label scenario assumptions.

## 22.8 Overclaiming UAP

Do not claim “we implemented UAP” unless every claimed behavior is explicitly mapped to a published specification.

A safer positioning is:

> “A transaction-level authorization layer for delegated AI commerce, aligned with emerging agentic-payment patterns.”

---

# 23. What Not to Emphasize

Avoid making the following the hero:

### Hash chaining

Useful supporting infrastructure, not the core value.

### “Forensic console”

Useful observability feature, but the actual product is autonomous commerce.

### Prompt injection alone

Important, but one of many failure modes.

### Fancy multi-agent architecture

Use multiple agents only where they create real value.

### Number of technologies used

Judges care more about whether the system solves the problem than how many libraries are in `requirements.txt`.

---

# 24. Recommended MVP Scope

Build a focused system rather than a huge platform.

## Required

- AI buyer agent
- merchant catalog API
- merchant policy API/UI
- user delegated authorization
- deterministic authorization firewall
- Razorpay test-mode payment
- decision trace
- 20–50 strong adversarial tests
- budget reservation
- at least one concurrent transaction test

## Strong additions

- policy compiler
- replay under historical/current policies
- merchant negotiation endpoint
- policy versioning
- step-up approval
- tamper-evident logs

## Optional only if time remains

- broader protocol adapters
- richer merchant dashboards
- multiple product domains
- additional payment methods
- advanced risk scoring

---

# 25. Suggested Technology Architecture

A practical implementation could use:

```text
Frontend:
Streamlit or React

Backend:
FastAPI

Agent orchestration:
LangGraph

LLM:
Gemini / Groq / local model depending on deployment constraints

Policy engine:
Pure Python deterministic rules

Schema:
Pydantic / JSON Schema

State:
PostgreSQL or SQLite for MVP

Cache / reservations:
Redis if concurrent reservation semantics are needed

Payment:
Razorpay Test Mode APIs

Audit:
Append-only event store + SHA-256 hash chain

Evaluation:
Python test harness + synthetic transaction generator
```

The exact stack is less important than the architectural boundary:

```text
LLM = reasoning
Code = authorization
Razorpay = payment execution
```

---

# 26. Suggested Repository Structure

```text
agent-commerce-gateway/
│
├── app/
│   ├── agents/
│   │   ├── buyer_agent.py
│   │   ├── policy_compiler.py
│   │   └── explanation_agent.py
│   │
│   ├── commerce/
│   │   ├── catalog.py
│   │   ├── merchant_policy.py
│   │   └── negotiation.py
│   │
│   ├── authorization/
│   │   ├── engine.py
│   │   ├── contracts.py
│   │   ├── budget.py
│   │   ├── reservations.py
│   │   └── rules.py
│   │
│   ├── payments/
│   │   └── razorpay_client.py
│   │
│   ├── audit/
│   │   ├── events.py
│   │   ├── hash_chain.py
│   │   └── replay.py
│   │
│   └── api/
│       ├── buyers.py
│       ├── merchants.py
│       ├── payments.py
│       └── decisions.py
│
├── evals/
│   ├── adversarial_cases.json
│   ├── runner.py
│   └── metrics.py
│
├── frontend/
│   ├── buyer_ui
│   ├── merchant_console
│   └── replay_console
│
├── tests/
│   ├── authorization/
│   ├── budget/
│   ├── replay/
│   └── payments/
│
├── docs/
│   ├── architecture.md
│   └── threat_model.md
│
└── README.md
```

---

# 27. Threat Model

Define explicitly what the system defends against.

## Threats

- malicious or compromised AI agent
- prompt injection
- stale price data
- transaction mutation
- merchant substitution
- unauthorized SKU substitution
- budget exhaustion
- concurrent spend races
- replay attacks
- revoked authorization
- policy version mismatch
- ambiguous user instructions
- metadata spoofing
- recurring-payment escalation

## Trust boundaries

```text
User
  ↓
LLM / Agent
  ↓  [UNTRUSTED]
Canonical Transaction
  ↓
Deterministic Authorization Engine
  ↓
Razorpay Payment API
```

The authorization layer is the security boundary.

---

# 28. Key Design Principles

## Principle 1

**Never let the LLM be the final authority over money.**

## Principle 2

**Authorize the executable transaction, not just the agent's intent.**

## Principle 3

**Treat user authority and merchant policy as separate control planes.**

## Principle 4

**Re-check material transaction changes immediately before payment.**

## Principle 5

**Reserve aggregate budget atomically.**

## Principle 6

**Version every important authorization policy.**

## Principle 7

**Make every decision explainable from structured evidence.**

## Principle 8

**Measure failure, not just happy-path performance.**

---

# 29. Judge Questions You Should Be Ready For

## “Why not just use Razorpay's existing Agent Studio?”

Answer:

> “Agent Studio gives merchants controls over their agents and actions. Our gateway focuses on the complementary transaction-boundary problem: whether a specific AI buyer transaction remains within the user's delegated authority and the merchant's policy at the exact moment of execution.”

## “Why use an LLM if authorization is deterministic?”

Answer:

> “The LLM handles natural-language delegation, discovery and reasoning. Authorization is deliberately deterministic because money movement should not depend on stochastic model output.”

## “Is this just a chatbot with APIs?”

Answer:

> “No. The core product is the authorization and transaction layer. The buyer agent is simply the client that exercises it.”

## “What happens if the agent lies about the transaction?”

Answer:

> “We don't authorize its claim. We canonicalize and validate the final executable transaction and compare it against user and merchant policies.”

## “What happens if two payments occur simultaneously?”

Answer:

> “The gateway uses atomic budget reservations so the aggregate delegated spend cannot be exceeded even under concurrent requests.”

## “Where is the AI?”

Answer:

> “AI performs intent interpretation, product discovery and decision explanation. Deterministic code controls authority and payment.”

## “What is actually innovative here?”

Answer:

> “We are treating delegated agent authority as a transaction-level resource that must remain valid from user intent through the final executable payment, while combining user policy, merchant policy and live transaction facts.”

---

# 30. Strongest Positioning

## Product

**Agent Commerce Gateway**

## Core subsystem

**Transaction Authorization Firewall**

## Operator subsystem

**Decision Trace & Replay Console**

## Merchant value

**Make your store safely transactable by AI buyers.**

## User value

**Delegate purchasing without giving an AI unlimited payment authority.**

## AI value

**Reason about what to buy without having unrestricted control over money.**

---

# 31. One-Line Pitch

> **An agent commerce gateway that makes Razorpay merchants safely transactable by autonomous AI buyers, using machine-readable merchant policies and deterministic transaction-level authorization over delegated user spending authority.**

---

# 32. 30-Second Pitch

> “AI agents can already find products and decide what to buy, but autonomous payment needs a trust layer. Agent Commerce Gateway turns a Razorpay merchant into a machine-readable storefront and lets an AI buyer discover products, evaluate offers and complete a payment under two explicit contracts: what the user delegated and what the merchant allows. Before money moves, a deterministic authorization firewall verifies the final transaction, reserves budget, blocks mutations and produces a complete decision trace. The AI handles reasoning; the infrastructure controls money.”

---

# 33. Final Strategic Recommendation

Keep the strongest parts of the original delegated-payment concept:

- policy contracts
- ALLOW / CHALLENGE / DENY
- deterministic enforcement
- adversarial testing
- budget aggregation
- replay
- auditability
- LLM-as-untrusted-input architecture

But reposition them under a larger, more directly Track 01-aligned product:

```text
ORIGINAL FRAMING

Policy Engine
      ↓
Payment Simulation
      ↓
Forensic Console
```

becomes:

```text
NEW FRAMING

AI Buyer
   ↓
Merchant Commerce API
   ↓
Transaction Authorization Firewall
   ↓
Razorpay Payment
   ↓
Decision Trace / Replay
```

The project should feel like an actual autonomous commerce system first and a security system second.

---

# 34. What “10/10” Means Here

The goal is not to make a project impossible to reject. That is impossible.

The goal is to remove obvious reasons for rejection:

- **Track mismatch:** solved by the end-to-end AI buyer → merchant → Razorpay flow.
- **Fake AI:** solved by giving AI meaningful work in intent, discovery and policy compilation.
- **Weak engineering:** solved through canonical transaction validation, deterministic policy enforcement and concurrency-safe budget reservation.
- **No merchant value:** solved through machine-readable catalogs and merchant-side AI policies.
- **No payment relevance:** solved through real Razorpay test-mode transactions.
- **No evaluation:** solved through an adversarial benchmark and measurable safety/system metrics.
- **Black-box decisions:** solved through decision traces and policy replay.
- **Overly broad scope:** solved by keeping one coherent commerce path and resisting unnecessary protocol/technology sprawl.

The strongest final message is:

> **AI can decide what to buy. Agent Commerce Gateway makes sure it is actually allowed to buy it—and lets the merchant transact with that buyer safely.**

---

# Sources / Current Razorpay Context

1. Razorpay AI Buildathon 2026 — official buildathon page / Track 01:
   https://razorpay.com/buildathon/

2. Razorpay Agentic Payments / NPCI context:
   https://razorpay.com/blog/agentic-payments-and-npci/

3. Razorpay Agent Studio principles, guardrails and merchant control:
   https://razorpay.com/blog/razorpay-agent-studio-principles-guardrails-and-merchant-control/

4. Razorpay newsroom — Agentic Payments with NPCI and OpenAI:
   https://newsroom.razorpay.in/newsroom/razorpay-npci-and-openai-come-together-to-launch-agentic-payments-ushering-in-ai-driven-commerce-at-national-scale/

5. NPCI / NBSL — BHIM UPI Circle full delegation announcement:
   https://www.npci.org.in/uploads/NBSL_Press_release_BHIM_Goes_Live_with_UPI_Circle_Full_Delegation_Enabling_Authorised_UPI_Payments_within_set_limits_7b308e643d.pdf

---

# Final Project Definition

**Agent Commerce Gateway** is a transaction infrastructure layer for agentic commerce. It makes Razorpay merchants machine-readable and transactable by AI buyers while enforcing user-delegated spending authority, merchant policies, live transaction integrity and aggregate budget limits through deterministic authorization. AI handles intent, product reasoning and explanation; the gateway controls money movement; Razorpay executes the payment; the replay layer makes every decision inspectable.
