import asyncio
from typing import AsyncGenerator, List, Optional
from openai import AsyncOpenAI
from config import LLMConfig
from models import Message, MessageRole

# API 调用超时时间（秒）：等待首个 chunk 的最长时间
_API_TIMEOUT = 60.0


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
        model_name: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)

        # 角色可指定独立模型，为空时 fallback 到全局配置
        effective_model = model_name if model_name else self.config.model_name

        try:
            stream = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=effective_model,
                    messages=api_messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=max_tokens,
                ),
                timeout=_API_TIMEOUT,
            )

            chunk_count = 0
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    chunk_count += 1
                    yield chunk.choices[0].delta.content

            # 0 chunk 说明模型名称有误或 API 返回了空响应
            if chunk_count == 0:
                yield f"\n[警告] 模型「{effective_model}」未返回任何内容，请检查模型名称是否正确"

        except asyncio.TimeoutError:
            yield f"\n[错误] 请求超时（>{_API_TIMEOUT:.0f}s），模型「{effective_model}」响应过慢，请检查网络或更换模型"
        except Exception as e:
            yield f"\n[错误] API 调用失败: {str(e)}"

    async def complete_chat(
        self,
        messages: List[dict],
        system_prompt: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> str:
        full_response = ""
        async for chunk in self.stream_chat(messages, system_prompt, model_name=model_name):
            full_response += chunk
        return full_response
