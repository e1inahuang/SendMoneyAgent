// ── Config ────────────────────────────────────────────────────────────────────
const API_BASE = "http://localhost:8001";

// ── State ─────────────────────────────────────────────────────────────────────
let SESSION_ID = null;
let transferCardOpen = false;
let currentSlots = {};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const userChat      = document.getElementById("user-chat");
const momChat       = document.getElementById("mom-chat");
const userInput     = document.getElementById("user-input");
const momInput      = document.getElementById("mom-input");
const userSendBtn   = document.getElementById("user-send-btn");
const momSendBtn    = document.getElementById("mom-send-btn");
const felixBanner   = document.getElementById("felix-banner");
const felixDot      = document.getElementById("felix-dot");
const felixStatus   = document.getElementById("felix-status");
const felixChip     = document.getElementById("felix-chip");
const felixBadge    = document.getElementById("felix-center-badge");
const userHeaderSub = document.getElementById("user-header-sub");

// Transfer card refs
const transferCard  = document.getElementById("transfer-card");
const tcSendBtn     = document.getElementById("tc-send-btn");
const tcCancelBtn   = document.getElementById("tc-cancel-btn");
const tcProgress    = document.getElementById("tc-progress");

// ── Slot display helpers ──────────────────────────────────────────────────────
const DELIVERY_LABELS = {
  bank_deposit:   "Bank Deposit",
  cash_pickup:    "Cash Pickup",
  mobile_wallet:  "Mobile Wallet",
};

