from typing import Dict


def build_persona_background_context(persona_context: Dict[str, str]) -> str:
    """Build non-POV-overriding persona context for Director and Narrator prompts."""
    context = persona_context or {}
    appearance = context.get("appearance", "").strip()
    background = context.get("background", "").strip()
    personality = context.get("personality", "").strip()

    if not (appearance or background or personality):
        return ""

    return (
        "\n\n--- PLAYER PERSONA BACKGROUND (CONTEXT ONLY) ---\n"
        "Use this only as background context. Keep second-person address to the player (\"you\") at all times.\n"
        f"- Appearance: {appearance or 'N/A'}\n"
        f"- Background: {background or 'N/A'}\n"
        f"- Personality: {personality or 'N/A'}"
    )
