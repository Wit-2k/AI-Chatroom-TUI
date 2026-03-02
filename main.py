#!/usr/bin/env python3
import asyncio
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from config import LLMConfig, PERSONAS
from config_loader import ConfigLoader, AppConfig
from wizard import ConfigWizard
from engine import DiscussionEngine


def print_welcome(console: Console):
    console.clear()
    console.print(
        Panel.fit(
            """
[bold cyan]🤖 AI 讨论室 - 多智能体辩论系统[/bold cyan]

[dim]这是一个多 AI 角色讨论系统，不同的 AI 角色将围绕
你提出的主题展开辩论，最后生成结构化的讨论总结。[/dim]

[bold green]启动选项：[/bold green]
  • 直接回车：使用配置文件或默认设置开始讨论
  • 输入 'config'：打开配置向导
  • 输入 'quit'：退出程序
            """,
            title="欢迎",
            border_style="blue",
        )
    )
    console.print()


def check_api_key(console: Console) -> bool:
    config = LLMConfig.from_env()
    if not config.api_key or config.api_key == "your_api_key_here":
        console.print(
            Panel.fit(
                "[bold red]❌ 错误：未配置 API Key[/bold red]\n\n"
                "请在 .env 文件中设置你的 OPENAI_API_KEY\n"
                "你可以复制 .env.example 为 .env 并填入你的 API Key\n\n"
                "[dim]支持的 API 提供商：\n"
                "• OpenAI (默认)\n"
                "• DeepSeek (设置 OPENAI_BASE_URL=https://api.deepseek.com/v1)\n"
                "• 其他 OpenAI 兼容 API[/dim]",
                border_style="red",
            )
        )
        return False
    return True


def get_or_create_config(console: Console) -> AppConfig:
    loader = ConfigLoader()

    if loader.exists():
        config = loader.load()
        if config:
            console.print(
                Panel.fit(
                    f"[bold green]已加载配置文件[/bold green]\n\n"
                    f"[dim]角色：{' vs '.join([p.name for p in config.personas])}[/dim]\n"
                    f"[dim]主题：{config.topic or '（未设置）'}[/dim]\n"
                    f"[dim]轮数：{config.max_rounds}[/dim]",
                    border_style="green",
                )
            )
            return config

    default_config = loader.get_default_config()
    console.print(
        Panel.fit(
            "[bold yellow]使用默认配置[/bold yellow]\n\n"
            f"[dim]角色：{' vs '.join([p.name for p in default_config.personas])}[/dim]\n"
            f"[dim]轮数：{default_config.max_rounds}[/dim]",
            border_style="yellow",
        )
    )
    return default_config


def prompt_for_topic(console: Console, default_topic: str = "") -> str:
    if default_topic:
        topic = Prompt.ask(
            "\n[bold green]讨论主题[/bold green]",
            default=default_topic,
        )
    else:
        topic = Prompt.ask(
            "\n[bold green]请输入讨论主题[/bold green]",
            default="如何科学有效地减肥",
        )
    return topic


async def run_discussion(console: Console, config: AppConfig):
    topic = config.topic
    if not topic:
        topic = prompt_for_topic(console)
    else:
        use_default = Confirm.ask(
            f"\n使用配置中的主题「{topic}」？",
            default=True,
        )
        if not use_default:
            topic = prompt_for_topic(console, topic)

    if not topic.strip():
        console.print("[red]主题不能为空，使用默认主题。[/red]")
        topic = "如何科学有效地减肥"

    console.print()
    console.print(f"[bold]开始讨论：{topic}[/bold]")
    console.print(f"[dim]轮次：{config.max_rounds}[/dim]")
    console.print()

    engine = DiscussionEngine(
        topic=topic,
        personas=config.personas,
        max_rounds=config.max_rounds,
    )

    await engine.run()


async def main():
    console = Console()

    print_welcome(console)

    if not check_api_key(console):
        sys.exit(1)

    config = get_or_create_config(console)

    while True:
        action = Prompt.ask(
            "\n[bold cyan]请选择操作[/bold cyan]",
            default="start",
        ).lower().strip()

        if action == "quit" or action == "exit" or action == "q":
            console.print("\n[bold green]感谢使用 AI 讨论室！再见！[/bold green]")
            break

        if action == "config" or action == "c":
            wizard = ConfigWizard(console=console)
            new_config = wizard.run()
            if new_config:
                config = new_config
            console.print()
            continue

        if action == "start" or action == "s" or action == "":
            await run_discussion(console, config)

            continue_discussion = Prompt.ask(
                "\n[bold cyan]是否开始新的讨论？[/bold cyan]",
                choices=["y", "n", "config"],
                default="y",
            )

            if continue_discussion.lower() == "n":
                console.print("\n[bold green]感谢使用 AI 讨论室！再见！[/bold green]")
                break
            elif continue_discussion.lower() == "config":
                wizard = ConfigWizard(console=console)
                new_config = wizard.run()
                if new_config:
                    config = new_config
                console.print()

            console.print()
            continue

        console.print(
            "[dim]无效命令。直接回车开始讨论，输入 'config' 配置，输入 'quit' 退出。[/dim]"
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        Console().print("\n[yellow]用户中断，程序退出。[/yellow]")
        sys.exit(0)