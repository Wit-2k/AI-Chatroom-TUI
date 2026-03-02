import asyncio
from typing import AsyncGenerator, List, Optional
from openai import AsyncOpenAI
from config import LLMConfig
from models import Message, MessageRole


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    async def stream_chat(
        self,
        messages: List[dict],
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
    ) -> AsyncGenerator[str, None]:
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)

        try:
            stream = await self.client.chat.completions.create(
                model=self.config.model_name,
                messages=api_messages,
                stream=True,
                temperature=0.7,
                max_tokens=max_tokens,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            yield f"\n[错误] API 调用失败: {str(e)}"

    async def complete_chat(
        self,
        messages: List[dict],
        system_prompt: Optional[str] = None,
    ) -> str:
        full_response = ""
        async for chunk in self.stream_chat(messages, system_prompt):
            full_response += chunk
        return full_response