function formatSlotValue(slot, value, slots) {
  if (!value) return null;
  switch (slot) {
    case "recipient_name":       return value;
    case "destination_country":  return slots.destination_country_name || value;
    case "amount_usd":           return `$${parseFloat(value).toFixed(2)} USD`;
    case "delivery_method":      return DELIVERY_LABELS[value] || value;
    case "recipient_contact":    return value;
    default: return value;
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
(async () => {
  SESSION_ID = await createSession();
  appendDateSep(userChat, "Today");
  appendDateSep(momChat,  "Today");
  await callAgent("__init__", "user", null);
})();

// ── Session ───────────────────────────────────────────────────────────────────
async function createSession() {
  const res  = await fetch(`${API_BASE}/session/new`, { method: "POST" });
  const data = await res.json();
  return data.session_id;
}

// ── Transfer card ─────────────────────────────────────────────────────────────
function showTransferCard() {
  transferCardOpen = true;
  transferCard.classList.add("open");
  transferCard.classList.remove("receipt");
  resetFormFields();
}

function hideTransferCard() {
  transferCardOpen = false;
  transferCard.classList.remove("open", "receipt");
  currentSlots = {};
  resetFormFields();
}

// Original field HTML — used to rebuild after receipt mode destroys it
const ORIGINAL_FIELDS_HTML = `
    <div class="tc-field" id="tf-recipient_name" data-slot="recipient_name">
      <span class="tc-label">To</span>
      <span class="tc-value">—</span>
      <span class="tc-check"></span>
    </div>
    <div class="tc-field" id="tf-destination_country" data-slot="destination_country">
      <span class="tc-label">Country</span>
      <span class="tc-value">—</span>
      <span class="tc-check"></span>
    </div>
    <div class="tc-field" id="tf-amount_usd" data-slot="amount_usd">
      <span class="tc-label">Amount</span>
      <span class="tc-value">—</span>
      <span class="tc-check"></span>
    </div>
    <div class="tc-field" id="tf-delivery_method" data-slot="delivery_method">
      <span class="tc-label">Delivery</span>
      <span class="tc-value">—</span>
      <span class="tc-check"></span>
    </div>
    <div class="tc-field" id="tf-recipient_contact" data-slot="recipient_contact">
      <span class="tc-label">Contact</span>
      <span class="tc-value">—</span>
      <span class="tc-check"></span>
    </div>`;

function resetFormFields() {
  // Rebuild field HTML if receipt mode destroyed it
  const fieldsEl = document.getElementById("tc-fields");
  if (!document.getElementById("tf-recipient_name")) {
    fieldsEl.innerHTML = ORIGINAL_FIELDS_HTML;
    // Re-attach manual edit click listeners
    fieldsEl.querySelectorAll(".tc-field").forEach(field => {
      field.addEventListener("click", () => {
        if (!transferCardOpen) return;
        const slot = field.dataset.slot;
        const currentValue = currentSlots[slot] || "";
        const label = field.querySelector(".tc-label").textContent;
        const newValue = prompt(`Enter ${label}:`, currentValue);
        if (newValue !== null && newValue.trim()) {
          callAgent(`__slot:${slot}:${newValue.trim()}`, "user", null);
        }
      });
    });
  }

  // Reset each field to empty state
  const SLOTS = ["recipient_name", "destination_country", "amount_usd", "delivery_method", "recipient_contact"];
  SLOTS.forEach(slot => {
    const el = document.getElementById(`tf-${slot}`);
    if (el) {
      el.classList.remove("filled", "just-filled");
      el.querySelector(".tc-value").textContent = "—";
    }
  });

  // Restore header title
  const titleEl = transferCard.querySelector(".tc-title");
  if (titleEl) titleEl.innerHTML = `<span class="tc-icon">✦</span> Send Money`;

  // Restore footer visibility
  const footer = transferCard.querySelector(".tc-footer");
  if (footer) footer.style.display = "";

  // Restore cancel button text
  tcCancelBtn.textContent = "Cancel";

  // Reset send button
  tcSendBtn.disabled = true;
  tcSendBtn.classList.remove("active", "sending");
  tcSendBtn.textContent = "Send Money";
  tcProgress.textContent = "0 / 5 fields";
}

function updateFormSlots(slots) {
  if (!slots) return;
  const REQUIRED = ["recipient_name", "destination_country", "amount_usd", "delivery_method", "recipient_contact"];
  let filledCount = 0;

  REQUIRED.forEach(slot => {
    const value = slots[slot];
    const el = document.getElementById(`tf-${slot}`);
    if (!el) return;

    if (value) {
      filledCount++;
      const display = formatSlotValue(slot, value, slots);
      const valueEl = el.querySelector(".tc-value");
      const wasEmpty = !currentSlots[slot];
      const changed = currentSlots[slot] !== value;

      if (display) valueEl.textContent = display;
      el.classList.add("filled");

      // Animate only when a NEW value appears
      if (changed && (wasEmpty || currentSlots[slot] !== value)) {
        el.classList.add("just-filled");
        setTimeout(() => el.classList.remove("just-filled"), 600);
      }
    }
  });

  currentSlots = { ...slots };
  tcProgress.textContent = `${filledCount} / 5 fields`;

  // Enable send button when all filled
  const allFilled = REQUIRED.every(s => slots[s]);
  tcSendBtn.disabled = !allFilled;
  tcSendBtn.classList.toggle("active", allFilled);
  if (allFilled) {
    const amt = parseFloat(slots.amount_usd).toFixed(2);
    tcSendBtn.textContent = `Send $${amt} →`;
  }
}

// Manual field editing
document.querySelectorAll(".tc-field").forEach(field => {
  field.addEventListener("click", () => {
    if (!transferCardOpen) return;
    const slot = field.dataset.slot;
    const currentValue = currentSlots[slot] || "";
    const label = field.querySelector(".tc-label").textContent;
    const newValue = prompt(`Enter ${label}:`, currentValue);
    if (newValue !== null && newValue.trim()) {
      // Send the update through the chat API so the agent records it
      callAgent(`__slot:${slot}:${newValue.trim()}`, "user", null);
    }
  });
});

// Send / Cancel buttons
tcSendBtn.addEventListener("click", async () => {
  if (tcSendBtn.disabled) return;
  tcSendBtn.disabled = true;
  tcSendBtn.classList.remove("active");
  tcSendBtn.classList.add("sending");
  tcSendBtn.textContent = "Sending...";
  await callAgent("__confirm", "user", null);
});

tcCancelBtn.addEventListener("click", async () => {
  await callAgent("cancel", "user", null);
  hideTransferCard();
});

// ── Event listeners ───────────────────────────────────────────────────────────
userSendBtn.addEventListener("click", () => handleSend("user"));
momSendBtn.addEventListener ("click", () => handleSend("mom"));

userInput.addEventListener("keydown", e => { if (e.key === "Enter") handleSend("user"); });
momInput.addEventListener ("keydown", e => { if (e.key === "Enter") handleSend("mom");  });

async function handleSend(who) {
  const input = who === "user" ? userInput : momInput;
  const text  = input.value.trim();
  if (!text || !SESSION_ID) return;
  input.value = "";

  if (who === "user") {
    appendBubble(userChat, "sent",     text);
    appendBubble(momChat,  "received", text);
    await callAgent(text, "user", "Maria");
  } else {
    appendBubble(momChat,  "sent",     text);
    appendBubble(userChat, "received", text);
    await callAgent(text, "contact", "Maria");
  }
}

// ── Agent call ────────────────────────────────────────────────────────────────
async function callAgent(text, senderRole, senderName) {
  const isSilentInit = text === "__init__";
  const isSlotUpdate = text.startsWith("__slot:");
  if (!isSilentInit && !isSlotUpdate) setFelixState("thinking");
  if (!isSilentInit && !isSlotUpdate) disableInputs(true);

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id:  SESSION_ID,
        message:     text,
        sender_role: senderRole,
        sender_name: senderName,
      }),
    });
    const data = await res.json();
    if (!isSilentInit && !isSlotUpdate) disableInputs(false);

    const status = data.transfer_status;

    // Show/update transfer form card
    if (status === "collecting" || status === "safety_check" || status === "confirming") {
      if (!transferCardOpen) {
        currentSlots = {};  // clean slate for new transfer
        showTransferCard();
      }
      if (data.transfer_slots) updateFormSlots(data.transfer_slots);
      setFelixState("active");
    }

    // Handle receipt UI component
    if (data.ui_component && data.ui_component.type === "transfer_receipt") {
      renderReceiptInCard(data.ui_component.data);
      setFelixState("active");
      setTimeout(() => { hideTransferCard(); setFelixState("standby"); }, 3500);
    }

    // Close on cancel/idle
    if (status === "cancelled" || status === "idle") {
      if (transferCardOpen) hideTransferCard();
      setFelixState("standby");
    }

    // After completion without receipt
    if (status === "complete" && !data.ui_component) {
      setFelixState("standby");
    }

    // Return to standby if no active transfer
    if (!status || status === "idle") {
      setFelixState("standby");
    }

    scrollBoth();
  } catch (err) {
    if (!isSilentInit && !isSlotUpdate) disableInputs(false);
    setFelixState("standby");
    console.error(err);
  }
}

