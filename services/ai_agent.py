from dataclasses import dataclass, field
from typing import List
import anthropic
from config import settings
from prompts.urdu_system import URDU_SYSTEM_PROMPT, UNCLEAR_TEXT

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 300       # Keep responses short for phone calls
_MAX_HISTORY = 20       # Limit history to avoid large contexts


@dataclass
class ConversationMessage:
    role: str
    content: str


@dataclass
class AppointmentData:
    name: str = ""
    date: str = ""
    time: str = ""
    purpose: str = ""

    def is_complete(self) -> bool:
        return all([self.name, self.date, self.time, self.purpose])


class UrduAgent:
    """Stateful AI agent for a single phone call session."""

    def __init__(self):
        self._history: List[ConversationMessage] = []
        self.appointment: AppointmentData = AppointmentData()
        self.collected_info: dict = {}

    async def get_response(self, user_text: str) -> str:
        """Send user text to Claude and return the Urdu reply."""
        if not user_text.strip():
            return UNCLEAR_TEXT

        self._history.append(ConversationMessage(role="user", content=user_text))

        # Trim history to avoid token bloat
        if len(self._history) > _MAX_HISTORY:
            self._history = self._history[-_MAX_HISTORY:]

        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in self._history
        ]

        try:
            response = _client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                system=URDU_SYSTEM_PROMPT,
                messages=messages,
            )
            reply = response.content[0].text.strip()
        except Exception as exc:
            print(f"[Agent] Claude error: {exc}")
            reply = UNCLEAR_TEXT

        self._history.append(ConversationMessage(role="assistant", content=reply))
        return reply

    def reset(self):
        self._history.clear()
        self.appointment = AppointmentData()
        self.collected_info = {}
