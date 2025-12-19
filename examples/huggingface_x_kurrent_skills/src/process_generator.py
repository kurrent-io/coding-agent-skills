"""
Financial Process Event Generator

Generates realistic financial process sequences and creates training data
for event prediction models.

Training task: Given a sequence of events, predict the next event.
"""

import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import asdict
import json

from events.process_events import (
    # Trade events
    OrderSubmitted, OrderValidated, OrderRejected, OrderRouted,
    OrderPartiallyFilled, OrderFilled, OrderCancelled,
    TradeBooked, TradeSettled, TradeConfirmed,
    # Payment events
    PaymentInitiated, PaymentValidated, PaymentPendingApproval,
    PaymentApproved, PaymentRejected, PaymentExecuted,
    PaymentCompleted, PaymentFailed,
    # Risk events
    RiskLimitBreached, RiskAlertCreated, RiskAlertAcknowledged,
    RiskMitigationStarted, RiskMitigationCompleted, RiskAlertResolved,
    # Compliance events
    ComplianceCheckTriggered, ComplianceCheckPassed, ComplianceFlagRaised,
    ComplianceReviewAssigned, ComplianceReviewCompleted,
    ComplianceEscalated, ComplianceCaseClosed,
    # Account events
    AccountApplicationSubmitted, AccountKYCStarted, AccountDocumentReceived,
    AccountKYCCompleted, AccountOpened, AccountFunded, AccountStatusChanged,
    PROCESS_FLOWS, ALL_EVENT_TYPES,
)


