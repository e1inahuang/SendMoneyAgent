"""
SendMoneyAgent — backup slot extractor.
The main extraction is done deterministically in main.py.
This agent only fills slots the regex missed.
"""
import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from tools.slot_tools import (
    save_transfer_slot,
    get_transfer_state,
    get_delivery_methods,
)
from tools.memory_tools import get_contact
from tools.safety_tools import run_safety_checks
from tools.confirmation_tools import build_transfer_summary

MODEL = LiteLlm(model="openai/gpt-4o-mini")

INSTRUCTION = """
You are a SILENT backup slot extractor for money transfers.
The primary extraction has already run before you. Your ONLY job is to
catch slot values the regex may have missed.

STEP 1: Call get_transfer_state() to see what is already filled.
STEP 2: Only call save_transfer_slot for slots that are STILL MISSING.
STEP 3: If all 5 slots are now filled, call run_safety_checks,
        then build_transfer_summary.

CRITICAL RULES:
- Each transfer is INDEPENDENT. NEVER reference previous transfers.
- NEVER add amounts together. If message says "800", amount is 800.
- Only extract values EXPLICITLY stated in the CURRENT message.
- If you find nothing new to extract, do nothing.
- ALWAYS end with exactly the word "SILENT".
  Never generate conversational text. Never ask questions.
"""

send_money_agent = LlmAgent(
    name="send_money_agent",
    model=MODEL,
    description="Backup slot extractor for money transfers.",
    instruction=INSTRUCTION,
    tools=[
        get_transfer_state,
        save_transfer_slot,
        get_delivery_methods,
        get_contact,
        run_safety_checks,
        build_transfer_summary,
    ],
)
