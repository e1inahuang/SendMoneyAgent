"""
FastAPI server for the Felix Send Money Agent.
Wraps the ADK runner and exposes a simple REST API for the WhatsApp UI.
"""
import os
import re
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from tools.slot_tools import (
    save_transfer_slot, SUPPORTED_COUNTRIES, COUNTRY_ALIASES,
    REQUIRED_SLOTS, DELIVERY_METHODS_BY_COUNTRY,
)
from tools.safety_tools import run_safety_checks, confirm_safety_check
from tools.confirmation_tools import execute_transfer, send_email_receipt
from tools.memory_tools import record_successful_transfer

# ── Bootstrap ──────────────────────────────────────────────────────────────────
from agents.orchestrator import root_agent

APP_NAME = os.getenv("APP_NAME", "felix_send_money")
USER_ID = "demo_user"

session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

class _MockCtx:
    """Minimal mock ToolContext for calling tool functions outside the agent."""
    def __init__(self, state):
        self.state = state


def _get_storage_session(session_id: str):
    """Get the ACTUAL stored session (not a deep copy).
    InMemorySessionService.get_session() returns a deepcopy, so direct
    mutations don't persist. This accesses internal storage directly.
    """
    return (
        session_service.sessions
        .get(APP_NAME, {})
        .get(USER_ID, {})
        .get(session_id)
    )


# ── Money regex patterns (compiled once) ──────────────────────────────────────

_MONEY_KEYWORDS = re.compile(
    r'\b(?:send|transfer|money|wire|pay|payment|dollars|usd|'
    r'mandar|enviar|dinero|plata|transferir|pagar)\b',
    re.IGNORECASE,
)
_DOLLAR_AMOUNT = re.compile(
    r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)'       # $200, $1,000.50
    r'|(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:usd|dollars?|bucks)'  # 200 usd
    r'|(?:send|transfer|pay|enviar|mandar)\s+(?:(?:me|us)\s+)?(?:\w+\s+){0,2}?(\d+(?:,\d{3})*(?:\.\d+)?)'  # send [me] [additional] 200
    r'|(?:additional|another|extra|more|otro|más)\s+(\d+(?:,\d{3})*(?:\.\d+)?)'  # additional 800
    , re.IGNORECASE,
)
_PHONE_NUMBER = re.compile(r'(\+?\d[\d\s\-]{7,}\d)')

# Delivery method keywords — longer phrases checked first
_DELIVERY_KEYWORDS = [
    ("bank deposit", "bank_deposit"),
    ("bank", "bank_deposit"),
    ("cash pickup", "cash_pickup"),
    ("cash pick up", "cash_pickup"),
    ("cash", "cash_pickup"),
    ("mobile wallet", "mobile_wallet"),
    ("wallet", "mobile_wallet"),
]


def _detect_money_intent(text: str) -> bool:
    """Check if a message is money-related using regex (no LLM)."""
    if _MONEY_KEYWORDS.search(text):
        return True
    if _DOLLAR_AMOUNT.search(text):
        return True
    return False


