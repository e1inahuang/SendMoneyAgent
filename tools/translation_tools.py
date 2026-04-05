"""
Language detection tool.
Flags Spanish messages so the orchestrator knows to respond bilingually.
We rely on the LLM for actual translation — this tool just sets the
detected language in session state for UI awareness.
"""
from google.adk.tools.tool_context import ToolContext

SPANISH_INDICATORS = {
    "hola", "quiero", "mandar", "enviar", "dinero", "cuánto", "cuanto",
    "gracias", "por favor", "sí", "si", "no", "ayuda", "cómo", "como",
    "puedo", "puedes", "necesito", "para", "con", "que", "qué",
    "cancelar", "confirmar", "mamá", "papá", "hermana", "hermano",
    "favor", "envíame", "enviame", "mándame", "mandame",
}


def detect_language(text: str, tool_context: ToolContext) -> dict:
    """Detect whether the user's message is in Spanish or English.
    Updates session state so the UI can track language preference.

    Args:
        text: The raw user message to analyse.
    """
    words = set(text.lower().split())
    spanish_hits = words & SPANISH_INDICATORS

    is_spanish = len(spanish_hits) >= 1
    detected = "es" if is_spanish else "en"

    tool_context.state["detected_language"] = detected
    return {
        "detected_language": detected,
        "is_spanish": is_spanish,
        "matched_words": list(spanish_hits),
        "instruction": (
            "Respond in BOTH English and Spanish (English first, then the Spanish "
            "translation in italics on a new line)."
            if is_spanish
            else "Respond in English."
        ),
    }
