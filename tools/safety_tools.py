"""
Safety and compliance tools.
Enforces identity verification for first-time recipients,
large-amount confirmation (>$500), and third-party transfer warnings.
"""
from google.adk.tools.tool_context import ToolContext

LARGE_AMOUNT_THRESHOLD = 500.0


def run_safety_checks(tool_context: ToolContext) -> dict:
    """Evaluate all safety requirements for the current transfer.

    Returns a list of checks that must be confirmed before proceeding.
    Call this after all slots are filled, before showing the summary.
    """
    transfer = tool_context.state.get("transfer", {})
    safety = dict(tool_context.state.get("safety", {}))
    contacts = tool_context.state.get("contacts", {})

    required_confirmations = []

    recipient = transfer.get("recipient_name", "")
    amount_str = transfer.get("amount_usd", "0")
    is_third_party = transfer.get("third_party_redirect", False)

    try:
        amount = float(amount_str)
    except (ValueError, TypeError):
        amount = 0.0

    # Check 1: First-time recipient
    contact_data = contacts.get(recipient, {})
    transfer_count = contact_data.get("transfer_count", 0)
    is_first_time = transfer_count == 0

    if is_first_time and not safety.get("identity_confirmed", False):
        required_confirmations.append({
            "type": "first_time_recipient",
            "priority": "high",
            "message": (
                f"⚠️ This is your first time sending money to **{recipient}**. "
                "Before proceeding, can you confirm you know this person and have "
                "verified their identity?"
            ),
            "message_es": (
                f"⚠️ Es la primera vez que le envías dinero a **{recipient}**. "
                "Antes de continuar, ¿puedes confirmar que conoces a esta persona "
                "y has verificado su identidad?"
            ),
            "state_key": "identity_confirmed",
        })

    # Check 2: Large amount (>$500)
    if amount > LARGE_AMOUNT_THRESHOLD and not safety.get("large_amount_confirmed", False):
        required_confirmations.append({
            "type": "large_amount",
            "priority": "medium",
            "message": (
                f"💰 You're about to send **${amount:,.2f}** — this is above our "
                f"${LARGE_AMOUNT_THRESHOLD:,.0f} threshold. Please confirm you "
                "intended this amount."
            ),
            "message_es": (
                f"💰 Estás a punto de enviar **${amount:,.2f}** — esto supera nuestro "
                f"límite de ${LARGE_AMOUNT_THRESHOLD:,.0f}. Por favor confirma que "
                "esta cantidad es correcta."
            ),
            "state_key": "large_amount_confirmed",
        })

    # Check 3: Third-party redirect (someone else asked user to send to a third party)
    if is_third_party and not safety.get("third_party_confirmed", False):
        requested_by = transfer.get("requested_by", "someone")
        required_confirmations.append({
            "type": "third_party_redirect",
            "priority": "high",
            "message": (
                f"🔄 **{requested_by}** is asking you to send money to "
                f"**{recipient}**. Please confirm this is intentional and you trust "
                "both parties."
            ),
            "message_es": (
                f"🔄 **{requested_by}** te está pidiendo que le envíes dinero a "
                f"**{recipient}**. Confirma que esto es intencional y confías en "
                "ambas personas."
            ),
            "state_key": "third_party_confirmed",
        })

    tool_context.state["safety"] = safety
    all_clear = len(required_confirmations) == 0

    return {
        "all_clear": all_clear,
        "required_confirmations": required_confirmations,
        "checks_passed": {
            "identity_confirmed": safety.get("identity_confirmed", False) or not is_first_time,
            "large_amount_ok": safety.get("large_amount_confirmed", False) or amount <= LARGE_AMOUNT_THRESHOLD,
            "third_party_ok": safety.get("third_party_confirmed", False) or not is_third_party,
        },
    }


def confirm_safety_check(check_type: str, tool_context: ToolContext) -> dict:
    """Mark a specific safety check as confirmed by the user.

    Args:
        check_type: One of: 'first_time_recipient', 'large_amount', 'third_party_redirect'.
    """
    safety = dict(tool_context.state.get("safety", {}))

    state_key_map = {
        "first_time_recipient": "identity_confirmed",
        "large_amount": "large_amount_confirmed",
        "third_party_redirect": "third_party_confirmed",
    }

    key = state_key_map.get(check_type)
    if not key:
        return {"error": f"Unknown check type: {check_type}"}

    safety[key] = True
    tool_context.state["safety"] = safety
    return {"success": True, "confirmed": check_type, "safety_state": safety}


def flag_third_party_request(
    requested_by: str,
    recipient_name: str,
    tool_context: ToolContext,
) -> dict:
    """Flag this transfer as a third-party redirect and record who initiated it.

    Args:
        requested_by: The contact who asked the user to send money to someone else.
        recipient_name: The third party who will receive the money.
    """
    transfer = dict(tool_context.state.get("transfer", {}))
    transfer["third_party_redirect"] = True
    transfer["requested_by"] = requested_by
    transfer["recipient_name"] = recipient_name
    if "status" not in transfer:
        transfer["status"] = "collecting"
    tool_context.state["transfer"] = transfer
    return {
        "success": True,
        "flagged_as_third_party": True,
        "requested_by": requested_by,
        "recipient": recipient_name,
    }
