"""
Slot filling tools for the Send Money flow.
Manages the transfer state: collecting, validating, and correcting slots.
"""
from google.adk.tools.tool_context import ToolContext

SUPPORTED_COUNTRIES = {
    "MX": "Mexico",
    "GT": "Guatemala",
    "HN": "Honduras",
    "SV": "El Salvador",
    "DO": "Dominican Republic",
    "CO": "Colombia",
    "PE": "Peru",
    "EC": "Ecuador",
    "BO": "Bolivia",
    "NI": "Nicaragua",
    "PA": "Panama",
    "VE": "Venezuela",
}

# Country name aliases for fuzzy matching
COUNTRY_ALIASES = {
    "mexico": "MX", "méjico": "MX", "mx": "MX",
    "guatemala": "GT", "gt": "GT",
    "honduras": "HN", "hn": "HN",
    "el salvador": "SV", "salvador": "SV", "sv": "SV",
    "dominican republic": "DO", "dominicana": "DO", "república dominicana": "DO", "do": "DO",
    "colombia": "CO", "co": "CO",
    "peru": "PE", "perú": "PE", "pe": "PE",
    "ecuador": "EC", "ec": "EC",
    "bolivia": "BO", "bo": "BO",
    "nicaragua": "NI", "ni": "NI",
    "panama": "PA", "panamá": "PA", "pa": "PA",
    "venezuela": "VE", "ve": "VE",
}

DELIVERY_METHODS_BY_COUNTRY = {
    "MX": ["bank_deposit", "cash_pickup", "mobile_wallet"],
    "GT": ["bank_deposit", "cash_pickup"],
    "HN": ["bank_deposit", "cash_pickup"],
    "SV": ["bank_deposit", "cash_pickup"],
    "DO": ["bank_deposit", "cash_pickup"],
    "CO": ["bank_deposit", "cash_pickup", "mobile_wallet"],
    "PE": ["bank_deposit", "cash_pickup"],
    "EC": ["bank_deposit", "cash_pickup"],
    "BO": ["cash_pickup"],
    "NI": ["cash_pickup"],
    "PA": ["bank_deposit", "cash_pickup"],
    "VE": ["cash_pickup"],
}

DELIVERY_METHOD_LABELS = {
    "bank_deposit": "🏦 Bank Deposit",
    "cash_pickup": "📍 Cash Pickup (40,000+ locations)",
    "mobile_wallet": "📱 Mobile Wallet",
}

POPULAR_BANKS = {
    "MX": ["BBVA Bancomer", "Banamex (Citibanamex)", "Banorte", "HSBC México", "Santander México"],
    "CO": ["Bancolombia", "Davivienda", "Banco de Bogotá", "Nequi", "Daviplata"],
    "GT": ["Banco Industrial", "Banrural", "BAC Guatemala"],
    "HN": ["Banco Atlántida", "BAC Honduras", "Banpaís"],
    "SV": ["Banco Agrícola", "Banco Cuscatlán", "BAC El Salvador"],
    "DO": ["Banco Popular Dominicano", "BanReservas", "Banco BHD León"],
    "PE": ["BCP", "Interbank", "BBVA Perú", "Yape"],
    "CO": ["Bancolombia", "Nequi", "Daviplata", "Davivienda"],
}

REQUIRED_SLOTS = [
    "recipient_name",
    "destination_country",
    "amount_usd",
    "delivery_method",
    "recipient_contact",
]


def get_supported_countries() -> dict:
    """Returns the list of supported destination countries for money transfers."""
    return {"countries": SUPPORTED_COUNTRIES}


def get_delivery_methods(country_code: str) -> dict:
    """Returns available delivery methods and popular banks for a given country.

    Args:
        country_code: Two-letter country code (e.g. 'MX', 'CO') or full name.
    """
    code = COUNTRY_ALIASES.get(country_code.lower().strip(), country_code.upper().strip())
    if code not in DELIVERY_METHODS_BY_COUNTRY:
        return {
            "error": f"Country '{country_code}' is not supported.",
            "supported_countries": SUPPORTED_COUNTRIES,
        }
    methods = DELIVERY_METHODS_BY_COUNTRY[code]
    result = {
        "country": SUPPORTED_COUNTRIES[code],
        "country_code": code,
        "delivery_methods": {m: DELIVERY_METHOD_LABELS[m] for m in methods},
    }
    if code in POPULAR_BANKS:
        result["popular_banks"] = POPULAR_BANKS[code]
    return result


