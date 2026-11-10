import re

# "@name" not glued to a word, dot or another @ (so emails like sam@x.com never match).
MENTION_PATTERN = re.compile(r"(?<![\w@.])@([A-Za-z0-9_]{3,50})\b")


def extract_mentions(text: str) -> set[str]:
    return {name.lower() for name in MENTION_PATTERN.findall(text)}