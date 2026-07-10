from __future__ import annotations


class ClarificationPolicy:
    def top_questions(self, questions: list[tuple[str, str]], limit: int = 5) -> list[tuple[str, str]]:
        return [item for item in questions if item[0] != "confirm"][:limit] or questions[:1]
