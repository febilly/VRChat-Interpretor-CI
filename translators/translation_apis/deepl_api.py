"""
DeepL API 翻译实现
使用 DeepL 官方 Python 库
需要在环境变量中设置 DEEPL_API_KEY
"""
import os
from typing import Optional
from .base_translation_api import BaseTranslationAPI

try:
    import deepl
except ImportError:
    raise ImportError(
        "DeepL 官方库未安装。请运行以下命令安装：\n"
        "pip install --upgrade deepl"
    )

FORMALITY = "prefer_more"

class DeepLAPI(BaseTranslationAPI):
    """DeepL 翻译 API 封装（使用官方库）"""
    
    # DeepL 原生支持上下文
    SUPPORTS_CONTEXT = True
    
    def __init__(self, api_key: str = None):
        """
        初始化 DeepL 客户端
        
        Args:
            api_key: DeepL API Key（如果为 None，从环境变量 DEEPL_API_KEY 获取）
        """
        # 从参数或环境变量获取 API Key
        auth_key = api_key or os.environ.get('DEEPL_API_KEY')
        
        if not auth_key:
            raise ValueError(
                "DeepL API Key 未设置。请通过以下方式之一设置：\n"
                "1. 在 .env 文件中添加: DEEPL_API_KEY=your-api-key\n"
                "2. 设置环境变量: DEEPL_API_KEY=your-api-key\n"
                "3. 初始化时传入: DeepLAPI(api_key='your-api-key')"
            )
        
        # 创建 DeepL 客户端（官方库会自动处理 Free/Pro 端点）
        self.client = deepl.DeepLClient(auth_key)
                
        # 提前进行一次翻译，以建立长连接
        self.translate("你好", source_language="auto", target_language="en")

    
    def translate(self, text: str, source_language: str = 'auto', 
                  target_language: str = 'zh-CN', context: Optional[str] = None) -> str:
        """
        翻译文本
        
        Args:
            text: 要翻译的文本
            source_language: 源语言代码（'auto' 表示自动检测）
            target_language: 目标语言代码
            context: 可选的上下文信息（DeepL 原生支持）
        
        Returns:
            翻译后的文本
        """
        try:
            # 处理目标语言代码
            # DeepL 的语言代码是大写的，如 'ZH', 'EN', 'DE' 等
            target_lang = target_language.upper()
            
            # 特殊处理语言代码映射
            lang_map = {
                'zh': 'ZH-HANS',
                'zh-cn': 'ZH-HANS',
                'zh-tw': 'ZH-HANT',
                'en': 'EN-US',
                'pt': 'PT-BR',
            }
            target_lang = lang_map.get(target_lang.lower(), target_lang)
            
            # 处理源语言
            source_lang = None if source_language.lower() == 'auto' else source_language.upper()
            
            # 调用 DeepL API
            # 如果提供了上下文，使用 context 参数
            if context:
                result = self.client.translate_text(
                    text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    context=context,
                    formality=FORMALITY,
                    model_type='prefer_quality_optimized',
                )
            else:
                result = self.client.translate_text(
                    text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    formality=FORMALITY,
                    model_type='prefer_quality_optimized',
                )
            
            return result.text
        
        except deepl.AuthorizationException:
            return "[ERROR] DeepL API 认证失败，请检查 API Key"
        except deepl.QuotaExceededException:
            return "[ERROR] DeepL API 配额已用尽"
        except deepl.DeepLException as e:
            return f"[ERROR] DeepL API error: {str(e)}"
        except Exception as e:
            return f"[ERROR] {str(e)}"


# 测试代码
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    
    # 加载环境变量
    load_dotenv()
    
    print("=" * 60)
    print("DeepL API 翻译测试（使用官方库）")
    print("=" * 60)
    
    # 检查 API Key
    if 'DEEPL_API_KEY' not in os.environ:
        print("\n❌ 错误：未找到 DEEPL_API_KEY 环境变量")
        print("\n请在 .env 文件中添加：")
        print("DEEPL_API_KEY=your-deepl-api-key")
        print("\n获取 API Key: https://www.deepl.com/pro-api")
        sys.exit(1)
    
    try:
        # 创建 API 实例
        api = DeepLAPI()
        print(f"\n✓ DeepL API 初始化成功")
        
        # 获取账户使用情况
        try:
            usage = api.client.get_usage()
            if usage.character.valid:
                print(f"  字符使用: {usage.character.count:,} / {usage.character.limit:,}")
                remaining = usage.character.limit - usage.character.count
                print(f"  剩余字符: {remaining:,}")
        except Exception as e:
            print(f"  无法获取使用情况: {e}")
        
        # 测试翻译
        test_cases = [
            ("Hello, world!", "auto", "zh-CN"),
            ("你好，世界！", "auto", "EN"),
            ("This is a test.", "EN", "zh-CN"),
        ]
        
        print("\n" + "-" * 60)
        print("翻译测试")
        print("-" * 60)
        
        for text, source, target in test_cases:
            print(f"\n原文: {text}")
            print(f"语言: {source} → {target}")
            result = api.translate(text, source, target)
            print(f"译文: {result}")
        
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
    
    except ValueError as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