def _extract_and_fill_slots(session, message: str, sender_role: str, sender_name: str | None):
    """Deterministic slot extraction from message text only.
    Mutates session.state directly (must be called with storage session).
    Returns the updated transfer dict.
    """
    transfer = session.state.get("transfer", {})
    status = transfer.get("status", "idle")

    # Start fresh if previous transfer is done
    if status in ("complete", "cancelled") or status == "idle":
        transfer = {"status": "collecting"}
        session.state["transfer"] = transfer
        session.state["safety"] = {}

    ctx = _MockCtx(session.state)

    # 1. Extract recipient_name from conversation context
    if not transfer.get("recipient_name") and sender_name:
        save_transfer_slot("recipient_name", sender_name, ctx)

    # 2. Look up contact memory → pre-fill country, delivery, phone
    # Re-read transfer since save_transfer_slot replaces the dict
    transfer = session.state.get("transfer", {})
    recipient = transfer.get("recipient_name")
    if recipient:
        contacts = session.state.get("contacts", {})
        contact = contacts.get(recipient, {})
        if contact:
            if not transfer.get("destination_country") and contact.get("country_code"):
                cc = contact["country_code"]
                if cc in SUPPORTED_COUNTRIES:
                    save_transfer_slot("destination_country", cc, ctx)
            if not transfer.get("delivery_method") and contact.get("preferred_delivery"):
                save_transfer_slot("delivery_method", contact["preferred_delivery"], ctx)
            if not transfer.get("recipient_contact") and contact.get("phone"):
                save_transfer_slot("recipient_contact", contact["phone"], ctx)

    # Re-read transfer after contact pre-fill
    transfer = session.state.get("transfer", {})

    # 3. Extract amount_usd (first match, NOT additive)
    m = _DOLLAR_AMOUNT.search(message)
    if m:
        raw = next(g for g in m.groups() if g is not None)
        raw = raw.replace(",", "")
        try:
            amount = float(raw)
            if 0 < amount <= 10000:
                save_transfer_slot("amount_usd", str(amount), ctx)
        except ValueError:
            pass

    # 4. Extract destination_country from message text
    msg_lower = message.lower()
    for alias, code in sorted(COUNTRY_ALIASES.items(), key=lambda x: -len(x[0])):
        # Match as whole word to avoid partial matches
        if re.search(r'\b' + re.escape(alias) + r'\b', msg_lower):
            save_transfer_slot("destination_country", code, ctx)
            break

    # 5. Extract delivery_method from message text
    for keyword, method in _DELIVERY_KEYWORDS:
        if keyword in msg_lower:
            save_transfer_slot("delivery_method", method, ctx)
            break

    # 6. Extract phone number
    if not transfer.get("recipient_contact"):
        pm = _PHONE_NUMBER.search(message)
        if pm:
            save_transfer_slot("recipient_contact", pm.group(1).strip(), ctx)

    return session.state.get("transfer", {})


def _build_transfer_slots(transfer: dict) -> dict:
    """Build the transfer_slots response dict from transfer state."""
    return {
        "recipient_name": transfer.get("recipient_name"),
        "destination_country": transfer.get("destination_country"),
        "destination_country_name": SUPPORTED_COUNTRIES.get(
            transfer.get("destination_country", ""), None
        ),
        "amount_usd": transfer.get("amount_usd"),
        "delivery_method": transfer.get("delivery_method"),
        "recipient_contact": transfer.get("recipient_contact"),
    }


# ── FastAPI setup ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Felix Send Money Agent — ready ✅")
    yield

