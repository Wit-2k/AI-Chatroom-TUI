import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    api_key: str
    base_url: str
    model_name: str

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model_name=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        )


@dataclass
class PersonaConfig:
    name: str
    role_description: str
    persona_prompt: str
    interaction_examples: str = ""
    model_name: str = ""

    @property
    def system_prompt(self) -> str:
        """动态拼接完整 system_prompt，供 LLM 调用使用。"""
        from config_loader import _INTERACTION_RULES_TEMPLATE
        return self.persona_prompt + _INTERACTION_RULES_TEMPLATE.format(
            examples=self.interaction_examples
        )


PERSONAS = {
    "fitness_coach": PersonaConfig(
        name="健身教练",
        role_description="专业的健身教练，主张通过运动来减肥",
        persona_prompt='你是一位专业的健身教练，名叫"健身教练"。你的观点是：减肥的核心在于运动和热量消耗。你相信通过规律的运动、力量训练和有氧运动可以健康有效地减肥。引用运动科学和健身知识支持你的观点，保持专业但友好的态度。',
        interaction_examples='「你说的饮食控制有道理，但运动才是关键……」、「我不同意X的观点，数据显示……」',
    ),
    "nutritionist": PersonaConfig(
        name="营养师",
        role_description="专业营养师，主张通过饮食控制来减肥",
        persona_prompt='你是一位专业的营养师，名叫"营养师"。你的观点是：减肥的核心在于饮食控制和热量摄入管理。你相信通过合理的营养搭配、控制热量摄入可以健康有效地减肥。引用营养学知识支持你的观点，保持专业但友好的态度。',
        interaction_examples='「X提到运动消耗，但饮食摄入才是根本……」、「我理解X的立场，但营养学研究表明……」',
    ),
}

SUMMARY_PROMPT = """你是一个讨论总结专家。请根据以下对话内容，生成一份结构化的总结报告。

对话主题：{topic}

对话内容：
{conversation}

请严格按照以下 JSON 格式输出（不要输出任何其他内容，不要加 markdown 代码块）：
{{
    "title": "为本次讨论生成一个简短的标题（10字以内）",
    "summary": "用2-3句话概括本次讨论最激烈的交锋与核心结论（50字以内）",
    "content": "## 讨论总结\\n\\n### 各方核心立场\\n- 逐一列出每位参与者的核心观点与立场\\n\\n### 关键交锋时刻\\n- 列出讨论中最具代表性的观点碰撞与直接交锋，注明是谁回应了谁\\n\\n### 主要分歧点\\n- 列出各方始终未能达成共识的核心分歧\\n\\n### 达成的共识\\n- 列出各方认同或相互借鉴的观点\\n\\n### 综合结论\\n- 给出一个综合各方视角的结论性判断"
}}

【严格要求】
1. title 必须简洁，适合作为文件名，不含特殊字符
2. summary 是用于终端显示的简短摘要，应体现交锋感，50字以内
3. content 字段的值必须是单行字符串，换行用 \\n 表示，不能有真实的换行符
4. content 中的「关键交锋时刻」章节必须具体描述谁回应了谁的哪个论点
5. 输出必须是合法的 JSON，不要在 JSON 前后添加任何说明文字或 ```json 代码块标记"""