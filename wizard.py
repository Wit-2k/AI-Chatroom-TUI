import json
import re
from typing import List, Optional, Callable
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text

from config import PersonaConfig
from config_loader import AppConfig, ConfigLoader
from llm_client import LLMClient
from config import LLMConfig


PERSONA_GENERATION_PROMPT = """请生成 {count} 个适合多话题讨论的 AI 辩论角色。这些角色应该：
1. 有鲜明的立场倾向（如激进派/保守派、理想主义/现实主义等）
2. 能适应各种讨论话题（社会、科技、生活、哲学等）
3. 有独特的说话风格和性格特点
4. 角色之间能形成有趣的观点对立

请严格按照以下 JSON 格式输出（不要输出任何其他内容）：
{{
    "personas": [
        {{
            "name": "角色名称（简短，不超过 5 个字）",
            "role_description": "角色描述（立场、性格、说话风格），不超过 30 字",
            "system_prompt": "完整的系统提示词，包含角色的立场、观点倾向、说话风格等，不超过 200 字"
        }}
    ]
}}

注意：
1. name 要简洁有辨识度
2. role_description 要概括角色的核心特点
4. system_prompt 须要求角色的发言不超过 100 字
4. 确保输出合法的 JSON 格式"""


class ConfigWizard:
    def __init__(self, console: Console = None, config_loader: ConfigLoader = None):
        self.console = console or Console()
        self.config_loader = config_loader or ConfigLoader()
        self.history: List[Callable] = []
        self.llm_client = LLMClient(LLMConfig.from_env())

    def _push_history(self, step: Callable):
        self.history.append(step)

    def _pop_history(self) -> Optional[Callable]:
        if self.history:
            return self.history.pop()
        return None

    def run(self) -> Optional[AppConfig]:
        self.console.clear()
        self._show_welcome()

        if self.config_loader.exists():
            config = self.config_loader.load()
            if config:
                action = self._ask_config_action()
                if action == "use":
                    return config
                elif action == "edit":
                    return self._edit_config(config)
                elif action == "new":
                    return self._create_new_config()
                else:
                    return None
            else:
                return self._create_new_config()
        else:
            return self._create_new_config()

    def _show_welcome(self):
        self.console.print(
            Panel.fit(
                """
[bold cyan]🔧 配置向导[/bold cyan]

[dim]本向导将帮助你创建或修改讨论配置文件。[/dim]

[bold yellow]配置项说明：[/bold yellow]
  • 角色（Personas）：参与讨论的 AI 角色
    - 名称：角色的显示名称
    - 描述：角色的简要介绍
    - 提示词：角色的系统提示，决定其行为和观点
    
  • 主题（Topic）：讨论的主题内容
  
  • 轮数（Max Rounds）：讨论的轮次数量（1-10）

[dim]提示：输入过程中可以输入 'back' 返回上一步[/dim]
            """,
                title="欢迎",
                border_style="blue",
            )
        )
        self.console.print()

    def _ask_config_action(self) -> str:
        self.console.print(
            Panel.fit(
                "[bold green]发现已有配置文件[/bold green]\n\n"
                "请选择操作：\n"
                "  [1] 使用现有配置\n"
                "  [2] 编辑现有配置\n"
                "  [3] 创建新配置\n"
                "  [4] 退出",
                border_style="green",
            )
        )

        choice = Prompt.ask(
            "\n请选择",
            choices=["1", "2", "3", "4"],
            default="1",
        )

        return {"1": "use", "2": "edit", "3": "new", "4": "exit"}.get(choice, "exit")

    def _create_new_config(self) -> Optional[AppConfig]:
        self.console.print("\n[bold cyan]━━━ 创建新配置 ━━━[/bold cyan]\n")

        personas = self._configure_personas()
        if not personas:
            return None

        topic = self._configure_topic()
        if topic is None:
            return None

        max_rounds = self._configure_rounds()
        if max_rounds is None:
            return None

        config = AppConfig(
            personas=personas,
            topic=topic,
            max_rounds=max_rounds,
        )

        return self._confirm_and_save(config)

    def _edit_config(self, config: AppConfig) -> Optional[AppConfig]:
        while True:
            self._show_config_preview(config)

            self.console.print(
                "\n[bold yellow]请选择要修改的项目：[/bold yellow]\n"
                "  [1] 修改角色配置\n"
                "  [2] 修改讨论主题\n"
                "  [3] 修改讨论轮数\n"
                "  [4] 保存并退出\n"
                "  [5] 放弃修改并退出"
            )

            choice = Prompt.ask(
                "\n请选择",
                choices=["1", "2", "3", "4", "5"],
                default="4",
            )

            if choice == "1":
                new_personas = self._configure_personas(config.personas)
                if new_personas:
                    config.personas = new_personas
            elif choice == "2":
                new_topic = self._configure_topic(config.topic)
                if new_topic is not None:
                    config.topic = new_topic
            elif choice == "3":
                new_rounds = self._configure_rounds(config.max_rounds)
                if new_rounds is not None:
                    config.max_rounds = new_rounds
            elif choice == "4":
                return self._confirm_and_save(config)
            elif choice == "5":
                if Confirm.ask("\n确定要放弃修改吗？", default=False):
                    return None

    def _configure_personas(
        self, existing: List[PersonaConfig] = None
    ) -> Optional[List[PersonaConfig]]:
        personas = list(existing) if existing else []

        while True:
            if personas:
                self._show_personas_table(personas)

                self.console.print(
                    "\n[bold yellow]角色操作：[/bold yellow]\n"
                    "  [1] 添加新角色\n"
                    "  [2] 修改现有角色\n"
                    "  [3] 删除角色\n"
                    "  [4] AI 随机生成角色\n"
                    "  [5] 完成角色配置"
                )

                choice = Prompt.ask(
                    "\n请选择",
                    choices=["1", "2", "3", "4", "5"],
                    default="5" if len(personas) >= 2 else "1",
                )

                if choice == "1":
                    persona = self._create_persona()
                    if persona:
                        personas.append(persona)
                elif choice == "2":
                    if personas:
                        idx = self._select_persona(personas)
                        if idx is not None:
                            new_persona = self._create_persona(personas[idx])
                            if new_persona:
                                personas[idx] = new_persona
                elif choice == "3":
                    if personas:
                        idx = self._select_persona(personas)
                        if idx is not None:
                            personas.pop(idx)
                elif choice == "4":
                    generated = self._generate_personas()
                    if generated:
                        personas.extend(generated)
                elif choice == "5":
                    if len(personas) < 2:
                        self.console.print(
                            "[red]至少需要配置 2 个角色才能进行讨论[/red]"
                        )
                        continue
                    return personas

            else:
                self.console.print(
                    "[bold]当前没有配置任何角色[/bold]\n"
                )
                self.console.print(
                    "[bold yellow]请选择：[/bold yellow]\n"
                    "  [1] 手动添加角色\n"
                    "  [2] AI 随机生成角色"
                )
                choice = Prompt.ask(
                    "\n请选择",
                    choices=["1", "2"],
                    default="2",
                )

                if choice == "1":
                    persona = self._create_persona()
                    if persona:
                        personas.append(persona)
                    else:
                        return None
                elif choice == "2":
                    generated = self._generate_personas()
                    if generated:
                        personas.extend(generated)
                    else:
                        continue

    async def _generate_personas_async(self, count: int) -> Optional[List[PersonaConfig]]:
        prompt = PERSONA_GENERATION_PROMPT.format(count=count)
        messages = [{"role": "user", "content": prompt}]

        full_response = ""
        async for chunk in self.llm_client.stream_chat(messages, max_tokens=2000):
            full_response += chunk

        try:
            json_match = re.search(r'\{[\s\S]*\}', full_response)
            if json_match:
                data = json.loads(json_match.group())
                personas = []
                for p in data.get("personas", []):
                    personas.append(
                        PersonaConfig(
                            name=p.get("name", ""),
                            role_description=p.get("role_description", ""),
                            system_prompt=p.get("system_prompt", ""),
                        )
                    )
                if personas:
                    return personas
        except json.JSONDecodeError as e:
            self.console.print(f"[dim red]JSON 解析错误：{e}[/dim red]")

        preview = full_response[:200] + "..." if len(full_response) > 200 else full_response
        self.console.print(
            Panel.fit(
                "[bold red]角色生成失败[/bold red]\n\n"
                f"[dim]AI 返回内容预览：\n{preview}[/dim]",
                border_style="red",
            )
        )
        return None

    def _generate_personas(self) -> Optional[List[PersonaConfig]]:
        self.console.print(
            Panel.fit(
                "[bold cyan]AI 随机生成角色[/bold cyan]\n\n"
                "[dim]AI 将为你生成适合多话题讨论的辩论角色[/dim]",
                border_style="cyan",
            )
        )

        count_str = Prompt.ask(
            "\n[bold green]请输入要生成的角色数量（2-5）[/bold green]",
            default="3",
        )

        try:
            count = int(count_str)
            if count < 2 or count > 5:
                self.console.print("[red]数量必须在 2-5 之间，使用默认值 3[/red]")
                count = 3
        except ValueError:
            self.console.print("[red]无效输入，使用默认值 3[/red]")
            count = 3

        self.console.print("\n[dim]正在生成角色，请稍候...[/dim]")

        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self._generate_personas_async(count)
                )
                personas = future.result()
        else:
            personas = asyncio.run(self._generate_personas_async(count))

        if personas:
            self.console.print(f"\n[bold green]✅ 成功生成 {len(personas)} 个角色：[/bold green]")
            self._show_personas_table(personas)

            if Confirm.ask("\n是否使用这些角色？", default=True):
                return personas
            else:
                return None

        return None

    def _create_persona(
        self, existing: PersonaConfig = None
    ) -> Optional[PersonaConfig]:
        self.console.print(
            Panel.fit(
                f"[bold cyan]{'编辑角色' if existing else '添加新角色'}[/bold cyan]",
                border_style="cyan",
            )
        )

        default_name = existing.name if existing else ""
        name = self._prompt_with_back(
            f"角色名称",
            default=default_name,
        )
        if name is None:
            return None

        default_desc = existing.role_description if existing else ""
        description = self._prompt_with_back(
            f"角色描述（简要介绍这个角色的特点）",
            default=default_desc,
        )
        if description is None:
            return None

        self.console.print(
            "\n[dim]角色提示词示例：[/dim]"
            "\n[dim]你是一位专业的健身教练，名叫'健身教练'。你的观点是：减肥的核心在于运动...[/dim]\n"
        )

        default_prompt = existing.system_prompt if existing else ""
        system_prompt = self._prompt_with_back(
            f"角色提示词（决定角色的行为和观点）",
            default=default_prompt,
        )
        if system_prompt is None:
            return None

        return PersonaConfig(
            name=name,
            role_description=description,
            system_prompt=system_prompt,
        )

    def _select_persona(self, personas: List[PersonaConfig]) -> Optional[int]:
        self._show_personas_table(personas)
        choice = Prompt.ask(
            "\n请选择角色编号",
            choices=[str(i + 1) for i in range(len(personas))],
        )
        return int(choice) - 1

    def _show_personas_table(self, personas: List[PersonaConfig]):
        table = Table(title="\n当前角色列表", show_header=True, header_style="bold cyan")
        table.add_column("编号", style="dim", width=6)
        table.add_column("名称", style="green", width=12)
        table.add_column("描述", width=30)
        table.add_column("提示词预览", width=40)

        for i, p in enumerate(personas):
            prompt_preview = (
                p.system_prompt[:37] + "..."
                if len(p.system_prompt) > 40
                else p.system_prompt
            )
            table.add_row(str(i + 1), p.name, p.role_description, prompt_preview)

        self.console.print(table)

    def _configure_topic(self, default: str = "") -> Optional[str]:
        self.console.print(
            Panel.fit(
                "[bold cyan]讨论主题设置[/bold cyan]\n\n"
                "[dim]请输入讨论的主题，例如：[/dim]\n"
                "[dim]• 如何科学有效地减肥[/dim]\n"
                "[dim]• 人工智能是否会取代人类工作[/dim]\n"
                "[dim]• 远程办公的利与弊[/dim]",
                border_style="cyan",
            )
        )

        topic = self._prompt_with_back(
            "\n讨论主题",
            default=default,
        )

        return topic

    def _configure_rounds(self, default: int = 3) -> Optional[int]:
        self.console.print(
            Panel.fit(
                "[bold cyan]讨论轮数设置[/bold cyan]\n\n"
                "[dim]轮数决定了每个角色发言的次数[/dim]\n"
                "[dim]建议设置 2-5 轮，轮数越多讨论越深入，但耗时也越长[/dim]",
                border_style="cyan",
            )
        )

        while True:
            rounds_str = self._prompt_with_back(
                "\n讨论轮数（1-10）",
                default=str(default),
            )

            if rounds_str is None:
                return None

            try:
                rounds = int(rounds_str)
                if 1 <= rounds <= 10:
                    return rounds
                else:
                    self.console.print("[red]轮数必须在 1-10 之间[/red]")
            except ValueError:
                self.console.print("[red]请输入有效的数字[/red]")

    def _show_config_preview(self, config: AppConfig):
        self.console.print("\n")
        self._show_personas_table(config.personas)

        info_table = Table(show_header=False, box=None)
        info_table.add_column("项目", style="bold yellow", width=15)
        info_table.add_column("内容", style="white")
        info_table.add_row("讨论主题", config.topic or "[dim]未设置[/dim]")
        info_table.add_row("讨论轮数", str(config.max_rounds))

        self.console.print(info_table)

    def _confirm_and_save(self, config: AppConfig) -> Optional[AppConfig]:
        self.console.print("\n[bold cyan]━━━ 配置预览 ━━━[/bold cyan]")
        self._show_config_preview(config)

        if Confirm.ask("\n是否保存此配置？", default=True):
            if self.config_loader.save(config):
                self.console.print(
                    Panel.fit(
                        f"[bold green]✅ 配置已保存[/bold green]\n\n"
                        f"文件：{self.config_loader.config_path}",
                        border_style="green",
                    )
                )
                return config
            else:
                return None
        else:
            if Confirm.ask("是否放弃当前配置？", default=False):
                return None
            return self._confirm_and_save(config)

    def _prompt_with_back(self, prompt: str, default: str = "") -> Optional[str]:
        result = Prompt.ask(
            f"[bold green]{prompt}[/bold green]",
            default=default,
        )

        if result.lower() == "back":
            return None

        return result