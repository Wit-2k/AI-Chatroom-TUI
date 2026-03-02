import asyncio
import json
import os
import random
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
        # 尝试策略1：直接解析（模型输出合规 JSON 时）
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

        # 尝试策略2：修复 JSON 字符串内的裸换行后再解析
        # 模型有时会在 content 字段内输出真实换行而非 \n，导致 JSON 非法
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                raw = json_match.group()
                # 将字符串值内部的裸换行替换为 \n（仅处理引号内的换行）
                fixed = re.sub(
                    r'("(?:[^"\\]|\\.)*")',
                    lambda m: m.group(0).replace('\n', '\\n').replace('\r', ''),
                    raw,
                )
                data = json.loads(fixed)
                return SummaryResult(
                    title=data.get("title", "讨论总结"),
                    summary=data.get("summary", ""),
                    content=data.get("content", response),
                )
        except (json.JSONDecodeError, Exception):
            pass

        # 尝试策略3：用正则直接提取各字段（兜底方案）
        try:
            title = re.search(r'"title"\s*:\s*"([^"]+)"', response)
            summary = re.search(r'"summary"\s*:\s*"([^"]+)"', response)
            # content 可能跨多行，用非贪婪匹配
            content = re.search(r'"content"\s*:\s*"([\s\S]+?)"\s*\}', response)
            if title and summary:
                return SummaryResult(
                    title=title.group(1),
                    summary=summary.group(1),
                    content=content.group(1).replace('\\n', '\n') if content else response,
                )
        except Exception:
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

    def _build_context_prompt(self, speaker: PersonaConfig, round_num: int) -> str:
        """
        构建 user 消息内容。
        system_prompt 已在调用处单独作为 system 消息传入，此处只返回 user prompt 字符串。
        """
        # 收集所有非当前角色的历史发言
        other_messages = [
            msg for msg in self.state.messages
            if msg.role == MessageRole.ASSISTANT and msg.speaker != speaker.name
        ]

        # 随机抽取 1-2 条历史发言作为"需要回应的目标"
        # 历史不足时取全部；开场无历史则不抽取
        if other_messages:
            sample_count = min(random.randint(1, 2), len(other_messages))
            target_messages = random.sample(other_messages, sample_count)
            # 按原始顺序排列，保持时序感
            target_messages.sort(key=lambda m: self.state.messages.index(m))
        else:
            target_messages = []

        # 构建完整历史记录（全部展示，供角色了解上下文）
        history_lines = [
            f"【{msg.speaker}】：{msg.content}"
            for msg in self.state.messages
            if msg.role == MessageRole.ASSISTANT
        ]
        history_text = "\n".join(history_lines) if history_lines else "（暂无发言记录）"

        # 判断轮次阶段
        is_opening = (round_num == 1 and not self.state.messages)
        is_final = (round_num == self.max_rounds)

        if is_opening:
            round_hint = "这是讨论的开场，请先陈述你对该话题的核心立场与观点。"
        elif is_final:
            round_hint = (
                f"这是第 {round_num} 轮，也是最后一轮。"
                "请回应下方指定发言，并做出你的最终立场总结。"
            )
        else:
            round_hint = (
                f"这是第 {round_num} 轮（共 {self.max_rounds} 轮）。"
                "请回应下方指定发言，再进一步阐述你的观点。"
            )

        # 构建需要回应的发言高亮块
        if target_messages:
            targets_text = "\n".join(
                f"【{m.speaker}】：{m.content}" for m in target_messages
            )
            respond_block = (
                f"\n【请重点回应以下发言】\n"
                f"{targets_text}\n"
            )
        else:
            respond_block = ""

        user_prompt = f"""【讨论主题】
{self.topic}

【完整对话记录】
{history_text}
{respond_block}
【你的发言任务】
{round_hint}
发言请控制在100字以内，直接输出内容，不要加任何角色名前缀或说明文字。"""

        return user_prompt

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

                user_prompt = self._build_context_prompt(speaker, round_num)
                messages = [
                    {"role": "system", "content": speaker.system_prompt},
                    {"role": "user", "content": user_prompt},
                ]

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

        async for chunk in self.llm_client.stream_chat(messages, max_tokens=2000):
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