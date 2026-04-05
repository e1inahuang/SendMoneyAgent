"""
SupportAgent — handles FAQs, exchange rates, transfer status, and general questions.
Routes back to send_money_agent if the user expresses a new transfer intent.
"""
import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

MODEL = LiteLlm(model="openai/gpt-4o-mini")

# ── Mock support tools ────────────────────────────────────────────────────────

from tools.slot_tools import SUPPORTED_COUNTRIES


def get_exchange_rate(country_code: str) -> dict:
    """Returns the current mock exchange rate for a destination country.

    Args:
        country_code: Two-letter country code (e.g. 'MX', 'CO').
    """
    rates = {
        "MX": {"currency": "MXN", "rate": 17.15, "fee": 2.99, "delivery": "1-3 business days"},
        "GT": {"currency": "GTQ", "rate": 7.75,  "fee": 2.99, "delivery": "1-3 business days"},
        "HN": {"currency": "HNL", "rate": 24.65, "fee": 2.99, "delivery": "2-5 business days"},
        "SV": {"currency": "USD", "rate": 1.00,  "fee": 1.99, "delivery": "Same day"},
        "DO": {"currency": "DOP", "rate": 58.50, "fee": 2.99, "delivery": "1-3 business days"},
        "CO": {"currency": "COP", "rate": 3950,  "fee": 2.99, "delivery": "1-3 business days"},
        "PE": {"currency": "PEN", "rate": 3.72,  "fee": 2.99, "delivery": "1-3 business days"},
        "EC": {"currency": "USD", "rate": 1.00,  "fee": 1.99, "delivery": "Same day"},
        "BO": {"currency": "BOB", "rate": 6.91,  "fee": 3.99, "delivery": "3-5 business days"},
        "NI": {"currency": "NIO", "rate": 36.60, "fee": 3.99, "delivery": "3-5 business days"},
    }
    code = country_code.upper().strip()
    if code not in rates:
        return {"error": f"No rate info for '{country_code}'.", "supported": list(rates.keys())}
    info = rates[code]
    return {
        "country": SUPPORTED_COUNTRIES.get(code, code),
        "country_code": code,
        "rate": f"1 USD = {info['rate']} {info['currency']}",
        "transfer_fee": f"${info['fee']} USD flat fee",
        "estimated_delivery": info["delivery"],
    }


def get_transfer_status(transaction_id: str) -> dict:
    """Look up the status of a past transfer by transaction ID (mock).

    Args:
        transaction_id: Felix transaction ID, e.g. FLX-20250401-ABCD1234.
    """
    if not transaction_id.startswith("FLX-"):
        return {"error": "Invalid transaction ID format. Expected FLX-YYYYMMDD-XXXXXXXX."}
    # Mock: all lookups return "in transit" for demo
    return {
        "transaction_id": transaction_id,
        "status": "IN_TRANSIT",
        "status_display": "💸 In Transit",
        "message": "Your transfer is on its way. Expected delivery within 1–3 business days.",
        "mock": True,
    }


def get_faqs(topic: str = "") -> dict:
    """Return frequently asked questions. Optionally filter by topic.

    Args:
        topic: Optional topic filter: 'fees', 'delivery', 'limits', 'security', 'countries'.
    """
    faqs = {
        "fees": "Felix charges a flat $2.99 fee per transfer. No hidden charges.",
        "delivery": (
            "Most transfers arrive in 1–3 business days. El Salvador and Ecuador "
            "(USD countries) are often same-day."
        ),
        "limits": "Minimum transfer: $1. Maximum: $10,000 per transaction.",
        "security": (
            "Felix uses 256-bit encryption. First-time recipients require identity "
            "confirmation. Transfers over $500 require extra confirmation."
        ),
        "countries": (
            "We currently support: Mexico, Guatemala, Honduras, El Salvador, "
            "Dominican Republic, Colombia, Peru, Ecuador, Bolivia, Nicaragua, "
            "Panama, and Venezuela."
        ),
        "cancel": "You can cancel any transfer before you confirm it. After confirmation, contact support.",
        "receipt": "A receipt is emailed to you immediately after every transfer.",
    }
    if topic and topic.lower() in faqs:
        return {"topic": topic, "answer": faqs[topic.lower()]}
    return {"faqs": faqs}


# ── Agent ─────────────────────────────────────────────────────────────────────

INSTRUCTION = """
You are Felix's support assistant. You help users with:
- Exchange rates and fees for any destination country
- Transfer delivery times
- Status of past transfers (by transaction ID)
- General FAQs (limits, security, cancellation, supported countries)

Be concise and friendly. If the user asks to SEND MONEY or expresses a transfer intent,
tell them "I'll connect you with the transfer flow!" and transfer to send_money_agent.

LANGUAGE: If the user writes in Spanish, respond bilingually
(English first, Spanish in italics below).
"""

support_agent = LlmAgent(
    name="support_agent",
    model=MODEL,
    description=(
        "Answers FAQs, looks up exchange rates and transfer status. "
        "Transfers back to send_money_agent when user wants to send money."
    ),
    instruction=INSTRUCTION,
    tools=[get_exchange_rate, get_transfer_status, get_faqs],
)
