#!/usr/bin/env python3
"""
Agentic Process Orchestrator Benchmark

This benchmark tests the fine-tuned model as an intelligent agent that:
1. Monitors event sequences in real-time
2. Predicts what should happen next
3. Detects anomalies when actual events differ from predictions
4. Suggests corrective actions

This is a more meaningful benchmark than simple next-token prediction
because it tests the model's practical utility in a real-world scenario.
"""

import json
import random
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from enum import Enum

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)


class AnomalyType(Enum):
    NONE = "none"
    WRONG_EVENT = "wrong_event"           # Event from different process
    SKIPPED_STEP = "skipped_step"         # Required step was skipped
    OUT_OF_ORDER = "out_of_order"         # Events in wrong sequence
    IMPOSSIBLE_TRANSITION = "impossible"   # Logically impossible transition


@dataclass
class AgentDecision:
    """Represents the agent's analysis of an event"""
    event_observed: str
    event_predicted: str
    confidence: float
    is_anomaly: bool
    anomaly_type: Optional[str]
    explanation: str
    suggested_action: str


# Valid process flows for reference
VALID_FLOWS = {
    "trade": {
        "normal": ["OrderSubmitted", "OrderValidated", "OrderRouted", "OrderFilled",
                   "TradeBooked", "TradeSettled", "TradeConfirmed"],
        "rejected": ["OrderSubmitted", "OrderRejected"],
        "cancelled": ["OrderSubmitted", "OrderValidated", "OrderRouted", "OrderCancelled"],
        "partial": ["OrderSubmitted", "OrderValidated", "OrderRouted",
                    "OrderPartiallyFilled", "OrderFilled", "TradeBooked", "TradeSettled", "TradeConfirmed"],
    },
    "payment": {
        "normal": ["PaymentInitiated", "PaymentValidated", "PaymentPendingApproval",
                   "PaymentApproved", "PaymentExecuted", "PaymentCompleted"],
        "rejected": ["PaymentInitiated", "PaymentValidated", "PaymentPendingApproval", "PaymentRejected"],
        "failed": ["PaymentInitiated", "PaymentValidated", "PaymentPendingApproval",
                   "PaymentApproved", "PaymentExecuted", "PaymentFailed"],
    },
    "risk": {
        "mitigated": ["RiskLimitBreached", "RiskAlertCreated", "RiskAlertAcknowledged",
                      "RiskMitigationStarted", "RiskMitigationCompleted", "RiskAlertResolved"],
        "accepted": ["RiskLimitBreached", "RiskAlertCreated", "RiskAlertAcknowledged", "RiskAlertResolved"],
    },
    "compliance": {
        "clear": ["ComplianceCheckTriggered", "ComplianceCheckPassed"],
        "flagged": ["ComplianceCheckTriggered", "ComplianceFlagRaised",
                    "ComplianceReviewAssigned", "ComplianceReviewCompleted", "ComplianceCaseClosed"],
    },
    "account": {
        "opened": ["AccountApplicationSubmitted", "AccountKYCStarted", "AccountDocumentReceived",
                   "AccountKYCCompleted", "AccountOpened", "AccountFunded"],
    }
}


def generate_normal_sequence(process_type: str = None) -> Tuple[List[str], str]:
    """Generate a normal (non-anomalous) sequence"""
    if process_type is None:
        process_type = random.choice(list(VALID_FLOWS.keys()))

    flows = VALID_FLOWS[process_type]
    flow_name = random.choice(list(flows.keys()))
    return flows[flow_name].copy(), process_type