def save_transfer_slot(slot_name: str, value: str, tool_context: ToolContext) -> dict:
    """Save a slot value for the current money transfer.

    Args:
        slot_name: One of: recipient_name, destination_country, amount_usd,
                   delivery_method, recipient_contact, requested_by, third_party_redirect.
        value: The value to save for this slot.
    """
    transfer = dict(tool_context.state.get("transfer", {}))

    # --- Reset if previous transfer is done (allows starting a fresh transfer) ---
    if transfer.get("status") in ("complete", "cancelled"):
        transfer = {"status": "collecting"}

    # --- Validate and normalize by slot type ---
    if slot_name == "destination_country":
        code = COUNTRY_ALIASES.get(value.lower().strip(), value.upper().strip())
        if code not in SUPPORTED_COUNTRIES:
            return {
                "error": f"'{value}' is not a supported destination country.",
                "supported_countries": SUPPORTED_COUNTRIES,
            }
        value = code

    elif slot_name == "amount_usd":
        cleaned = value.replace("$", "").replace(",", "").strip()
        try:
            amount = float(cleaned)
        except ValueError:
            return {"error": f"'{value}' is not a valid dollar amount."}
        if amount <= 0:
            return {"error": "Amount must be greater than $0."}
        if amount > 10000:
            return {"error": "Maximum transfer is $10,000 per transaction."}
        value = str(round(amount, 2))

    elif slot_name == "delivery_method":
        country = transfer.get("destination_country")
        valid = DELIVERY_METHODS_BY_COUNTRY.get(country, [])
        if value not in valid and value not in DELIVERY_METHOD_LABELS:
            return {
                "error": f"'{value}' is not available for {SUPPORTED_COUNTRIES.get(country, country)}.",
                "available_methods": valid,
            }

    transfer[slot_name] = value
    if "status" not in transfer:
        transfer["status"] = "collecting"
    tool_context.state["transfer"] = transfer

    return {
        "success": True,
        "saved": {slot_name: value},
        "transfer_state": transfer,
    }


def update_transfer_slot(slot_name: str, new_value: str, tool_context: ToolContext) -> dict:
    """Correct / update a previously saved slot value (e.g. user changes amount or recipient).

    Args:
        slot_name: The slot to update.
        new_value: The corrected value.
    """
    transfer = tool_context.state.get("transfer", {})
    old_value = transfer.get(slot_name, "not set")
    result = save_transfer_slot(slot_name, new_value, tool_context)
    if "error" in result:
        return result
    return {
        "success": True,
        "corrected": slot_name,
        "old_value": old_value,
        "new_value": new_value,
    }


def get_transfer_state(tool_context: ToolContext) -> dict:
    """Get the current transfer state: what has been collected, what is still missing."""
    transfer = tool_context.state.get("transfer", {})
    filled = {k: transfer[k] for k in REQUIRED_SLOTS if k in transfer and transfer[k]}
    missing = [k for k in REQUIRED_SLOTS if k not in filled]

    # Enrich display
    if "destination_country" in filled:
        filled["destination_country_name"] = SUPPORTED_COUNTRIES.get(
            filled["destination_country"], filled["destination_country"]
        )
    if "amount_usd" in filled:
        filled["amount_display"] = f"${float(filled['amount_usd']):,.2f}"

    return {
        "status": transfer.get("status", "idle"),
        "filled_slots": filled,
        "missing_slots": missing,
        "is_complete": len(missing) == 0,
        "third_party_redirect": transfer.get("third_party_redirect", False),
        "requested_by": transfer.get("requested_by"),
    }


def dismiss_felix(tool_context: ToolContext) -> dict:
    """Dismiss Felix after a completed transfer. Resets transfer state to idle
    so Felix returns to silent monitoring mode and stops responding to
    non-money messages.
    """
    tool_context.state["transfer"] = {"status": "idle"}
    tool_context.state["safety"] = {}
    tool_context.state["ui_component"] = None
    return {
        "success": True,
        "message": "Felix dismissed. Will reactivate on next money-related message.",
    }


def cancel_transfer(tool_context: ToolContext) -> dict:
    """Cancel the current transfer at any point and reset transfer state.
    No money is moved. Contact memory is preserved.
    """
    had_transfer = bool(tool_context.state.get("transfer", {}).get("recipient_name"))
    tool_context.state["transfer"] = {"status": "cancelled"}
    tool_context.state["safety"] = {}
    tool_context.state["ui_component"] = None
    return {
        "success": True,
        "message": "Transfer cancelled. No money was sent.",
        "had_active_transfer": had_transfer,
    }