// ── Receipt in card ───────────────────────────────────────────────────────────
function renderReceiptInCard(d) {
  transferCard.classList.add("receipt");

  // Update header
  const titleEl = transferCard.querySelector(".tc-title");
  titleEl.innerHTML = `<span class="tc-icon">✅</span> Transfer Sent!`;

  // Replace fields with receipt data
  const fieldsEl = document.getElementById("tc-fields");
  fieldsEl.innerHTML = `
    <div class="tc-field filled"><span class="tc-label">To</span><span class="tc-value">${esc(d.recipient_name)}</span><span class="tc-check"></span></div>
    <div class="tc-field filled"><span class="tc-label">Amount</span><span class="tc-value">$${esc(d.amount_usd)} USD</span><span class="tc-check"></span></div>
    <div class="tc-field filled"><span class="tc-label">Fee</span><span class="tc-value">${esc(d.fee || "$2.99")}</span><span class="tc-check"></span></div>
    <div class="tc-field filled"><span class="tc-label">Via</span><span class="tc-value">${esc(d.delivery_method)}</span><span class="tc-check"></span></div>
    <div class="tc-field filled"><span class="tc-label">Date</span><span class="tc-value">${esc(d.timestamp)}</span><span class="tc-check"></span></div>
  `;

  // Add receipt ID and email
  tcProgress.innerHTML = `<span class="tc-receipt-id">${esc(d.transaction_id)}</span>`;

  // Hide send button, change cancel to "Close"
  const footer = transferCard.querySelector(".tc-footer");
  footer.style.display = "none";
  tcCancelBtn.textContent = "Close";
}

// ── Felix state ───────────────────────────────────────────────────────────────
function setFelixState(state) {
  felixDot.className   = "felix-dot";
  felixBanner.className = "felix-banner";
  felixChip.className  = "felix-chip";
  felixBadge.className = "felix-center-badge";

  if (state === "active") {
    felixDot.classList.add("active");
    felixBanner.classList.add("active");
    felixChip.classList.add("active");
    felixBadge.classList.add("active");
    felixStatus.textContent = "active";
  } else if (state === "thinking") {
    felixDot.classList.add("active");
    felixBanner.classList.add("active");
    felixChip.classList.add("active");
    felixBadge.classList.add("active");
    felixStatus.textContent = "thinking...";
    userHeaderSub.textContent = "Felix is processing...";
  } else {
    felixStatus.textContent = "standing by";
    userHeaderSub.textContent = "online";
  }

  if (state !== "thinking") {
    userHeaderSub.textContent = "online";
  }
}

// ── Rendering ─────────────────────────────────────────────────────────────────
function appendBubble(chatEl, direction, text) {
  const row    = document.createElement("div");
  row.className = `msg-row ${direction}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = `${fmt(text)}<div class="msg-time">${nowTime()}</div>`;
  row.appendChild(bubble);
  chatEl.appendChild(row);
  scroll(chatEl);
  return row;
}

function appendDateSep(chatEl, label) {
  const el = document.createElement("div");
  el.className = "date-sep";
  el.textContent = label;
  chatEl.appendChild(el);
}

// ── Utils ─────────────────────────────────────────────────────────────────────
function fmt(text) {
  return String(text)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>")
    .replace(/\*(.+?)\*/g,   "<em>$1</em>")
    .replace(/_(.+?)_/g,     "<em>$1</em>")
    .replace(/\n/g,          "<br>");
}
function esc(v) {
  return String(v ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
function nowTime() {
  return new Date().toLocaleTimeString([], { hour:"2-digit", minute:"2-digit" });
}
function scroll(el) { el.scrollTop = el.scrollHeight; }
function scrollBoth() { scroll(userChat); scroll(momChat); }
function disableInputs(v) {
  userInput.disabled  = v;
  momInput.disabled   = v;
  userSendBtn.disabled = v;
  momSendBtn.disabled  = v;
}