class ProcessEventGenerator:
    """Generates realistic financial process event sequences"""

    SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM"]
    VENUES = ["NYSE", "NASDAQ", "BATS", "IEX", "DARK_POOL"]
    CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF"]

    def __init__(self, seed: Optional[int] = None):
        if seed:
            random.seed(seed)

    def generate_trade_sequence(self, outcome: str = "success") -> List[Dict[str, Any]]:
        """
        Generate a trade lifecycle sequence.

        Args:
            outcome: success, partial_fill, rejected, cancelled
        """
        order_id = str(uuid.uuid4())[:8]
        account_id = f"ACC{random.randint(1000, 9999)}"
        symbol = random.choice(self.SYMBOLS)
        side = random.choice(["buy", "sell"])
        order_type = random.choice(["market", "limit", "stop"])
        quantity = random.randint(100, 10000)
        price = round(random.uniform(50, 500), 2) if order_type != "market" else None

        events = []
        ts = datetime.utcnow()

        # OrderSubmitted
        events.append({
            "event_type": "OrderSubmitted",
            "data": asdict(OrderSubmitted(
                order_id=order_id, account_id=account_id, symbol=symbol,
                side=side, order_type=order_type, quantity=quantity, price=price,
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(milliseconds=random.randint(10, 100))

        if outcome == "rejected":
            events.append({
                "event_type": "OrderRejected",
                "data": asdict(OrderRejected(
                    order_id=order_id, account_id=account_id,
                    rejection_reason=random.choice(["insufficient_margin", "position_limit_exceeded", "symbol_halted"]),
                    rejection_code=f"REJ{random.randint(100, 999)}",
                    timestamp=ts.isoformat()
                ))
            })
            return events

        # OrderValidated
        events.append({
            "event_type": "OrderValidated",
            "data": asdict(OrderValidated(
                order_id=order_id, account_id=account_id,
                validation_checks=["margin_check", "position_limit", "trading_allowed"],
                margin_available=round(random.uniform(10000, 1000000), 2),
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(milliseconds=random.randint(10, 50))

        # OrderRouted
        venue = random.choice(self.VENUES)
        events.append({
            "event_type": "OrderRouted",
            "data": asdict(OrderRouted(
                order_id=order_id, venue=venue, routed_quantity=quantity,
                routing_strategy=random.choice(["smart", "direct", "algo"]),
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(milliseconds=random.randint(50, 500))

        if outcome == "cancelled":
            filled_qty = random.randint(0, quantity // 2)
            if filled_qty > 0:
                events.append({
                    "event_type": "OrderPartiallyFilled",
                    "data": asdict(OrderPartiallyFilled(
                        order_id=order_id, fill_id=str(uuid.uuid4())[:8],
                        filled_quantity=filled_qty, remaining_quantity=quantity - filled_qty,
                        fill_price=price or round(random.uniform(50, 500), 2),
                        venue=venue, timestamp=ts.isoformat()
                    ))
                })
                ts += timedelta(seconds=random.randint(1, 30))

            events.append({
                "event_type": "OrderCancelled",
                "data": asdict(OrderCancelled(
                    order_id=order_id, cancelled_quantity=quantity - filled_qty,
                    filled_quantity=filled_qty,
                    cancel_reason=random.choice(["user_requested", "timeout", "market_close"]),
                    timestamp=ts.isoformat()
                ))
            })
            return events

        # Fills
        fill_price = price or round(random.uniform(50, 500), 2)
        if outcome == "partial_fill" or outcome == "success":
            remaining = quantity
            fills = []

            if outcome == "partial_fill" or random.random() > 0.5:
                # Multiple fills
                num_fills = random.randint(2, 4)
                for i in range(num_fills - 1):
                    fill_qty = random.randint(remaining // 4, remaining // 2)
                    remaining -= fill_qty
                    fills.append(fill_qty)
                    events.append({
                        "event_type": "OrderPartiallyFilled",
                        "data": asdict(OrderPartiallyFilled(
                            order_id=order_id, fill_id=str(uuid.uuid4())[:8],
                            filled_quantity=fill_qty, remaining_quantity=remaining,
                            fill_price=round(fill_price * random.uniform(0.999, 1.001), 2),
                            venue=venue, timestamp=ts.isoformat()
                        ))
                    })
                    ts += timedelta(milliseconds=random.randint(100, 2000))

            # Final fill
            fills.append(remaining)
            total_filled = sum(fills)
            avg_price = fill_price

            events.append({
                "event_type": "OrderFilled",
                "data": asdict(OrderFilled(
                    order_id=order_id, fill_id=str(uuid.uuid4())[:8],
                    total_quantity=total_filled, average_price=avg_price,
                    total_fills=len(fills), venue=venue, timestamp=ts.isoformat()
                ))
            })
            ts += timedelta(milliseconds=random.randint(100, 500))

        # TradeBooked
        trade_id = str(uuid.uuid4())[:8]
        trade_date = ts.strftime("%Y-%m-%d")
        settlement_date = (ts + timedelta(days=2)).strftime("%Y-%m-%d")

        events.append({
            "event_type": "TradeBooked",
            "data": asdict(TradeBooked(
                trade_id=trade_id, order_id=order_id, account_id=account_id,
                symbol=symbol, side=side, quantity=quantity, price=fill_price,
                trade_date=trade_date, settlement_date=settlement_date,
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(days=2)

        # TradeSettled
        events.append({
            "event_type": "TradeSettled",
            "data": asdict(TradeSettled(
                trade_id=trade_id, settlement_id=str(uuid.uuid4())[:8],
                settlement_status="settled", settled_quantity=quantity,
                settlement_amount=round(quantity * fill_price, 2),
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(hours=random.randint(1, 4))

        # TradeConfirmed
        events.append({
            "event_type": "TradeConfirmed",
            "data": asdict(TradeConfirmed(
                trade_id=trade_id, confirmation_id=str(uuid.uuid4())[:8],
                sent_to=random.choice(["email", "api", "swift"]),
                confirmed=True, timestamp=ts.isoformat()
            ))
        })

        return events

    def generate_payment_sequence(self, outcome: str = "success") -> List[Dict[str, Any]]:
        """Generate a payment processing sequence"""
        payment_id = str(uuid.uuid4())[:8]
        account_id = f"ACC{random.randint(1000, 9999)}"
        amount = round(random.uniform(1000, 1000000), 2)
        currency = random.choice(self.CURRENCIES)

        events = []
        ts = datetime.utcnow()

        # PaymentInitiated
        events.append({
            "event_type": "PaymentInitiated",
            "data": asdict(PaymentInitiated(
                payment_id=payment_id, account_id=account_id,
                amount=amount, currency=currency,
                payment_type=random.choice(["wire", "ach", "internal"]),
                beneficiary_id=f"BEN{random.randint(1000, 9999)}",
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(seconds=random.randint(1, 10))

        # PaymentValidated
        events.append({
            "event_type": "PaymentValidated",
            "data": asdict(PaymentValidated(
                payment_id=payment_id,
                validation_checks=["balance_check", "sanctions_check", "limit_check"],
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(seconds=random.randint(5, 30))

        # PaymentPendingApproval
        required_approvers = 2 if amount > 100000 else 1
        events.append({
            "event_type": "PaymentPendingApproval",
            "data": asdict(PaymentPendingApproval(
                payment_id=payment_id,
                approval_level="dual" if required_approvers > 1 else "single",
                required_approvers=required_approvers,
                current_approvals=0, timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(minutes=random.randint(5, 60))

        if outcome == "rejected":
            events.append({
                "event_type": "PaymentRejected",
                "data": asdict(PaymentRejected(
                    payment_id=payment_id,
                    rejector_id=f"USR{random.randint(100, 999)}",
                    rejection_reason=random.choice(["policy_violation", "incorrect_details", "suspicious_activity"]),
                    timestamp=ts.isoformat()
                ))
            })
            return events

        # PaymentApproved
        for i in range(required_approvers):
            events.append({
                "event_type": "PaymentApproved",
                "data": asdict(PaymentApproved(
                    payment_id=payment_id,
                    approver_id=f"USR{random.randint(100, 999)}",
                    approval_level=i + 1, timestamp=ts.isoformat()
                ))
            })
            ts += timedelta(minutes=random.randint(5, 30))

        # PaymentExecuted
        network = "swift" if currency != "USD" else random.choice(["fedwire", "ach"])
        events.append({
            "event_type": "PaymentExecuted",
            "data": asdict(PaymentExecuted(
                payment_id=payment_id,
                execution_ref=str(uuid.uuid4())[:12].upper(),
                network=network, status="sent", timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(hours=random.randint(1, 24))

        if outcome == "failed":
            events.append({
                "event_type": "PaymentFailed",
                "data": asdict(PaymentFailed(
                    payment_id=payment_id,
                    failure_reason=random.choice(["invalid_account", "network_error", "compliance_hold"]),
                    failure_code=f"FAIL{random.randint(100, 999)}",
                    timestamp=ts.isoformat()
                ))
            })
            return events

        # PaymentCompleted
        fees = round(amount * 0.001, 2)
        events.append({
            "event_type": "PaymentCompleted",
            "data": asdict(PaymentCompleted(
                payment_id=payment_id,
                completion_ref=str(uuid.uuid4())[:12].upper(),
                final_amount=amount, fees=fees, timestamp=ts.isoformat()
            ))
        })

        return events

    def generate_risk_sequence(self, outcome: str = "mitigated") -> List[Dict[str, Any]]:
        """Generate a risk management sequence"""
        alert_id = str(uuid.uuid4())[:8]
        account_id = f"ACC{random.randint(1000, 9999)}"

        events = []
        ts = datetime.utcnow()

        limit_value = round(random.uniform(100000, 10000000), 2)
        breach_pct = random.uniform(1.05, 1.5)
        current_value = round(limit_value * breach_pct, 2)

        # RiskLimitBreached
        events.append({
            "event_type": "RiskLimitBreached",
            "data": asdict(RiskLimitBreached(
                alert_id=alert_id, account_id=account_id,
                limit_type=random.choice(["var_limit", "position_limit", "loss_limit", "concentration"]),
                current_value=current_value, limit_value=limit_value,
                breach_percentage=round((breach_pct - 1) * 100, 2),
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(seconds=random.randint(1, 5))

        # RiskAlertCreated
        severity = "critical" if breach_pct > 1.3 else "high" if breach_pct > 1.15 else "medium"
        events.append({
            "event_type": "RiskAlertCreated",
            "data": asdict(RiskAlertCreated(
                alert_id=alert_id, severity=severity,
                alert_type="limit_breach",
                description=f"Risk limit breached by {round((breach_pct - 1) * 100, 1)}%",
                assigned_to=f"RISK{random.randint(1, 10)}",
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(minutes=random.randint(1, 15))

        # RiskAlertAcknowledged
        events.append({
            "event_type": "RiskAlertAcknowledged",
            "data": asdict(RiskAlertAcknowledged(
                alert_id=alert_id,
                acknowledged_by=f"RISK{random.randint(1, 10)}",
                notes="Investigating breach", timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(minutes=random.randint(5, 30))

        if outcome == "mitigated":
            mitigation_id = str(uuid.uuid4())[:8]

            events.append({
                "event_type": "RiskMitigationStarted",
                "data": asdict(RiskMitigationStarted(
                    alert_id=alert_id, mitigation_id=mitigation_id,
                    action_type=random.choice(["reduce_position", "add_hedge", "increase_margin"]),
                    target_reduction=round(current_value - limit_value * 0.9, 2),
                    timestamp=ts.isoformat()
                ))
            })
            ts += timedelta(minutes=random.randint(15, 120))

            events.append({
                "event_type": "RiskMitigationCompleted",
                "data": asdict(RiskMitigationCompleted(
                    alert_id=alert_id, mitigation_id=mitigation_id,
                    result="successful",
                    new_risk_value=round(limit_value * 0.85, 2),
                    timestamp=ts.isoformat()
                ))
            })
            ts += timedelta(minutes=random.randint(5, 15))

        # RiskAlertResolved
        resolution = "mitigated" if outcome == "mitigated" else random.choice(["accepted", "false_positive"])
        events.append({
            "event_type": "RiskAlertResolved",
            "data": asdict(RiskAlertResolved(
                alert_id=alert_id, resolution=resolution,
                resolved_by=f"RISK{random.randint(1, 10)}",
                timestamp=ts.isoformat()
            ))
        })

        return events

    def generate_compliance_sequence(self, outcome: str = "clear") -> List[Dict[str, Any]]:
        """Generate a compliance workflow sequence"""
        check_id = str(uuid.uuid4())[:8]
        entity_id = str(uuid.uuid4())[:8]

        events = []
        ts = datetime.utcnow()

        # ComplianceCheckTriggered
        events.append({
            "event_type": "ComplianceCheckTriggered",
            "data": asdict(ComplianceCheckTriggered(
                check_id=check_id,
                trigger_type=random.choice(["trade", "payment", "account_change"]),
                entity_type=random.choice(["trade", "account", "counterparty"]),
                entity_id=entity_id, timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(seconds=random.randint(1, 5))

        if outcome == "clear":
            events.append({
                "event_type": "ComplianceCheckPassed",
                "data": asdict(ComplianceCheckPassed(
                    check_id=check_id,
                    checks_performed=["aml", "sanctions", "pep", "kyc"],
                    timestamp=ts.isoformat()
                ))
            })
            return events

        # ComplianceFlagRaised
        flag_id = str(uuid.uuid4())[:8]
        events.append({
            "event_type": "ComplianceFlagRaised",
            "data": asdict(ComplianceFlagRaised(
                check_id=check_id, flag_id=flag_id,
                flag_type=random.choice(["sanctions_hit", "unusual_activity", "pep_match"]),
                severity=random.choice(["medium", "high"]),
                details="Potential match found - requires review",
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(minutes=random.randint(1, 10))

        # ComplianceReviewAssigned
        reviewer_id = f"COMP{random.randint(1, 20)}"
        events.append({
            "event_type": "ComplianceReviewAssigned",
            "data": asdict(ComplianceReviewAssigned(
                flag_id=flag_id, reviewer_id=reviewer_id,
                priority=random.choice(["medium", "high", "urgent"]),
                due_date=(ts + timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d"),
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(hours=random.randint(1, 48))

        if outcome == "escalated":
            events.append({
                "event_type": "ComplianceEscalated",
                "data": asdict(ComplianceEscalated(
                    flag_id=flag_id,
                    escalated_to=random.choice(["senior_compliance", "legal"]),
                    escalation_reason="Complex case requiring senior review",
                    timestamp=ts.isoformat()
                ))
            })
            ts += timedelta(hours=random.randint(4, 24))

        # ComplianceReviewCompleted
        events.append({
            "event_type": "ComplianceReviewCompleted",
            "data": asdict(ComplianceReviewCompleted(
                flag_id=flag_id, reviewer_id=reviewer_id,
                decision=random.choice(["clear", "escalate"]) if outcome != "escalated" else "clear",
                rationale="Review completed - no action required",
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(hours=random.randint(1, 4))

        # ComplianceCaseClosed
        events.append({
            "event_type": "ComplianceCaseClosed",
            "data": asdict(ComplianceCaseClosed(
                flag_id=flag_id,
                outcome=random.choice(["no_action", "warning"]),
                closed_by=reviewer_id, timestamp=ts.isoformat()
            ))
        })

        return events

    def generate_account_sequence(self, outcome: str = "opened") -> List[Dict[str, Any]]:
        """Generate an account opening sequence"""
        application_id = str(uuid.uuid4())[:8]

        events = []
        ts = datetime.utcnow()

        # AccountApplicationSubmitted
        events.append({
            "event_type": "AccountApplicationSubmitted",
            "data": asdict(AccountApplicationSubmitted(
                application_id=application_id,
                applicant_type=random.choice(["individual", "corporate"]),
                account_type=random.choice(["trading", "custody", "margin"]),
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(hours=random.randint(1, 24))

        # AccountKYCStarted
        kyc_id = str(uuid.uuid4())[:8]
        events.append({
            "event_type": "AccountKYCStarted",
            "data": asdict(AccountKYCStarted(
                application_id=application_id, kyc_id=kyc_id,
                documents_required=["passport", "utility_bill", "bank_statement"],
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(days=random.randint(1, 5))

        # Documents received
        for doc in ["passport", "utility_bill"]:
            events.append({
                "event_type": "AccountDocumentReceived",
                "data": asdict(AccountDocumentReceived(
                    application_id=application_id,
                    document_type=doc, document_status="verified",
                    timestamp=ts.isoformat()
                ))
            })
            ts += timedelta(days=random.randint(1, 3))

        # AccountKYCCompleted
        kyc_status = "approved" if outcome == "opened" else "rejected"
        events.append({
            "event_type": "AccountKYCCompleted",
            "data": asdict(AccountKYCCompleted(
                application_id=application_id,
                kyc_status=kyc_status,
                risk_rating=random.choice(["low", "medium"]),
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(hours=random.randint(1, 8))

        if outcome == "rejected":
            return events

        # AccountOpened
        account_id = f"ACC{random.randint(10000, 99999)}"
        events.append({
            "event_type": "AccountOpened",
            "data": asdict(AccountOpened(
                account_id=account_id, application_id=application_id,
                account_type="trading", initial_status="active",
                timestamp=ts.isoformat()
            ))
        })
        ts += timedelta(days=random.randint(1, 7))

        # AccountFunded
        events.append({
            "event_type": "AccountFunded",
            "data": asdict(AccountFunded(
                account_id=account_id,
                funding_amount=round(random.uniform(10000, 1000000), 2),
                funding_source=random.choice(["wire", "ach"]),
                timestamp=ts.isoformat()
            ))
        })

        return events

    def generate_dataset(self, num_sequences: int = 500) -> Tuple[List[Dict], Dict[str, List[Dict]]]:
        """
        Generate a complete dataset of process sequences.

        Returns:
            (all_events, sequences_by_stream)
        """
        all_events = []
        streams = {}

        # Distribution of sequence types
        generators = [
            (self.generate_trade_sequence, ["success", "success", "partial_fill", "rejected", "cancelled"]),
            (self.generate_payment_sequence, ["success", "success", "rejected", "failed"]),
            (self.generate_risk_sequence, ["mitigated", "mitigated", "accepted"]),
            (self.generate_compliance_sequence, ["clear", "clear", "flagged", "escalated"]),
            (self.generate_account_sequence, ["opened", "opened", "rejected"]),
        ]

        for i in range(num_sequences):
            generator, outcomes = random.choice(generators)
            outcome = random.choice(outcomes)
            events = generator(outcome)

            # Determine stream name
            if events:
                first_event = events[0]
                event_type = first_event["event_type"]
                data = first_event["data"]

                if "order_id" in data:
                    stream_name = f"trade-{data['order_id']}"
                elif "payment_id" in data:
                    stream_name = f"payment-{data['payment_id']}"
                elif "alert_id" in data:
                    stream_name = f"risk-{data['alert_id']}"
                elif "check_id" in data:
                    stream_name = f"compliance-{data['check_id']}"
                elif "application_id" in data:
                    stream_name = f"account-{data['application_id']}"
                else:
                    stream_name = f"process-{i}"

                streams[stream_name] = events
                all_events.extend(events)

        return all_events, streams


def create_prediction_training_data(
    streams: Dict[str, List[Dict]],
    output_path: str
) -> List[Dict]:
    """
    Create training data for next-event prediction.

    Each example: given N events, predict the (N+1)th event.
    """
    training_data = []

    SYSTEM_PROMPT = """You are a financial process prediction system. Given a sequence of events from a financial workflow, predict what event will happen next.

Event types you may encounter:
- Trade: OrderSubmitted → OrderValidated → OrderRouted → OrderFilled → TradeBooked → TradeSettled → TradeConfirmed
- Trade (rejected): OrderSubmitted → OrderRejected
- Payment: PaymentInitiated → PaymentValidated → PaymentPendingApproval → PaymentApproved → PaymentExecuted → PaymentCompleted
- Risk: RiskLimitBreached → RiskAlertCreated → RiskAlertAcknowledged → RiskMitigationStarted → RiskMitigationCompleted → RiskAlertResolved
- Compliance: ComplianceCheckTriggered → ComplianceCheckPassed (or ComplianceFlagRaised → ComplianceReviewAssigned → ...)
- Account: AccountApplicationSubmitted → AccountKYCStarted → AccountDocumentReceived → AccountKYCCompleted → AccountOpened → AccountFunded

Respond with ONLY the next event type name."""

    for stream_name, events in streams.items():
        if len(events) < 2:
            continue

        # Create examples for different positions in the sequence
        for i in range(1, len(events)):
            # Context: first i events
            context_events = events[:i]
            # Target: the next event
            next_event = events[i]

            # Format context
            context_lines = []
            for j, evt in enumerate(context_events, 1):
                context_lines.append(f"{j}. {evt['event_type']}")

            context = "\n".join(context_lines)
            target = next_event["event_type"]

            training_data.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Event sequence:\n{context}\n\nWhat is the next event?"},
                    {"role": "assistant", "content": target}
                ]
            })

            # Also create examples with more context (event details)
            if len(context_events) <= 3:
                detailed_context = []
                for j, evt in enumerate(context_events, 1):
                    evt_type = evt["event_type"]
                    data = evt["data"]
                    # Extract key fields
                    key_info = []
                    for k in ["order_id", "payment_id", "alert_id", "account_id", "status", "outcome"]:
                        if k in data:
                            key_info.append(f"{k}={data[k]}")
                    info_str = ", ".join(key_info[:3]) if key_info else ""
                    detailed_context.append(f"{j}. {evt_type}" + (f" ({info_str})" if info_str else ""))

                training_data.append({
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Event sequence:\n" + "\n".join(detailed_context) + "\n\nWhat is the next event?"},
                        {"role": "assistant", "content": target}
                    ]
                })

    # Save
    from pathlib import Path
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        for example in training_data:
            f.write(json.dumps(example) + "\n")

    print(f"Created {len(training_data)} training examples")
    print(f"Saved to: {output_path}")

    return training_data


if __name__ == "__main__":
    generator = ProcessEventGenerator(seed=42)
    all_events, streams = generator.generate_dataset(num_sequences=100)

    print(f"Generated {len(all_events)} events in {len(streams)} streams")

    training_data = create_prediction_training_data(
        streams,
        "output/data/process_prediction_train.jsonl"
    )