def generate_anomalous_sequence() -> Tuple[List[str], str, AnomalyType, int]:
    """Generate a sequence with an intentional anomaly"""
    process_type = random.choice(list(VALID_FLOWS.keys()))
    flows = VALID_FLOWS[process_type]
    flow_name = random.choice(list(flows.keys()))
    sequence = flows[flow_name].copy()

    anomaly_type = random.choice([
        AnomalyType.WRONG_EVENT,
        AnomalyType.SKIPPED_STEP,
        AnomalyType.OUT_OF_ORDER,
    ])

    if len(sequence) < 3:
        # Too short for meaningful anomaly, just use wrong event
        anomaly_type = AnomalyType.WRONG_EVENT

    anomaly_position = -1

    if anomaly_type == AnomalyType.WRONG_EVENT:
        # Insert an event from a different process
        other_process = random.choice([p for p in VALID_FLOWS.keys() if p != process_type])
        other_flows = VALID_FLOWS[other_process]
        other_sequence = random.choice(list(other_flows.values()))
        wrong_event = random.choice(other_sequence)

        anomaly_position = random.randint(1, len(sequence) - 1)
        sequence[anomaly_position] = wrong_event

    elif anomaly_type == AnomalyType.SKIPPED_STEP:
        # Remove a required middle step
        if len(sequence) > 3:
            skip_position = random.randint(1, len(sequence) - 2)
            anomaly_position = skip_position  # The anomaly shows at the position after skip
            sequence.pop(skip_position)

    elif anomaly_type == AnomalyType.OUT_OF_ORDER:
        # Swap two adjacent events
        if len(sequence) > 2:
            swap_position = random.randint(1, len(sequence) - 2)
            sequence[swap_position], sequence[swap_position + 1] = \
                sequence[swap_position + 1], sequence[swap_position]
            anomaly_position = swap_position + 1

    return sequence, process_type, anomaly_type, anomaly_position


class ProcessOrchestrator:
    """
    An agentic process orchestrator that monitors event streams,
    predicts next events, and detects anomalies.
    """

    SYSTEM_PROMPT = """You are a financial process prediction system. Given a sequence of events from a financial workflow, predict what event will happen next.

Event types you may encounter:
- Trade: OrderSubmitted -> OrderValidated -> OrderRouted -> OrderFilled -> TradeBooked -> TradeSettled -> TradeConfirmed
- Trade (rejected): OrderSubmitted -> OrderRejected
- Payment: PaymentInitiated -> PaymentValidated -> PaymentPendingApproval -> PaymentApproved -> PaymentExecuted -> PaymentCompleted
- Risk: RiskLimitBreached -> RiskAlertCreated -> RiskAlertAcknowledged -> RiskMitigationStarted -> RiskMitigationCompleted -> RiskAlertResolved
- Compliance: ComplianceCheckTriggered -> ComplianceCheckPassed (or ComplianceFlagRaised -> ComplianceReviewAssigned -> ...)
- Account: AccountApplicationSubmitted -> AccountKYCStarted -> AccountDocumentReceived -> AccountKYCCompleted -> AccountOpened -> AccountFunded

Respond with ONLY the next event type name."""

    def __init__(self, model_path: str):
        """Initialize the orchestrator with a fine-tuned model"""
        print(f"Loading model: {model_path}")

        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        model_kwargs = {"trust_remote_code": True}
        if torch.cuda.is_available():
            model_kwargs["device_map"] = "auto"
            model_kwargs["torch_dtype"] = torch.bfloat16

        self.model = AutoModelForCausalLM.from_pretrained(model_path, **model_kwargs)
        self.pipe = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            max_new_tokens=30,
            do_sample=False,
            pad_token_id=self.tokenizer.eos_token_id
        )

    def predict_next_event(self, event_history: List[str]) -> str:
        """Predict the next event given history"""
        context_lines = [f"{i+1}. {evt}" for i, evt in enumerate(event_history)]
        context = "\n".join(context_lines)

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Event sequence:\n{context}\n\nWhat is the next event?"}
        ]

        output = self.pipe(messages, return_full_text=False)
        prediction = output[0]["generated_text"].strip()
        # Clean prediction
        prediction = prediction.split()[0] if prediction else ""
        prediction = prediction.rstrip(".,;:")
        return prediction

    def analyze_event(self, event_history: List[str], actual_event: str) -> AgentDecision:
        """
        Analyze whether an observed event is expected or anomalous.
        This is the core agent logic.
        """
        predicted = self.predict_next_event(event_history)
        is_anomaly = predicted != actual_event

        # Determine anomaly type and explanation
        if is_anomaly:
            # Check what kind of anomaly this might be
            last_event = event_history[-1] if event_history else "START"

            # Detect cross-process contamination
            actual_process = self._detect_process_type(actual_event)
            expected_process = self._detect_process_type(predicted)

            if actual_process != expected_process and actual_process and expected_process:
                anomaly_type = "cross_process_contamination"
                explanation = f"Expected {expected_process} event '{predicted}', but received {actual_process} event '{actual_event}'. Events from different process types are mixed."
                action = f"Investigate why {actual_event} appeared in this stream. Check for event routing errors."
            else:
                anomaly_type = "unexpected_transition"
                explanation = f"Expected '{predicted}' after '{last_event}', but observed '{actual_event}'. This transition is unusual."
                action = f"Review the process. If '{actual_event}' is valid, the process may have taken an exception path. Otherwise, investigate the cause."
        else:
            anomaly_type = None
            explanation = f"Event '{actual_event}' matches prediction. Process is following expected flow."
            action = "No action needed. Continue monitoring."

        return AgentDecision(
            event_observed=actual_event,
            event_predicted=predicted,
            confidence=0.88 if not is_anomaly else 0.75,  # Simplified confidence
            is_anomaly=is_anomaly,
            anomaly_type=anomaly_type,
            explanation=explanation,
            suggested_action=action
        )

    def _detect_process_type(self, event: str) -> Optional[str]:
        """Detect which process type an event belongs to"""
        event_to_process = {
            "Order": "trade", "Trade": "trade",
            "Payment": "payment",
            "Risk": "risk",
            "Compliance": "compliance",
            "Account": "account", "KYC": "account"
        }
        for prefix, process in event_to_process.items():
            if prefix in event:
                return process
        return None

    def monitor_sequence(self, events: List[str]) -> List[AgentDecision]:
        """Monitor an entire sequence and return decisions for each transition"""
        decisions = []
        for i in range(1, len(events)):
            history = events[:i]
            actual = events[i]
            decision = self.analyze_event(history, actual)
            decisions.append(decision)
        return decisions


