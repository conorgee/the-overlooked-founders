import re

SOURCE_PATTERN = re.compile(r"\U0001f4ce\s*Source:\s*(.+?)(?:\n|$)", re.IGNORECASE)


def extract_sources(text: str) -> list[str]:
    return [s.strip() for s in SOURCE_PATTERN.findall(text)]