app = FastAPI(title="Felix Send Money Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="ui"), name="static")


# ── Pydantic models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str
    sender_role: str = "user"
    sender_name: Optional[str] = None

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    ui_component: Optional[dict] = None
    transfer_status: Optional[str] = None
    transfer_slots: Optional[dict] = None
    detected_language: Optional[str] = None

class NewSessionResponse(BaseModel):
    session_id: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse("ui/index.html")


@app.post("/session/new", response_model=NewSessionResponse)
async def new_session():
    session_id = str(uuid.uuid4())
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
    )
    return {"session_id": session_id}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send a message and get transfer form updates."""
    # Ensure session exists
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=req.session_id,
    )
    if not session:
        await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=req.session_id,
        )

    # ── __init__: seed demo contacts ──────────────────────────────────────
    if req.message == "__init__":
        s = _get_storage_session(req.session_id)
        if s:
            s.state["contacts"] = {
                "Maria": {
                    "relationship": "mother", "country_code": "MX",
                    "preferred_delivery": "cash_pickup", "phone": "+52-55-1234-5678",
                    "nickname": "mamá", "transfer_count": 12,
                    "last_transfer": "2025-03-15", "trusted": True,
                },
                "Ana": {
                    "relationship": "sister", "country_code": "MX",
                    "preferred_delivery": "mobile_wallet", "phone": "+52-55-8765-4321",
                    "nickname": "hermana", "transfer_count": 4,
                    "last_transfer": "2025-01-20", "trusted": True,
                },
                "Carlos": {
                    "relationship": "friend", "country_code": "CO",
                    "preferred_delivery": "cash_pickup", "phone": "+57-300-123-4567",
                    "nickname": "", "transfer_count": 0,
                    "last_transfer": None, "trusted": False,
                },
            }
        return ChatResponse(session_id=req.session_id, reply="")

    # ── __slot: manual field edit ─────────────────────────────────────────
    if req.message.startswith("__slot:"):
        parts = req.message.split(":", 2)
        if len(parts) == 3:
            slot_name, value = parts[1], parts[2]
            s = _get_storage_session(req.session_id)
            if s:
                ctx = _MockCtx(s.state)
                save_transfer_slot(slot_name, value, ctx)
                transfer = s.state.get("transfer", {})
                return ChatResponse(
                    session_id=req.session_id, reply="",
                    transfer_status=transfer.get("status"),
                    transfer_slots=_build_transfer_slots(transfer),
                )
        return ChatResponse(session_id=req.session_id, reply="")

    # ── __confirm: execute transfer directly ──────────────────────────────
    if req.message == "__confirm":
        s = _get_storage_session(req.session_id)
        if s:
            transfer = s.state.get("transfer", {})
            missing = [slot for slot in REQUIRED_SLOTS if not transfer.get(slot)]
            if not missing:
                ctx = _MockCtx(s.state)
                # Safety checks (auto-confirm for demo)
                result = run_safety_checks(ctx)
                for check in result.get("required_confirmations", []):
                    confirm_safety_check(check["type"], ctx)
                # Execute
                execute_transfer(ctx)
                send_email_receipt(ctx)
                record_successful_transfer(
                    transfer.get("recipient_name", ""),
                    transfer.get("amount_usd", "0"),
                    ctx,
                )
                updated = s.state.get("transfer", {})
                ui_component = s.state.get("ui_component")
                s.state["ui_component"] = None
                return ChatResponse(
                    session_id=req.session_id, reply="",
                    ui_component=ui_component,
                    transfer_status=updated.get("status"),
                    transfer_slots=_build_transfer_slots(updated),
                )
        return ChatResponse(session_id=req.session_id, reply="")

    # ── Main flow: deterministic extraction → optional agent backup ──────

    storage = _get_storage_session(req.session_id)
    if not storage:
        return ChatResponse(session_id=req.session_id, reply="")

    current_status = storage.state.get("transfer", {}).get("status", "idle")
    is_money = _detect_money_intent(req.message)
    is_active = current_status in ("collecting", "safety_check", "confirming")

    if is_money or is_active:
        # Run deterministic extraction
        transfer = _extract_and_fill_slots(
            storage, req.message, req.sender_role, req.sender_name,
        )
        transfer_status = transfer.get("status", "collecting")
        transfer_slots = _build_transfer_slots(transfer)

        # Check if all slots are filled — auto-run safety checks + summary
        missing = [slot for slot in REQUIRED_SLOTS if not transfer.get(slot)]
        ui_component = None
        if not missing and transfer_status == "collecting":
            ctx = _MockCtx(storage.state)
            safety = run_safety_checks(ctx)
            for check in safety.get("required_confirmations", []):
                confirm_safety_check(check["type"], ctx)
            from tools.confirmation_tools import build_transfer_summary
            build_transfer_summary(ctx)
            transfer = storage.state.get("transfer", {})
            transfer_status = transfer.get("status")
            transfer_slots = _build_transfer_slots(transfer)

        return ChatResponse(
            session_id=req.session_id,
            reply="",
            ui_component=ui_component,
            transfer_status=transfer_status,
            transfer_slots=transfer_slots,
        )

    # ── Non-money message, no active transfer → run agent for support ────
    message_text = req.message
    if req.sender_role == "contact" and req.sender_name:
        message_text = f"[Message from {req.sender_name}]: {req.message}"

    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=message_text)],
    )

    reply_text = ""
    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=req.session_id,
            new_message=content,
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    reply_text = event.content.parts[0].text or ""
                break
    except Exception:
        reply_text = ""

    # Suppress "SILENT" responses
    if not reply_text or reply_text.strip().upper() in ("SILENT", ""):
        reply_text = ""

    return ChatResponse(
        session_id=req.session_id,
        reply=reply_text,
    )


@app.get("/session/{session_id}/state")
async def get_session_state(session_id: str):
    """Debug endpoint — returns full session state."""
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"state": session.state}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