def run_benchmark(model_path: str, num_normal: int = 50, num_anomalous: int = 50):
    """Run the agentic benchmark"""

    print("=" * 70)
    print("AGENTIC PROCESS ORCHESTRATOR BENCHMARK")
    print("=" * 70)

    # Initialize agent
    agent = ProcessOrchestrator(model_path)

    # Generate test cases
    print(f"\nGenerating {num_normal} normal + {num_anomalous} anomalous sequences...")

    test_cases = []

    # Normal sequences
    for _ in range(num_normal):
        sequence, process_type = generate_normal_sequence()
        test_cases.append({
            "sequence": sequence,
            "process_type": process_type,
            "has_anomaly": False,
            "anomaly_type": None,
            "anomaly_position": None
        })

    # Anomalous sequences
    for _ in range(num_anomalous):
        sequence, process_type, anomaly_type, anomaly_pos = generate_anomalous_sequence()
        test_cases.append({
            "sequence": sequence,
            "process_type": process_type,
            "has_anomaly": True,
            "anomaly_type": anomaly_type,
            "anomaly_position": anomaly_pos
        })

    random.shuffle(test_cases)

    # Run agent on all test cases
    print("\nRunning agent on test sequences...")

    results = {
        "true_positives": 0,   # Correctly detected anomalies
        "false_positives": 0,  # Normal flagged as anomaly
        "true_negatives": 0,   # Correctly identified normal
        "false_negatives": 0,  # Missed anomalies
        "details": []
    }

    for i, test_case in enumerate(test_cases):
        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(test_cases)}")

        sequence = test_case["sequence"]
        has_anomaly = test_case["has_anomaly"]

        # Agent monitors the sequence
        decisions = agent.monitor_sequence(sequence)

        # Check if agent detected any anomaly
        agent_detected_anomaly = any(d.is_anomaly for d in decisions)

        # Score
        if has_anomaly and agent_detected_anomaly:
            results["true_positives"] += 1
            result_type = "TP"
        elif has_anomaly and not agent_detected_anomaly:
            results["false_negatives"] += 1
            result_type = "FN"
        elif not has_anomaly and agent_detected_anomaly:
            results["false_positives"] += 1
            result_type = "FP"
        else:
            results["true_negatives"] += 1
            result_type = "TN"

        results["details"].append({
            "sequence": sequence,
            "has_anomaly": has_anomaly,
            "anomaly_type": test_case["anomaly_type"].value if test_case["anomaly_type"] else None,
            "agent_detected": agent_detected_anomaly,
            "result": result_type,
            "decisions": [
                {
                    "predicted": d.event_predicted,
                    "observed": d.event_observed,
                    "is_anomaly": d.is_anomaly
                }
                for d in decisions
            ]
        })

    # Calculate metrics
    tp, fp, tn, fn = results["true_positives"], results["false_positives"], \
                      results["true_negatives"], results["false_negatives"]

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / (tp + tn + fp + fn)

    results["metrics"] = {
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "accuracy": accuracy
    }

    # Print report
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)

    print("\n### Confusion Matrix ###")
    print(f"                    Actual Anomaly    Actual Normal")
    print(f"  Agent Detected:        {tp:3d} (TP)         {fp:3d} (FP)")
    print(f"  Agent Missed:          {fn:3d} (FN)         {tn:3d} (TN)")

    print("\n### Metrics ###")
    print(f"  Precision:  {precision:.1%}  (of detected anomalies, how many were real)")
    print(f"  Recall:     {recall:.1%}  (of real anomalies, how many were detected)")
    print(f"  F1 Score:   {f1:.1%}  (harmonic mean of precision and recall)")
    print(f"  Accuracy:   {accuracy:.1%}  (overall correct classifications)")

    print("\n### Sample Agent Decisions ###")

    # Show some true positives
    tps = [d for d in results["details"] if d["result"] == "TP"][:2]
    if tps:
        print("\nTrue Positives (correctly detected anomalies):")
        for tp_case in tps:
            print(f"  Sequence: {' -> '.join(tp_case['sequence'][:4])}...")
            print(f"  Anomaly type: {tp_case['anomaly_type']}")
            flagged = [d for d in tp_case["decisions"] if d["is_anomaly"]][0]
            print(f"  Agent flagged: expected '{flagged['predicted']}', saw '{flagged['observed']}'")

    # Show some false negatives
    fns = [d for d in results["details"] if d["result"] == "FN"][:2]
    if fns:
        print("\nFalse Negatives (missed anomalies):")
        for fn_case in fns:
            print(f"  Sequence: {' -> '.join(fn_case['sequence'][:4])}...")
            print(f"  Anomaly type: {fn_case['anomaly_type']} (not detected)")

    # Save results
    output_path = "output/reports/agentic_benchmark_results.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Simplify for JSON
    json_results = {
        "metrics": results["metrics"],
        "confusion_matrix": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn
        },
        "test_cases": {
            "normal_sequences": num_normal,
            "anomalous_sequences": num_anomalous
        }
    }

    with open(output_path, 'w') as f:
        json.dump(json_results, f, indent=2)

    print(f"\nResults saved to: {output_path}")

    return results


