"""
OpenRouter translation API implementation using hosted large language models.
"""
import asyncio
import aiohttp
import json
import os
from typing import Optional

from .base_translation_api import BaseTranslationAPI


class OpenRouterAPI(BaseTranslationAPI):
    """Translation API that routes requests through OpenRouter."""

    SUPPORTS_CONTEXT = True

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "google/gemini-2.5-flash-lite:nitro",
        base_url: str = "https://openrouter.ai/api/v1/chat/completions",
        temperature: float = 0.2,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key is not set. Set OPENROUTER_API_KEY in the environment or pass it explicitly."
            )

        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.system_prompt = (
            "You are a helpful translation assistant. Always respond with a concise, light, and friendly tone. "
            "Return only the translated text with no additional commentary."
        )
        self.app_url = os.getenv("OPENROUTER_APP_URL", "")
        self.app_title = os.getenv("OPENROUTER_APP_TITLE", "")
        
        # 创建长连接会话
        self._session_timeout = aiohttp.ClientTimeout(total=self.timeout)
        self._session = None
        self._loop = None
        
        # 提前进行一次翻译，以建立长连接
        self.translate("Hello", source_language="auto", target_language="zh-CN")
    
    async def _get_session(self):
        """获取或创建 HTTP 长连接会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._session_timeout)
        return self._session
    
    async def _reset_session(self):
        """重置长连接会话（关闭旧的，创建新的）"""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None
        # 创建新的会话
        return await self._get_session()
    
    async def close(self):
        """关闭 HTTP 长连接会话"""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None
    
    async def _translate_async(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: Optional[str] = None,
    ) -> str:
        """
        异步翻译方法（带重试逻辑）
        
        Args:
            text: 要翻译的文本
            source_language: 源语言代码
            target_language: 目标语言代码
            context: 可选的上下文信息
        
        Returns:
            翻译后的文本
        """
        if not text:
            return ""

        context_block = context.strip() if context and context.strip() else "None."
        source_descriptor = (
            source_language
            if source_language and source_language.lower() != "auto"
            else "auto-detect the source language"
        )

        user_message = (
            "Context Section:\n"
            f"{context_block}\n\n"
            "Output Format:\n"
            "Provide only the translated text without quotation marks, prefixes, or explanations.\n\n"
            "Translation Principles:\n"
            "1. Keep the tone short, breezy, and friendly.\n"
            "2. Preserve the original meaning, named entities, and essential formatting.\n"
            "3. Prefer natural phrasing that reads well for the target audience.\n\n"
            "4. Fix any obvious recognition errors in the source text.\n\n"
            "Task:\n"
            f"Translate the text below inside <text> and </text> from **{source_descriptor}** to **{target_language}**.\n\n"
            "Text To Translate:\n"
            f"<text>{text}</text>"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": self.temperature,
            "provider": {
                "sort": "latency"
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.app_url:
            headers["HTTP-Referer"] = self.app_url
        if self.app_title:
            headers["X-Title"] = self.app_title
        
        # 尝试指定次数
        for attempt in range(self.max_retries + 1):
            try:
                # 获取长连接会话
                session = await self._get_session()
                
                # 发送请求（使用长连接）
                async with session.post(self.base_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        response_body = await response.text()
                        
                        # 解析 JSON 响应
                        try:
                            data = json.loads(response_body)
                        except json.JSONDecodeError:
                            return "[ERROR] Failed to decode OpenRouter response"
                        
                        # 提取翻译结果
                        choices = data.get("choices") or []
                        if not choices:
                            message = data.get("error", {}).get("message", "No choices returned")
                            return f"[ERROR] OpenRouter response missing translation: {message}"

                        content = choices[0].get("message", {}).get("content")
                        if not content:
                            return "[ERROR] OpenRouter returned an empty message"

                        return content.strip()
                    else:
                        error_detail = await response.text()
                        return f"[ERROR] OpenRouter HTTP {response.status}: {error_detail.strip()}"
            
            except (aiohttp.ClientConnectionError, aiohttp.ClientSSLError, 
                    ConnectionError, BrokenPipeError) as e:
                # 长连接断掉的错误
                if attempt < self.max_retries:
                    # 还有重试次数，重置会话后重试
                    try:
                        await self._reset_session()
                    except Exception:
                        pass
                    # 继续下一次尝试
                    continue
                else:
                    # 重试次数已用完，返回错误
                    return f"[ERROR] Connection failed after {self.max_retries + 1} attempts: {str(e)}"
            
            except asyncio.TimeoutError:
                if attempt < self.max_retries:
                    # 超时也进行重试
                    try:
                        await self._reset_session()
                    except Exception:
                        pass
                    continue
                else:
                    return f"[ERROR] Translation timeout (>{self.timeout}s) after {self.max_retries + 1} attempts"
            
            except Exception as e:
                # 其他异常直接返回错误
                return f"[ERROR] OpenRouter request error: {str(e)}"
        
        # 不应该到达这里
        return "[ERROR] Unknown error after all retry attempts"
    
    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            if self._loop and not self._loop.is_closed():
                if self._loop.is_running():
                    # 如果事件循环正在运行，使用 create_task 替代
                    self._loop.create_task(self.close())
                else:
                    # 否则直接运行关闭任务
                    self._loop.run_until_complete(self.close())
                self._loop.close()
                self._loop = None
        except Exception:
            # 忽略清理过程中的错误
            pass

    def translate(
        self,
        text: str,
        source_language: str = "auto",
        target_language: str = "zh-CN",
        context: Optional[str] = None,
    ) -> str:
        """
        同步翻译接口（包装异步调用）
        
        Args:
            text: 要翻译的文本
            source_language: 源语言代码
            target_language: 目标语言代码
            context: 可选的上下文信息
        
        Returns:
            翻译后的文本
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 没有运行中的事件循环，复用或创建新的
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
            loop = self._loop
            asyncio.set_event_loop(loop)
        
        # 同步执行异步翻译
        return loop.run_until_complete(
            self._translate_async(text, source_language, target_language, context)
        )
