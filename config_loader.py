import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel

from config import PersonaConfig


@dataclass
class AppConfig:
    personas: List[PersonaConfig] = field(default_factory=list)
    topic: str = ""
    max_rounds: int = 3

    def to_dict(self) -> dict:
        return {
            "personas": [
                {
                    "name": p.name,
                    "role_description": p.role_description,
                    "system_prompt": p.system_prompt,
                }
                for p in self.personas
            ],
            "topic": self.topic,
            "max_rounds": self.max_rounds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        personas = []
        for p in data.get("personas", []):
            personas.append(
                PersonaConfig(
                    name=p.get("name", ""),
                    role_description=p.get("role_description", ""),
                    system_prompt=p.get("system_prompt", ""),
                )
            )
        return cls(
            personas=personas,
            topic=data.get("topic", ""),
            max_rounds=data.get("max_rounds", 3),
        )


class ConfigLoader:
    DEFAULT_CONFIG_PATH = "config.json"

    def __init__(self, config_path: str = None, console: Console = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.console = console or Console()

    def exists(self) -> bool:
        return os.path.exists(self.config_path)

    def load(self) -> Optional[AppConfig]:
        if not self.exists():
            return None

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            config = AppConfig.from_dict(data)

            if not self._validate_config(config):
                return None

            return config

        except json.JSONDecodeError as e:
            self.console.print(
                Panel.fit(
                    f"[bold red]配置文件格式错误[/bold red]\n\n"
                    f"文件：{self.config_path}\n"
                    f"错误：{str(e)}\n\n"
                    f"[dim]请检查 JSON 格式是否正确（注意引号、逗号、括号匹配）[/dim]",
                    border_style="red",
                )
            )
            return None

        except Exception as e:
            self.console.print(
                Panel.fit(
                    f"[bold red]读取配置文件失败[/bold red]\n\n"
                    f"文件：{self.config_path}\n"
                    f"错误：{str(e)}",
                    border_style="red",
                )
            )
            return None

    def save(self, config: AppConfig) -> bool:
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.console.print(
                Panel.fit(
                    f"[bold red]保存配置文件失败[/bold red]\n\n"
                    f"文件：{self.config_path}\n"
                    f"错误：{str(e)}",
                    border_style="red",
                )
            )
            return False

    def _validate_config(self, config: AppConfig) -> bool:
        errors = []

        if not config.personas:
            errors.append("缺少角色配置（personas）")
        else:
            for i, persona in enumerate(config.personas):
                if not persona.name:
                    errors.append(f"角色 {i+1} 缺少名称（name）")
                if not persona.system_prompt:
                    errors.append(f"角色 {i+1} 缺少提示词（system_prompt）")

        if config.max_rounds < 1 or config.max_rounds > 10:
            errors.append(f"轮数（max_rounds）必须在 1-10 之间，当前值：{config.max_rounds}")

        if errors:
            self.console.print(
                Panel.fit(
                    "[bold red]配置验证失败[/bold red]\n\n"
                    + "\n".join(f"• {e}" for e in errors),
                    border_style="red",
                )
            )
            return False

        return True

    def get_default_config(self) -> AppConfig:
        from config import PERSONAS

        return AppConfig(
            personas=[PERSONAS["fitness_coach"], PERSONAS["nutritionist"]],
            topic="",
            max_rounds=3,
        )