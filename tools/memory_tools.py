"""
Relationship memory tools.
Stores contact profiles (name, relationship, country, preferred delivery, history)
across the session so the agent can pre-fill slots and personalise messages.
"""
from datetime import datetime
from google.adk.tools.tool_context import ToolContext

# Relationship labels used for safety thresholds
HIGH_TRUST_RELATIONSHIPS = {"mother", "father", "parent", "spouse", "partner", "sibling",
                             "sister", "brother", "son", "daughter", "child", "grandparent",
                             "grandmother", "grandfather", "mamá", "papá", "esposo", "esposa"}


def get_contact(name: str, tool_context: ToolContext) -> dict:
    """Look up a contact by name (fuzzy). Returns their profile and transfer history.

    Args:
        name: Name or partial name to search for.
    """
    contacts: dict = tool_context.state.get("contacts", {})
    name_lower = name.lower().strip()

    # Exact match first
    if name_lower in {k.lower() for k in contacts}:
        for k, v in contacts.items():
            if k.lower() == name_lower:
                return {"found": True, "contact": {**v, "name": k}}

    # Partial / relationship match
    matches = []
    for contact_name, profile in contacts.items():
        if (name_lower in contact_name.lower()
                or name_lower in profile.get("relationship", "").lower()
                or name_lower in profile.get("nickname", "").lower()):
            matches.append({"name": contact_name, **profile})

    if len(matches) == 1:
        return {"found": True, "contact": matches[0]}
    if len(matches) > 1:
        return {"found": False, "multiple_matches": matches,
                "message": f"Multiple contacts match '{name}'. Please clarify."}

    return {"found": False, "message": f"No contact named '{name}' found in memory."}


def save_contact(
    name: str,
    tool_context: ToolContext,
    relationship: str = "",
    country_code: str = "",
    preferred_delivery: str = "",
    phone: str = "",
    nickname: str = "",
) -> dict:
    """Save or update a contact in relationship memory.

    Args:
        name: Full name of the contact.
        relationship: e.g. 'mother', 'sister', 'friend'.
        country_code: Destination country code e.g. 'MX'.
        preferred_delivery: e.g. 'bank_deposit'.
        phone: Phone number or bank account.
        nickname: Optional nickname / alias.
    """
    contacts: dict = dict(tool_context.state.get("contacts", {}))
    existing = contacts.get(name, {})

    contacts[name] = {
        **existing,
        "relationship": relationship or existing.get("relationship", ""),
        "country_code": country_code or existing.get("country_code", ""),
        "preferred_delivery": preferred_delivery or existing.get("preferred_delivery", ""),
        "phone": phone or existing.get("phone", ""),
        "nickname": nickname or existing.get("nickname", ""),
        "transfer_count": existing.get("transfer_count", 0),
        "last_transfer": existing.get("last_transfer"),
        "trusted": existing.get("trusted", False),
    }
    tool_context.state["contacts"] = contacts
    return {"success": True, "contact_saved": contacts[name]}


def record_successful_transfer(
    recipient_name: str,
    amount_usd: str,
    tool_context: ToolContext,
) -> dict:
    """Record a completed transfer in the contact's history and mark them as trusted.

    Args:
        recipient_name: Name of the recipient.
        amount_usd: Amount transferred (string, e.g. '200.0').
    """
    contacts: dict = dict(tool_context.state.get("contacts", {}))
    if recipient_name not in contacts:
        contacts[recipient_name] = {"transfer_count": 0, "trusted": False}

    contacts[recipient_name]["transfer_count"] = contacts[recipient_name].get("transfer_count", 0) + 1
    contacts[recipient_name]["last_transfer"] = datetime.now().strftime("%Y-%m-%d")
    contacts[recipient_name]["trusted"] = True
    tool_context.state["contacts"] = contacts
    return {"success": True, "updated": recipient_name,
            "total_transfers": contacts[recipient_name]["transfer_count"]}


def is_trusted_contact(name: str, tool_context: ToolContext) -> dict:
    """Check whether a recipient is a previously verified / trusted contact.

    Args:
        name: Name to check.
    """
    contacts: dict = tool_context.state.get("contacts", {})
    for contact_name, profile in contacts.items():
        if contact_name.lower() == name.lower().strip():
            is_trusted = profile.get("trusted", False)
            transfer_count = profile.get("transfer_count", 0)
            relationship = profile.get("relationship", "")
            high_trust_rel = relationship.lower() in HIGH_TRUST_RELATIONSHIPS
            return {
                "name": contact_name,
                "is_trusted": is_trusted,
                "is_first_time": transfer_count == 0,
                "transfer_count": transfer_count,
                "relationship": relationship,
                "high_trust_relationship": high_trust_rel,
            }
    return {
        "name": name,
        "is_trusted": False,
        "is_first_time": True,
        "transfer_count": 0,
        "relationship": "unknown",
        "high_trust_relationship": False,
    }


def list_all_contacts(tool_context: ToolContext) -> dict:
    """List all saved contacts and their profiles."""
    contacts: dict = tool_context.state.get("contacts", {})
    if not contacts:
        return {"contacts": [], "message": "No contacts saved yet."}
    summary = [
        {
            "name": name,
            "relationship": p.get("relationship", ""),
            "country": p.get("country_code", ""),
            "transfers": p.get("transfer_count", 0),
            "trusted": p.get("trusted", False),
        }
        for name, p in contacts.items()
    ]
    return {"contacts": summary, "total": len(summary)}


def seed_demo_contacts(tool_context: ToolContext) -> dict:
    """Seed the session with demo contacts for the interview presentation."""
    demo_contacts = {
        "Maria": {
            "relationship": "mother",
            "country_code": "MX",
            "preferred_delivery": "bank_deposit",
            "phone": "+52-55-1234-5678",
            "nickname": "mamá",
            "transfer_count": 12,
            "last_transfer": "2025-03-15",
            "trusted": True,
        },
        "Ana": {
            "relationship": "sister",
            "country_code": "MX",
            "preferred_delivery": "mobile_wallet",
            "phone": "+52-55-8765-4321",
            "nickname": "hermana",
            "transfer_count": 4,
            "last_transfer": "2025-01-20",
            "trusted": True,
        },
        "Carlos": {
            "relationship": "friend",
            "country_code": "CO",
            "preferred_delivery": "cash_pickup",
            "phone": "+57-300-123-4567",
            "nickname": "",
            "transfer_count": 0,
            "last_transfer": None,
            "trusted": False,
        },
    }
    tool_context.state["contacts"] = demo_contacts
    return {"success": True, "seeded": list(demo_contacts.keys())}
