# Send Money Agent
An AI-powered cross-border remittance agent that **detects transfer intent from natural conversation** and orchestrates the entire send-money flow — from slot extraction to safety checks to receipt generation — all within a WhatsApp-style chat interface.

Built with Google ADK (Agent Development Kit) multi-agent architecture and OpenAI GPT-4o-mini.

---
## Demo
- How to run:
```bash
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```
- Identifies transfer intent and the transfer window pops up
  <img width="902" height="1084" alt="Screenshot 2026-04-05 at 12 09 07 PM" src="https://github.com/user-attachments/assets/c8efe223-9d8a-414b-838d-d8708b1df9fe" />
- Autofills info from conversation
  <img width="902" height="1084" alt="Screenshot 2026-04-05 at 12 10 03 PM" src="https://github.com/user-attachments/assets/13570d0d-0a65-4b81-a767-48af541aaf9e" />
- Manual edition suppported too
  <img width="902" height="1084" alt="Screenshot 2026-04-05 at 12 19 51 PM" src="https://github.com/user-attachments/assets/af8e3d8d-665b-42a4-bb19-ca9c2b31ea02" />
- Send money agent will not pop up for daily conversation
  <img width="902" height="1084" alt="Screenshot 2026-04-05 at 12 20 34 PM" src="https://github.com/user-attachments/assets/1c6a4a0f-1ad0-469f-bb6e-1029ec2ebd09" />


---

## How It Works

A user chats with a family member (e.g., Maria in Mexico). When Maria says _"can you send me 200 usd"_, the Felix agent:

1. **Detects** the money-transfer intent from the message (regex, not LLM — deterministic & instant)
2. **Extracts** slots: recipient, amount, country, delivery method, contact info
3. **Pre-fills** known fields from contact memory (past transfer history)
4. **Pops up** a transfer card on the user's phone with all extracted info
5. **Runs safety checks** (first-time recipient, large amount, third-party request)
6. **Executes** the transfer and generates a receipt with transaction ID

The user never leaves the chat. No forms, no app switching — just conversation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend (main.py)                    │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              Deterministic Pre-Processing Layer               │  │
│  │                                                               │  │
│  │  Message ──→ Money Intent Detection (regex)                   │  │
│  │         ──→ Slot Extraction (regex + contact memory lookup)   │  │
│  │         ──→ Bypass Handlers (__init__, __slot, __confirm)     │  │
│  └──────────────────────────┬────────────────────────────────────┘  │
│                             │ fallback (if slots still missing)     │
│                             ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              Google ADK Multi-Agent System                    │   │
│  │                                                               │   │
│  │  ┌──────────────────┐                                         │   │
│  │  │   Orchestrator   │──→ Routes messages to sub-agents        │   │
│  │  │   (root agent)   │                                         │   │
│  │  └────┬────────┬────┘                                         │   │
│  │       │        │                                               │   │
│  │       ▼        ▼                                               │   │
│  │  ┌─────────┐ ┌──────────┐                                     │   │
│  │  │  Send   │ │ Support  │                                     │   │
│  │  │  Money  │ │  Agent   │                                     │   │
│  │  │  Agent  │ │ (FAQs,   │                                     │   │
│  │  │(backup  │ │  rates,  │                                     │   │
│  │  │ slot    │ │  status) │                                     │   │
│  │  │extract) │ │          │                                     │   │
│  │  └─────────┘ └──────────┘                                     │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                        Tool Layer                             │  │
│  │  slot_tools │ safety_tools │ confirmation_tools │ memory_tools│  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
          │                                          │
          ▼                                          ▼
