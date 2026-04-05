"""
Root Orchestrator — thin router.
Money intent detection and slot extraction are handled in main.py.
This agent only routes active transfers to send_money_agent
and support questions to support_agent.
"""
import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from tools.slot_tools import cancel_transfer, get_transfer_state
from agents.send_money_agent import send_money_agent
from agents.support_agent import support_agent

MODEL = LiteLlm(model="openai/gpt-4o-mini")

INSTRUCTION = """
You are a SILENT message router. You NEVER chat with the user.

1. Call get_transfer_state().
2. If status is "collecting", "safety_check", or "confirming":
   → transfer to send_money_agent.
3. If user says "cancel", "stop", "nevermind", or "cancelar":
   → call cancel_transfer(), then return "SILENT".
4. If user asks about exchange rates, fees, transfer status, or FAQs:
   → transfer to support_agent.
5. Otherwise → return exactly "SILENT".

NEVER generate conversational text. NEVER ask questions.
"""

root_agent = LlmAgent(
    name="felix_orchestrator",
    model=MODEL,
    description="Felix — routes messages to the right sub-agent.",
    instruction=INSTRUCTION,
    tools=[
        get_transfer_state,
        cancel_transfer,
    ],
    sub_agents=[send_money_agent, support_agent],
)
