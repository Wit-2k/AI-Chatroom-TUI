from dataclasses import dataclass, field
from typing import List
from enum import Enum


class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class Message:
    role: MessageRole
    content: str
    speaker: str = ""

    def to_api_format(self) -> dict:
        return {
            "role": self.role.value,
            "content": self.content,
        }


@dataclass
class DiscussionState:
    topic: str
    current_round: int = 0
    max_rounds: int = 3
    current_speaker_index: int = 0
    messages: List[Message] = field(default_factory=list)
    is_completed: bool = False

    def add_message(self, message: Message):
        self.messages.append(message)

    def get_conversation_history(self) -> List[dict]:
        return [msg.to_api_format() for msg in self.messages]

    def get_formatted_conversation(self) -> str:
        lines = []
        for msg in self.messages:
            if msg.role == MessageRole.ASSISTANT:
                lines.append(f"【{msg.speaker}】: {msg.content}")
        return "\n".join(lines)