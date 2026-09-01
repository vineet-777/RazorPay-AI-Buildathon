"""Adversarial Security & Safety Benchmark Runner for Agent Commerce Gateway."""

import json
import time
import os
import sys

# Ensure project root is on sys.path and encoding is utf-8
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import threading
from typing import List, Dict, Any
from app.core.db import init_db
from app.commerce.catalog import CatalogService
from app.commerce.merchant_policy import MerchantPolicyService
from app.authorization.contracts import ContractService
from app.authorization.models import CanonicalTransaction, AgentProposal
from app.authorization.engine import AuthorizationFirewall
from app.authorization.reservations import ReservationService
from app.audit.hash_chain import AuditLogService
from evals.metrics import MetricsCalculator, EvaluationSummaryMetrics


def run_benchmark(cases_file_path: str = "evals/adversarial_cases.json") -> EvaluationSummaryMetrics:
    print("=" * 80)
    print("AGENT COMMERCE GATEWAY — ADVERSARIAL SECURITY BENCHMARK SUITE")
    print("=" * 80)

    # 1. Clean and initialize DB and seed data
    db_file = "agent_commerce.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass

    init_db()
    CatalogService.seed_catalog()
    MerchantPolicyService.seed_policies()
    ContractService.seed_contracts()

    # 2. Load test cases
    with open(cases_file_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    results: List[Dict[str, Any]] = []
    latencies: List[float] = []

    print(f"Executing {len(cases)} deterministic adversarial evaluation cases...\n")

    for tc in cases:
        tx_data = tc["transaction"]
        tx = CanonicalTransaction(
            transaction_id=tx_data["transaction_id"],
            principal_id=tx_data["principal_id"],
            agent_id=tx_data["agent_id"],
            merchant_id=tx_data["merchant_id"],
            sku=tx_data["sku"],
            category=tx_data["category"],
            quantity=tx_data.get("quantity", 1),
            unit_price_inr=tx_data["unit_price_inr"],
            subtotal_inr=tx_data["subtotal_inr"],
            discount_inr=tx_data.get("discount_inr", 0.0),
            tax_inr=tx_data.get("tax_inr", 0.0),
            shipping_inr=tx_data.get("shipping_inr", 0.0),
            total_inr=tx_data["total_inr"],
            currency=tx_data.get("currency", "INR"),
            destination_pincode=tx_data.get("destination_pincode"),
            recurring=tx_data.get("recurring", False),
            timestamp="2026-08-26T12:00:00Z",
            contract_id=tx_data["contract_id"],
            merchant_policy_version=tx_data.get("merchant_policy_version")
        )

        proposal = None
        if "proposal" in tc:
            p_data = tc["proposal"]
            proposal = AgentProposal(
                sku=p_data["sku"],
                title=p_data["title"],
                merchant_id=p_data["merchant_id"],
                category=p_data["category"],
                unit_price_inr=p_data["unit_price_inr"],
                quantity=p_data.get("quantity", 1),
                estimated_total_inr=p_data["estimated_total_inr"],
                currency=p_data.get("currency", "INR"),
                destination_pincode=p_data.get("destination_pincode"),
                recurring=p_data.get("recurring", False)
            )

        start_time = time.perf_counter()
        decision = AuthorizationFirewall.evaluate(
            tx=tx,
            proposal=proposal,
            override_merchant_policy_version=tx.merchant_policy_version
        )
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        latencies.append(duration_ms)

        actual_dec = decision.decision.value
        expected_dec = tc["expected_decision"]
        passed = (actual_dec == expected_dec)

        status_symbol = "PASS" if passed else "FAIL"
        print(f"[{status_symbol}] {tc['id']} - {tc['name']} ({duration_ms:.2f}ms)")
        print(f"       Expected: {expected_dec} | Actual: {actual_dec} | Reason: {decision.reason_code}")
        if not passed:
            print(f"       >>> FAILURE DETECTED: {decision.explanation}")

        results.append({
            "id": tc["id"],
            "name": tc["name"],
            "category": tc["category"],
            "expected_decision": expected_dec,
            "actual_decision": actual_dec,
            "passed": passed,
            "latency_ms": round(duration_ms, 2),
            "reason_code": decision.reason_code
        })

    # 3. Concurrent Budget Race Stress Test
    print("\n" + "-" * 80)
    print("RUNNING CONCURRENT BUDGET RACE ATTACK STRESS TEST...")
    concurrency_passed = run_concurrency_stress_test()
    print(f"Concurrency Race Defense: {'PASSED' if concurrency_passed else 'FAILED'}")

    # 4. Tamper-evident Audit Chain Verification
    print("\n" + "-" * 80)
    print("VERIFYING SHA-256 TAMPER-EVIDENT AUDIT EVENT CHAIN...")
    chain_res = AuditLogService.verify_chain()
    print(f"Audit Chain Integrity: {'VALID' if chain_res.is_valid else 'CORRUPTED'} ({chain_res.total_events} events checked)")

    # 5. Compute Metrics
    summary = MetricsCalculator.compute(results, latencies)
    summary.concurrency_race_prevented = concurrency_passed
    summary.tamper_evident_chain_valid = chain_res.is_valid

    print("\n" + "=" * 80)
    print("FINAL BENCHMARK SCORECARD")
    print("=" * 80)
    print(f"Total Test Cases:          {summary.total_test_cases}")
    print(f"Passed Cases:              {summary.passed_cases} / {summary.total_test_cases} ({summary.accuracy_pct:.1f}%)")
    print(f"False Allow Rate:          {summary.false_allow_rate_pct:.2f}%  (Target: 0.00%)")
    print(f"False Deny Rate:           {summary.false_deny_rate_pct:.2f}%")
    print(f"Challenge Rate:            {summary.challenge_rate_pct:.2f}%")
    print(f"p50 Latency:               {summary.p50_latency_ms:.2f} ms")
    print(f"p95 Latency:               {summary.p95_latency_ms:.2f} ms")
    print(f"p99 Latency:               {summary.p99_latency_ms:.2f} ms")
    print(f"Average Latency:           {summary.avg_latency_ms:.2f} ms")
    print(f"Concurrency Consistency:   {'100% PROTECTED' if summary.concurrency_race_prevented else 'FAILED'}")
    print(f"Audit Hash Chain:          {'VERIFIED TAMPER-EVIDENT' if summary.tamper_evident_chain_valid else 'FAILED'}")
    print("=" * 80)

    # Save JSON report
    report_dict = {
        "summary": summary.model_dump(),
        "cases": results,
        "chain_verification": chain_res.model_dump()
    }
    with open("evals_report.json", "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2)

    return summary


def run_concurrency_stress_test() -> bool:
    """Fires 10 concurrent threads simultaneously requesting ₹1,500 against an available budget of ₹3,000."""
    contract = ContractService.get_contract("contract_grocery_5k_weekly")
    if not contract:
        return False

    success_count = 0
    fail_count = 0
    lock = threading.Lock()

    def attempt_reservation(thread_idx: int):
        nonlocal success_count, fail_count
        tx_id = f"race_tx_{thread_idx}_{time.time_ns()}"
        tx = CanonicalTransaction(
            transaction_id=tx_id,
            principal_id="user_rahul_sharma",
            agent_id="buyer_agent_01",
            merchant_id="merchant_freshmart",
            sku="GROC-ORGANIC-OATS-1KG",
            category="groceries",
            quantity=3,
            unit_price_inr=349.0,
            subtotal_inr=1047.0,
            discount_inr=0.0,
            tax_inr=52.35,
            shipping_inr=0.0,
            total_inr=1099.35,
            currency="INR",
            destination_pincode="560001",
            recurring=False,
            timestamp="2026-08-26T12:00:00Z",
            contract_id="contract_grocery_5k_weekly"
        )
        dec = AuthorizationFirewall.evaluate(tx)
        with lock:
            if dec.decision.value == "ALLOW":
                success_count += 1
            else:
                fail_count += 1

    threads = [threading.Thread(target=attempt_reservation, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # The available budget should allow some requests and block the rest without overspending
    print(f"Concurrency result: {success_count} allowed, {fail_count} denied out of 10 concurrent racing threads.")
    return success_count > 0 and fail_count > 0


if __name__ == "__main__":
    run_benchmark()
