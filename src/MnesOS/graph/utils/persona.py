from typing import Dict


def build_persona_background_context(persona_context: Dict[str, str]) -> str:
    """Build persona context for Director and Narrator prompts."""
    context = persona_context or {}
    name = context.get("name", "").strip()
    pronouns = context.get("pronouns", "").strip()
    appearance = context.get("appearance", "").strip()
    background = context.get("background", "").strip()
    personality = context.get("personality", "").strip()

    if not (name or pronouns or appearance or background or personality):
        return ""

    return (
        "\n\n--- PLAYER CHARACTER BACKGROUND (CONTEXT ONLY) ---\n"
        f"- Name: {name or 'N/A'}\n"
        f"- Pronouns: {pronouns or 'N/A'}\n"
        f"- Appearance: {appearance or 'N/A'}\n"
        f"- Background: {background or 'N/A'}\n"
        f"- Personality: {personality or 'N/A'}"
    )
