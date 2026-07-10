from __future__ import annotations

from pathlib import Path


class ConversationMemory:
    def write(self, path: str | Path, idea: str, questions: list[tuple[str, str]], fields: dict) -> None:
        lines = ["# Conversation Log", "", f"User idea: {idea}", "", "## Inferred Fields", str(fields), "", "## Next Questions"]
        lines.extend(f"- [{qid}] {question}" for qid, question in questions)
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