┌───────────────────┐                    ┌───────────────────┐
│  YOUR PHONE 🇺🇸   │     Felix AI       │ MARIA'S PHONE 🇲🇽  │
│                   │    ┌───────┐       │                   │
│  Chat + Transfer  │◄──►│  ✦    │◄──────│  Chat (sender)    │
│  Card UI          │    │ Agent │       │                   │
└───────────────────┘    └───────┘       └───────────────────┘
```

### Design Decisions

| Decision | Why |
|----------|-----|
| **Deterministic extraction first, LLM second** | Regex runs in microseconds with 100% reproducibility. The LLM agent is only a backup for edge cases the regex misses. This eliminates the #1 problem with LLM-only extraction: conversation history contamination across consecutive transfers. |
| **Bypass handlers (`__init__`, `__slot:`, `__confirm`)** | Manual field edits and transfer execution skip the LLM entirely. No latency, no hallucination risk for critical operations. |
| **3 agents instead of 7** | The spec called for 7 specialized agents. In practice, deterministic code handles intent detection, safety, confirmation, and execution better than LLM agents. The 3 remaining agents (orchestrator, send_money, support) handle routing, backup extraction, and FAQs. |
| **Contact memory pre-fill** | When Maria (a known contact) sends a message, her saved profile auto-fills country, delivery method, and phone — making the demo feel like magic. |
| **SILENT agents** | Agents return "SILENT" instead of generating chat text. All user-facing interaction happens through the transfer card UI, not chat bubbles. This prevents agents from generating incorrect or confusing messages. |
| **InMemorySessionService `_get_storage_session()`** | ADK's `get_session()` returns a `deepcopy`. Direct mutations don't persist. We access the internal `sessions` dict directly for deterministic handlers that need to write state. |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Agent Framework | Google ADK (Agent Development Kit) |
| LLM | OpenAI GPT-4o-mini via LiteLLM adapter |
| Backend | Python FastAPI + Uvicorn |
| Frontend | Vanilla HTML/JS/CSS (no build step) |
| Session Store | ADK InMemorySessionService |

---

## Project Structure

```
SendMoneyAgent/
├── main.py                  # FastAPI server, deterministic extraction, bypass handlers
├── requirements.txt
├── .env                     # API keys (not committed)
├── agents/
│   ├── orchestrator.py      # Root agent — routes to sub-agents
│   ├── send_money_agent.py  # Backup LLM slot extractor
│   └── support_agent.py     # FAQs, exchange rates, transfer status
├── tools/
│   ├── slot_tools.py        # Slot validation, transfer state machine
│   ├── safety_tools.py      # First-time recipient, large amount, third-party checks
│   ├── confirmation_tools.py # Transfer execution, receipt, email
│   ├── memory_tools.py      # Contact profiles, transfer history
│   └── translation_tools.py # Language detection (en/es)
└── ui/
    ├── index.html           # Dual-phone WhatsApp layout
    ├── app.js               # Frontend logic, transfer card, receipt rendering
    └── style.css            # Dark theme, animations
```

---

## Setup

### Prerequisites
- Python 3.11+
- OpenAI API key

### Install & Run

```bash
# Clone
git clone https://github.com/e1inahuang/SendMoneyAgent.git
cd SendMoneyAgent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Run
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Open **http://localhost:8001** in your browser.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4o-mini |
| `USER_EMAIL` | No | Email for mock receipts (default: demo address) |
| `APP_NAME` | No | Session namespace (default: `felix_send_money`) |

---

## Demo Walkthrough

### Transfer Flow

1. **Maria sends**: _"can you send me 200 usd"_
2. **Transfer card pops up** on your phone with 5/5 fields auto-filled:
   - TO: Maria ✓ (from sender context)
   - COUNTRY: Mexico ✓ (from contact memory)
   - AMOUNT: $200.00 USD ✓ (regex extraction)
   - DELIVERY: Cash Pickup ✓ (from contact memory)
   - CONTACT: +52-55-1234-5678 ✓ (from contact memory)
3. **Click "Send $200.00 →"** — safety checks run, transfer executes
4. **Receipt appears** with transaction ID, then auto-dismisses
5. **Maria sends**: _"can you send me additional 800"_
6. **New card appears** with $800 (independent — NOT $1000)


### Supported Countries

Mexico, Guatemala, Honduras, El Salvador, Dominican Republic, Colombia, Peru, Ecuador, Bolivia, Nicaragua, Panama, Venezuela

---

## Transfer State Machine

```
idle ──→ collecting ──→ confirming ──→ complete
  ↑          │                           │
  └──────────┴───── cancelled ◄──────────┘
                   (reset to idle)
```

| State | Description |
|-------|-------------|
| `idle` | No active transfer |
| `collecting` | Slots being filled (card visible) |
| `confirming` | All slots filled, awaiting user confirmation |
| `complete` | Transfer executed, receipt shown |
| `cancelled` | User cancelled, state reset |

---

## API

### `POST /chat`

Main endpoint for all interactions.

```json
// Request
{
  "session_id": "uuid",
  "message": "can you send me 200 usd",
  "sender_role": "contact",
  "sender_name": "Maria"
}

// Response
{
  "session_id": "uuid",
  "reply": "",
  "transfer_status": "collecting",
  "transfer_slots": {
    "recipient_name": "Maria",
    "destination_country": "MX",
    "destination_country_name": "Mexico",
    "amount_usd": "200.0",
    "delivery_method": "cash_pickup",
    "recipient_contact": "+52-55-1234-5678"
  },
  "ui_component": null
}
```

### Special Messages

| Message | Purpose |
|---------|---------|
| `__init__` | Seeds demo contacts on session start |
| `__slot:field:value` | Manual field edit (bypasses LLM) |
| `__confirm` | Execute transfer (runs safety → execute → receipt) |

---

## License

MIT
