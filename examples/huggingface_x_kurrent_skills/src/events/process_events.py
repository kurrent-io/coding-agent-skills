"""
Financial Process Events for Event Sequence Prediction

These events model realistic financial workflows where KurrentDB shines:
1. Trade Lifecycle - order to settlement
2. Payment Processing - initiation to confirmation
3. Risk Management - detection to resolution
4. Compliance Workflow - flag to resolution
5. Account Management - opening to closure

The model will learn to predict: "Given these events, what happens next?"
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum
import json
import uuid


# =============================================================================
# TRADE LIFECYCLE EVENTS
# =============================================================================

@dataclass
class OrderSubmitted:
    """Trade order submitted to the system"""
    order_id: str
    account_id: str
    symbol: str
    side: str  # buy, sell
    order_type: str  # market, limit, stop
    quantity: float
    price: Optional[float]  # None for market orders
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OrderValidated:
    """Order passed validation checks"""
    order_id: str
    account_id: str
    validation_checks: List[str]  # margin_check, position_limit, trading_allowed
    margin_available: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class OrderRejected:
    """Order rejected due to validation failure"""
    order_id: str
    account_id: str
    rejection_reason: str  # insufficient_margin, position_limit_exceeded, symbol_halted
    rejection_code: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class OrderRouted:
    """Order routed to exchange/venue"""
    order_id: str
    venue: str  # NYSE, NASDAQ, dark_pool
    routed_quantity: float
    routing_strategy: str  # smart, direct, algo
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class OrderPartiallyFilled:
    """Order partially executed"""
    order_id: str
    fill_id: str
    filled_quantity: float
    remaining_quantity: float
    fill_price: float
    venue: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class OrderFilled:
    """Order fully executed"""
    order_id: str
    fill_id: str
    total_quantity: float
    average_price: float
    total_fills: int
    venue: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class OrderCancelled:
    """Order cancelled before full execution"""
    order_id: str
    cancelled_quantity: float
    filled_quantity: float
    cancel_reason: str  # user_requested, timeout, market_close
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class TradeBooked:
    """Trade booked in the system"""
    trade_id: str
    order_id: str
    account_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    trade_date: str
    settlement_date: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class TradeSettled:
    """Trade settled - securities and cash exchanged"""
    trade_id: str
    settlement_id: str
    settlement_status: str  # settled, failed, partial
    settled_quantity: float
    settlement_amount: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class TradeConfirmed:
    """Trade confirmation sent to client"""
    trade_id: str
    confirmation_id: str
    sent_to: str  # email, api, swift
    confirmed: bool
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# =============================================================================
# PAYMENT PROCESSING EVENTS
# =============================================================================

@dataclass
class PaymentInitiated:
    """Payment request initiated"""
    payment_id: str
    account_id: str
    amount: float
    currency: str
    payment_type: str  # wire, ach, internal
    beneficiary_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PaymentValidated:
    """Payment passed validation"""
    payment_id: str
    validation_checks: List[str]  # balance_check, sanctions_check, limit_check
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PaymentPendingApproval:
    """Payment requires approval"""
    payment_id: str
    approval_level: str  # auto, single, dual
    required_approvers: int
    current_approvals: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PaymentApproved:
    """Payment approved"""
    payment_id: str
    approver_id: str
    approval_level: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PaymentRejected:
    """Payment rejected"""
    payment_id: str
    rejector_id: str
    rejection_reason: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PaymentExecuted:
    """Payment sent to payment network"""
    payment_id: str
    execution_ref: str
    network: str  # swift, fedwire, ach
    status: str  # sent, pending, failed
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PaymentCompleted:
    """Payment confirmed by receiving bank"""
    payment_id: str
    completion_ref: str
    final_amount: float
    fees: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class PaymentFailed:
    """Payment failed"""
    payment_id: str
    failure_reason: str  # insufficient_funds, invalid_account, network_error
    failure_code: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# =============================================================================
# RISK MANAGEMENT EVENTS
# =============================================================================

@dataclass
class RiskLimitBreached:
    """Risk limit breached"""
    alert_id: str
    account_id: str
    limit_type: str  # var_limit, position_limit, loss_limit, concentration
    current_value: float
    limit_value: float
    breach_percentage: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RiskAlertCreated:
    """Risk alert created for review"""
    alert_id: str
    severity: str  # low, medium, high, critical
    alert_type: str
    description: str
    assigned_to: Optional[str]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RiskAlertAcknowledged:
    """Risk alert acknowledged by risk manager"""
    alert_id: str
    acknowledged_by: str
    notes: Optional[str]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RiskMitigationStarted:
    """Risk mitigation action started"""
    alert_id: str
    mitigation_id: str
    action_type: str  # reduce_position, add_hedge, increase_margin, trading_halt
    target_reduction: Optional[float]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RiskMitigationCompleted:
    """Risk mitigation completed"""
    alert_id: str
    mitigation_id: str
    result: str  # successful, partial, failed
    new_risk_value: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class RiskAlertResolved:
    """Risk alert resolved"""
    alert_id: str
    resolution: str  # mitigated, accepted, false_positive
    resolved_by: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# =============================================================================
# COMPLIANCE WORKFLOW EVENTS
# =============================================================================

@dataclass
class ComplianceCheckTriggered:
    """Compliance check triggered"""
    check_id: str
    trigger_type: str  # trade, payment, account_change, periodic
    entity_type: str  # trade, account, counterparty
    entity_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ComplianceCheckPassed:
    """Compliance check passed"""
    check_id: str
    checks_performed: List[str]  # aml, sanctions, pep, kyc
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ComplianceFlagRaised:
    """Compliance flag raised for review"""
    check_id: str
    flag_id: str
    flag_type: str  # sanctions_hit, unusual_activity, pep_match, threshold_breach
    severity: str
    details: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ComplianceReviewAssigned:
    """Compliance review assigned to analyst"""
    flag_id: str
    reviewer_id: str
    priority: str  # low, medium, high, urgent
    due_date: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ComplianceReviewCompleted:
    """Compliance review completed"""
    flag_id: str
    reviewer_id: str
    decision: str  # clear, escalate, sar_filed, block
    rationale: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ComplianceEscalated:
    """Compliance issue escalated"""
    flag_id: str
    escalated_to: str  # senior_compliance, legal, regulator
    escalation_reason: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ComplianceCaseClosed:
    """Compliance case closed"""
    flag_id: str
    outcome: str  # no_action, warning, restriction, termination, sar
    closed_by: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# =============================================================================
# ACCOUNT MANAGEMENT EVENTS
# =============================================================================

@dataclass
class AccountApplicationSubmitted:
    """New account application"""
    application_id: str
    applicant_type: str  # individual, corporate, institutional
    account_type: str  # trading, custody, margin
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class AccountKYCStarted:
    """KYC process started"""
    application_id: str
    kyc_id: str
    documents_required: List[str]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class AccountDocumentReceived:
    """Document received for KYC"""
    application_id: str
    document_type: str  # passport, utility_bill, incorporation_cert
    document_status: str  # received, verified, rejected
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class AccountKYCCompleted:
    """KYC completed"""
    application_id: str
    kyc_status: str  # approved, rejected, pending_info
    risk_rating: str  # low, medium, high
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class AccountOpened:
    """Account opened"""
    account_id: str
    application_id: str
    account_type: str
    initial_status: str  # active, restricted
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class AccountFunded:
    """Account received initial funding"""
    account_id: str
    funding_amount: float
    funding_source: str  # wire, ach, transfer
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class AccountStatusChanged:
    """Account status changed"""
    account_id: str
    old_status: str
    new_status: str  # active, suspended, restricted, closed
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# =============================================================================
# EVENT REGISTRY
# =============================================================================

# Process definitions for sequence generation
PROCESS_FLOWS = {
    "trade_success": [
        "OrderSubmitted", "OrderValidated", "OrderRouted",
        "OrderFilled", "TradeBooked", "TradeSettled", "TradeConfirmed"
    ],
    "trade_partial_fill": [
        "OrderSubmitted", "OrderValidated", "OrderRouted",
        "OrderPartiallyFilled", "OrderPartiallyFilled", "OrderFilled",
        "TradeBooked", "TradeSettled", "TradeConfirmed"
    ],
    "trade_rejected": [
        "OrderSubmitted", "OrderRejected"
    ],
    "trade_cancelled": [
        "OrderSubmitted", "OrderValidated", "OrderRouted",
        "OrderPartiallyFilled", "OrderCancelled"
    ],
    "payment_success": [
        "PaymentInitiated", "PaymentValidated", "PaymentPendingApproval",
        "PaymentApproved", "PaymentExecuted", "PaymentCompleted"
    ],
    "payment_rejected": [
        "PaymentInitiated", "PaymentValidated", "PaymentPendingApproval",
        "PaymentRejected"
    ],
    "payment_failed": [
        "PaymentInitiated", "PaymentValidated", "PaymentPendingApproval",
        "PaymentApproved", "PaymentExecuted", "PaymentFailed"
    ],
    "risk_mitigated": [
        "RiskLimitBreached", "RiskAlertCreated", "RiskAlertAcknowledged",
        "RiskMitigationStarted", "RiskMitigationCompleted", "RiskAlertResolved"
    ],
    "risk_accepted": [
        "RiskLimitBreached", "RiskAlertCreated", "RiskAlertAcknowledged",
        "RiskAlertResolved"
    ],
    "compliance_clear": [
        "ComplianceCheckTriggered", "ComplianceCheckPassed"
    ],
    "compliance_flagged_cleared": [
        "ComplianceCheckTriggered", "ComplianceFlagRaised",
        "ComplianceReviewAssigned", "ComplianceReviewCompleted", "ComplianceCaseClosed"
    ],
    "compliance_escalated": [
        "ComplianceCheckTriggered", "ComplianceFlagRaised",
        "ComplianceReviewAssigned", "ComplianceEscalated",
        "ComplianceReviewCompleted", "ComplianceCaseClosed"
    ],
    "account_opened": [
        "AccountApplicationSubmitted", "AccountKYCStarted",
        "AccountDocumentReceived", "AccountDocumentReceived",
        "AccountKYCCompleted", "AccountOpened", "AccountFunded"
    ],
    "account_rejected": [
        "AccountApplicationSubmitted", "AccountKYCStarted",
        "AccountDocumentReceived", "AccountKYCCompleted"  # with rejected status
    ],
}

# All event types for reference
ALL_EVENT_TYPES = [
    # Trade
    "OrderSubmitted", "OrderValidated", "OrderRejected", "OrderRouted",
    "OrderPartiallyFilled", "OrderFilled", "OrderCancelled",
    "TradeBooked", "TradeSettled", "TradeConfirmed",
    # Payment
    "PaymentInitiated", "PaymentValidated", "PaymentPendingApproval",
    "PaymentApproved", "PaymentRejected", "PaymentExecuted",
    "PaymentCompleted", "PaymentFailed",
    # Risk
    "RiskLimitBreached", "RiskAlertCreated", "RiskAlertAcknowledged",
    "RiskMitigationStarted", "RiskMitigationCompleted", "RiskAlertResolved",
    # Compliance
    "ComplianceCheckTriggered", "ComplianceCheckPassed", "ComplianceFlagRaised",
    "ComplianceReviewAssigned", "ComplianceReviewCompleted",
    "ComplianceEscalated", "ComplianceCaseClosed",
    # Account
    "AccountApplicationSubmitted", "AccountKYCStarted", "AccountDocumentReceived",
    "AccountKYCCompleted", "AccountOpened", "AccountFunded", "AccountStatusChanged",
]