def demo_agent(model_path: str):
    """Interactive demo of the agent"""

    print("=" * 70)
    print("AGENTIC PROCESS ORCHESTRATOR DEMO")
    print("=" * 70)

    agent = ProcessOrchestrator(model_path)

    # Demo 1: Normal sequence
    print("\n### Demo 1: Normal Trade Sequence ###")
    normal_sequence = ["OrderSubmitted", "OrderValidated", "OrderRouted", "OrderFilled", "TradeBooked"]

    print(f"Sequence: {' -> '.join(normal_sequence)}")
    print("\nAgent monitoring each transition:")

    for i in range(1, len(normal_sequence)):
        history = normal_sequence[:i]
        actual = normal_sequence[i]
        decision = agent.analyze_event(history, actual)

        status = "ANOMALY DETECTED" if decision.is_anomaly else "OK"
        print(f"  After {history[-1]}: saw '{actual}' (predicted '{decision.event_predicted}') [{status}]")

    # Demo 2: Anomalous sequence
    print("\n### Demo 2: Anomalous Sequence (wrong event injected) ###")
    anomalous_sequence = ["OrderSubmitted", "OrderValidated", "PaymentFailed", "OrderFilled"]

    print(f"Sequence: {' -> '.join(anomalous_sequence)}")
    print("\nAgent monitoring each transition:")

    for i in range(1, len(anomalous_sequence)):
        history = anomalous_sequence[:i]
        actual = anomalous_sequence[i]
        decision = agent.analyze_event(history, actual)

        status = "ANOMALY DETECTED" if decision.is_anomaly else "OK"
        print(f"  After {history[-1]}: saw '{actual}' (predicted '{decision.event_predicted}') [{status}]")
        if decision.is_anomaly:
            print(f"    -> {decision.explanation}")
            print(f"    -> Action: {decision.suggested_action}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agentic Process Orchestrator Benchmark")
    parser.add_argument("--model", default="./output/process-model", help="Path to fine-tuned model")
    parser.add_argument("--demo", action="store_true", help="Run interactive demo")
    parser.add_argument("--normal", type=int, default=50, help="Number of normal sequences")
    parser.add_argument("--anomalous", type=int, default=50, help="Number of anomalous sequences")

    args = parser.parse_args()

    if args.demo:
        demo_agent(args.model)
    else:
        run_benchmark(args.model, args.normal, args.anomalous)
