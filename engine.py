import asyncio
import json
import os
import re
from datetime import datetime
from typing import AsyncGenerator, List, Tuple, Optional
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text

from config import LLMConfig, PersonaConfig, PERSONAS, SUMMARY_PROMPT
from models import DiscussionState, Message, MessageRole
from llm_client import LLMClient


@dataclass
class SummaryResult:
    title: str
    summary: str
    content: str


class DiscussionEngine:
    def __init__(
        self,
        topic: str,
        personas: List[PersonaConfig] = None,
        max_rounds: int = 3,
        llm_config: LLMConfig = None,
        summary_dir: str = "Summary",
    ):
        self.topic = topic
        self.personas = personas or [PERSONAS["fitness_coach"], PERSONAS["nutritionist"]]
        self.max_rounds = max_rounds
        self.state = DiscussionState(
            topic=topic,
            max_rounds=max_rounds,
        )
        self.llm_config = llm_config or LLMConfig.from_env()
        self.llm_client = LLMClient(self.llm_config)
        self.console = Console()
        self.summary_dir = summary_dir

    def _sanitize_filename(self, title: str) -> str:
        sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
        return sanitized.strip()[:50]

    def _parse_summary_response(self, response: str) -> Optional[SummaryResult]:
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return SummaryResult(
                    title=data.get("title", "讨论总结"),
                    summary=data.get("summary", ""),
                    content=data.get("content", response),
                )
        except json.JSONDecodeError:
            pass
        return None

    def _save_summary(self, result: SummaryResult) -> str:
        if not os.path.exists(self.summary_dir):
            os.makedirs(self.summary_dir)
        
        filename = self._sanitize_filename(result.title)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(self.summary_dir, f"{filename}_{timestamp}.md")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {result.title}\n\n")
            f.write(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"> 讨论主题：{self.topic}\n\n")
            f.write("---\n\n")
            f.write(result.content)
        
        return filepath

    def _build_context_prompt(self, speaker: PersonaConfig) -> str:
        history_lines = []
        for msg in self.state.messages:
            if msg.role == MessageRole.ASSISTANT:
                history_lines.append(f"【{msg.speaker}】说：{msg.content}")

        context = "\n".join(history_lines) if history_lines else "（这是讨论的开始）"

        prompt = f"""当前讨论主题：{self.topic}

之前的对话记录：
{context}

现在轮到你发言。你是【{speaker.name}】。
{speaker.system_prompt}

请直接发表你的观点，不要加任何前缀或说明。"""
        return prompt

    def _build_summary_prompt(self) -> str:
        conversation = self.state.get_formatted_conversation()
        return SUMMARY_PROMPT.format(
            topic=self.topic,
            conversation=conversation,
        )

    async def run_discussion(self) -> AsyncGenerator[Tuple[str, str], None]:
        self.console.print(
            Panel.fit(
                f"[bold cyan]讨论主题：{self.topic}[/bold cyan]\n"
                f"[dim]参与角色：{' vs '.join([p.name for p in self.personas])}[/dim]\n"
                f"[dim]轮次设置：{self.max_rounds} 轮[/dim]",
                title="🤖 AI 讨论室",
                border_style="blue",
            )
        )
        self.console.print()

        for round_num in range(1, self.max_rounds + 1):
            self.state.current_round = round_num
            self.console.print(
                f"[bold yellow]━━━ 第 {round_num} 轮 ━━━[/bold yellow]"
            )

            for speaker_index, speaker in enumerate(self.personas):
                self.state.current_speaker_index = speaker_index

                context_prompt = self._build_context_prompt(speaker)
                messages = [{"role": "user", "content": context_prompt}]

                full_response = ""
                speaker_color = "green" if speaker_index == 0 else "magenta"

                self.console.print(
                    f"\n[bold {speaker_color}]💬 {speaker.name}：[/bold {speaker_color}]",
                    end="",
                )

                async for chunk in self.llm_client.stream_chat(messages):
                    full_response += chunk
                    print(chunk, end="", flush=True)

                print()

                message = Message(
                    role=MessageRole.ASSISTANT,
                    content=full_response,
                    speaker=speaker.name,
                )
                self.state.add_message(message)

                yield (speaker.name, full_response)

                await asyncio.sleep(0.5)

            self.console.print()

        self.console.print(
            Panel.fit(
                "[bold cyan]正在生成讨论总结...[/bold cyan]",
                border_style="yellow",
            )
        )

        summary_prompt = self._build_summary_prompt()
        messages = [{"role": "user", "content": summary_prompt}]

        summary_response = ""
        self.console.print("\n[dim]正在生成总结...[/dim]")

        async for chunk in self.llm_client.stream_chat(messages):
            summary_response += chunk

        self.state.is_completed = True

        summary_result = self._parse_summary_response(summary_response)
        
        if summary_result:
            filepath = self._save_summary(summary_result)
            
            self.console.print()
            self.console.print(
                Panel.fit(
                    f"[bold green]📝 讨论总结[/bold green]\n\n"
                    f"[cyan]{summary_result.summary}[/cyan]\n\n"
                    f"[dim]完整总结已保存至：{filepath}[/dim]",
                    border_style="green",
                )
            )
        else:
            self.console.print()
            self.console.print(
                Panel.fit(
                    f"[bold yellow]📝 讨论总结[/bold yellow]\n\n"
                    f"{summary_response[:200]}...\n\n"
                    f"[dim]（总结格式解析失败，未保存文件）[/dim]",
                    border_style="yellow",
                )
            )

        yield ("总结", summary_response)

    async def run(self):
        async for speaker, content in self.run_discussion():
            pass

        return self.state