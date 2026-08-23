"""People-first practical-benefit rules for ETAP travel articles."""
PRACTICAL_BENEFIT_RULES = r'''
[PEOPLE-FIRST PRACTICAL BENEFITS]
- Lead with the traveler's actual decision: where to go, when to go, what to book, or how to avoid a wasted trip.
- For at least two concrete facts, use this chain: verified fact -> situation where it matters -> practical benefit such as time, cost, convenience, mobility, or lower booking risk -> who benefits and who may not need it.
- After a fact or specification, answer: "What changes for the traveler in real use?"
- Never infer all-day use, easy portability, guaranteed savings, or convenience unless the source data supports it.
- State limits and trade-offs. Recommendations must be framed as fit for a traveler type, not as universal superiority.
- Prefer concrete details such as port walking time, opening hours, transfer steps, ticket conditions, neighborhood, duration, or price when verified.
'''

_BENEFIT_MARKERS = (
    "best for", "less useful", "useful when", "in practice", "saves time",
    "saves money", "helps you", "what changes", "worth it if", "trade-off",
    "travellers who", "travelers who", "if you only have", "to avoid",
)


def benefit_connection_issues(content: str, minimum: int = 2) -> list[str]:
    text = (content or "").lower()
    count = sum(1 for marker in _BENEFIT_MARKERS if marker in text)
    issues = []
    if count < minimum:
        issues.append(f"[WARNING] Practical benefit connections: {count}/{minimum} minimum")
    return issues
