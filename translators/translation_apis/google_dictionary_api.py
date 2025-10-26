"""
Google Dictionary API 翻译实现
使用 Google Dictionary Extension API
"""
import asyncio
import aiohttp
import urllib.parse
import json
from typing import Optional
from .base_translation_api import BaseTranslationAPI


class GoogleDictionaryAPI(BaseTranslationAPI):
    """Google Dictionary 翻译 API 封装"""
    
    # Google Dictionary API 不支持原生上下文
    SUPPORTS_CONTEXT = False
    
    def __init__(self):
        """初始化 API 配置"""
        self.api_key = "AIzaSyA6EEtrDCfBkHV8uU2lgGY-N383ZgAOo7Y"
        self.api_endpoint = "https://dictionaryextension-pa.googleapis.com/v1/dictionaryExtensionData"
        self.strategy = "2"
        self.timeout = 8  # 超时时间（秒）
    
    async def _translate_async(self, text: str, source_language: str, target_language: str) -> str:
        """
        异步翻译方法
        
        Args:
            text: 要翻译的文本
            source_language: 源语言代码（此 API 会自动检测，该参数保留以兼容接口）
            target_language: 目标语言代码
        
        Returns:
            翻译后的文本
        """
        # URL 编码文本
        encoded_text = urllib.parse.quote(text)
        
        # 构建请求 URL
        url = (f"{self.api_endpoint}?"
               f"language={target_language}&"
               f"key={self.api_key}&"
               f"term={encoded_text}&"
               f"strategy={self.strategy}")
        
        # 设置请求头（模拟 Chrome 扩展）
        headers = {
            'x-referer': 'chrome-extension://mgijmajocgfcbeboacabfgobmjgjcoja'
        }
        
        try:
            # 创建超时配置
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            # 发送请求
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        response_body = await response.text()
                        
                        # 解析 JSON 响应
                        data = json.loads(response_body)
                        
                        # 提取翻译结果
                        if 'translateResponse' in data:
                            translated_text = data['translateResponse'].get('translateText', '')
                            return translated_text
                        else:
                            return "[ERROR] Translation Failed: Unexpected API response format"
                    else:
                        return f"[ERROR] HTTP {response.status}: {await response.text()}"
        
        except asyncio.TimeoutError:
            return f"[ERROR] Translation timeout (>{self.timeout}s)"
        except Exception as e:
            return f"[ERROR] {str(e)}"
    
    def translate(self, text: str, source_language: str = 'auto', 
                  target_language: str = 'zh-CN', context: Optional[str] = None) -> str:
        """
        同步翻译接口（包装异步调用）
        
        Args:
            text: 要翻译的文本
            source_language: 源语言代码
            target_language: 目标语言代码
            context: 上下文信息（此 API 不支持，如果提供将抛出异常）
        
        Returns:
            翻译后的文本
        
        Raises:
            NotImplementedError: 如果提供了 context 参数
        """
        # 检查是否提供了上下文参数
        if context is not None:
            raise NotImplementedError(
                "Google Dictionary API 不支持原生上下文功能。"
                "请使用 ContextAwareTranslator 包装器来启用上下文感知翻译。"
            )
        
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 没有运行中的事件循环，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # 同步执行异步翻译
        return loop.run_until_complete(
            self._translate_async(text, source_language, target_language)
        )
