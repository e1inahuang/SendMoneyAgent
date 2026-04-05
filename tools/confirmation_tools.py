"""
Confirmation and receipt tools.
Builds the transfer summary card, executes the mock transfer,
and sends a mock email receipt.
"""
import os
import uuid
from datetime import datetime
from google.adk.tools.tool_context import ToolContext

from tools.slot_tools import SUPPORTED_COUNTRIES, DELIVERY_METHOD_LABELS

USER_EMAIL = os.getenv("USER_EMAIL", "huangytelina@gmail.com")

FX_RATES = {
    "MX": {"currency": "MXN", "rate": 17.15, "symbol": "$"},
    "GT": {"currency": "GTQ", "rate": 7.75, "symbol": "Q"},
    "HN": {"currency": "HNL", "rate": 24.65, "symbol": "L"},
    "SV": {"currency": "USD", "rate": 1.0, "symbol": "$"},
    "DO": {"currency": "DOP", "rate": 58.50, "symbol": "RD$"},
    "CO": {"currency": "COP", "rate": 3950.0, "symbol": "$"},
    "PE": {"currency": "PEN", "rate": 3.72, "symbol": "S/"},
    "EC": {"currency": "USD", "rate": 1.0, "symbol": "$"},
    "BO": {"currency": "BOB", "rate": 6.91, "symbol": "Bs"},
    "NI": {"currency": "NIO", "rate": 36.60, "symbol": "C$"},
    "PA": {"currency": "PAB", "rate": 1.0, "symbol": "B/."},
    "VE": {"currency": "VES", "rate": 36.50, "symbol": "Bs."},
}

TRANSFER_FEE = 2.99  # flat fee for demo


def build_transfer_summary(tool_context: ToolContext) -> dict:
    """Build the full transfer summary to show the user before confirmation.
    Also stores a UI component in state for the frontend to render a summary card.
    """
    transfer = tool_context.state.get("transfer", {})

    recipient = transfer.get("recipient_name", "Unknown")
    country_code = transfer.get("destination_country", "")
    country_name = SUPPORTED_COUNTRIES.get(country_code, country_code)
    amount_str = transfer.get("amount_usd", "0")
    delivery = transfer.get("delivery_method", "")
    contact = transfer.get("recipient_contact", "")
    requested_by = transfer.get("requested_by")

    try:
        amount_usd = float(amount_str)
    except (ValueError, TypeError):
        amount_usd = 0.0

    # FX calculation
    fx = FX_RATES.get(country_code, {"currency": "LOCAL", "rate": 1.0, "symbol": ""})
    amount_local = round(amount_usd * fx["rate"], 2)
    total_deducted = amount_usd + TRANSFER_FEE

    summary = {
        "recipient_name": recipient,
        "destination_country": country_name,
        "country_code": country_code,
        "amount_usd": amount_usd,
        "amount_display": f"${amount_usd:,.2f} USD",
        "total_deducted": f"${total_deducted:,.2f} USD (incl. ${TRANSFER_FEE:.2f} fee)",
        "amount_local": f"{fx['symbol']}{amount_local:,.2f} {fx['currency']}",
        "exchange_rate": f"1 USD = {fx['rate']} {fx['currency']}",
        "delivery_method": DELIVERY_METHOD_LABELS.get(delivery, delivery),
        "delivery_method_key": delivery,
        "recipient_contact": contact,
        "requested_by": requested_by,
        "is_third_party": bool(requested_by),
        "estimated_delivery": "Within 1-3 business days",
    }

    # Store UI component for frontend
    tool_context.state["ui_component"] = {
        "type": "transfer_summary",
        "data": summary,
    }

    # Update transfer status
    current_transfer = dict(tool_context.state.get("transfer", {}))
    current_transfer["status"] = "confirming"
    tool_context.state["transfer"] = current_transfer

    return {"summary": summary, "status": "awaiting_confirmation"}


def execute_transfer(tool_context: ToolContext) -> dict:
    """Execute the mock transfer after user confirmation.
    Generates a transaction ID and marks the transfer as complete.
    """
    transfer = tool_context.state.get("transfer", {})

    tx_id = f"FLX-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    receipt = {
        "transaction_id": tx_id,
        "status": "SUCCESS",
        "timestamp": timestamp,
        "recipient_name": transfer.get("recipient_name"),
        "destination_country": SUPPORTED_COUNTRIES.get(
            transfer.get("destination_country", ""), transfer.get("destination_country", "")
        ),
        "amount_usd": transfer.get("amount_usd"),
        "delivery_method": DELIVERY_METHOD_LABELS.get(
            transfer.get("delivery_method", ""), transfer.get("delivery_method", "")
        ),
        "recipient_contact": transfer.get("recipient_contact"),
        "fee": f"${TRANSFER_FEE:.2f}",
        "email_receipt_sent_to": USER_EMAIL,
    }

    # Store receipt as UI component
    tool_context.state["ui_component"] = {
        "type": "transfer_receipt",
        "data": receipt,
    }

    # Mark complete and save receipt
    current_transfer = dict(tool_context.state.get("transfer", {}))
    current_transfer["status"] = "complete"
    current_transfer["transaction_id"] = tx_id
    tool_context.state["transfer"] = current_transfer
    tool_context.state["last_receipt"] = receipt

    return {"success": True, "receipt": receipt}


def send_email_receipt(tool_context: ToolContext) -> dict:
    """Send a mock email receipt to the user after a successful transfer.
    In production this would call an email service (SendGrid, SES, etc.).
    """
    receipt = tool_context.state.get("last_receipt", {})
    if not receipt:
        return {"error": "No completed transfer found to send receipt for."}

    # Mock email — in production: call email API here
    email_body = f"""
    Subject: ✅ Felix Transfer Confirmed — {receipt.get('transaction_id')}

    Hi there,

    Your transfer has been successfully initiated.

    ──────────────────────────────
    Transaction ID : {receipt.get('transaction_id')}
    Recipient      : {receipt.get('recipient_name')}
    Country        : {receipt.get('destination_country')}
    Amount         : ${receipt.get('amount_usd')} USD
    Delivery       : {receipt.get('delivery_method')}
    Date           : {receipt.get('timestamp')}
    ──────────────────────────────

    Estimated delivery: 1–3 business days.
    Questions? Reply to this email or message us on WhatsApp.

    — The Felix Team
    """

    print(f"\n[MOCK EMAIL] → {USER_EMAIL}\n{email_body}\n")

    return {
        "success": True,
        "email_sent_to": USER_EMAIL,
        "transaction_id": receipt.get("transaction_id"),
        "mock": True,
    }
