"""
语言检测模块
使用 fast-langdetect 库来检测文本的语言
"""
import asyncio
import os
import sys
from pathlib import Path
from fast_langdetect import LangDetectConfig, LangDetector
from language_detectors.base_language_detector import BaseLanguageDetector

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from resource_path import get_user_data_path, ensure_dir

# 模型装在用户数据目录的models文件夹下（可写）
MODEL_DIR = get_user_data_path("models")
# 确保模型目录存在
ensure_dir(MODEL_DIR)
# 配置 fast-langdetect 使用的模型目录
# config = LangDetectConfig(cache_dir=MODEL_DIR, model="full")
config = LangDetectConfig(cache_dir=MODEL_DIR, model="lite")
fast_langdetect_detector = LangDetector(config)

CJK_RANGES = [
    ('\u4e00', '\u9fff'),  # CJK Unified Ideographs
    ('\u3400', '\u4dbf'),  # CJK Unified Ideographs Extension A
    ('\u3000', '\u303f'),  # CJK Symbols and Punctuation
    ('\uff00', '\uffef'),  # Halfwidth and Fullwidth Forms
]

KOREAN_CHAR_RANGES = [
    ('\uac00', '\ud7af'),  # Hangul Syllables
    ('\u1100', '\u11ff'),  # Hangul Jamo
    ('\u3130', '\u318f'),  # Hangul Compatibility Jamo
]

KANA_RANGES = [
    ('\u3040', '\u309f'),  # Hiragana
    ('\u30a0', '\u30ff'),  # Katakana
]

def char_ratio_in_charset(text: str, char_ranges: list) -> float:
    if not text:
        return 0.0

    total_chars = len(text)
    matching_chars = 0
    for char in text:
        for start, end in char_ranges:
            if start <= char <= end:
                matching_chars += 1
                break

    return matching_chars / total_chars

def handle_special_cases(text: str) -> str:
    if len(text) <= 4 and '々' in text:
        return 'ja'
    if len(text) <= 6 and char_ratio_in_charset(text, KANA_RANGES) >= 0.5:
        return 'ja'
    if len(text) <= 6 and char_ratio_in_charset(text, CJK_RANGES) >= 0.5:
        return 'zh'
    return None

class FasttextDetector(BaseLanguageDetector):
    """语言检测器"""
    
    def __init__(self):
        """初始化检测器"""
        pass
    
    def detect(self, text: str) -> dict:
        """
        同步检测文本的语言
        
        Args:
            text: 要检测的文本
        
        Returns:
            包含语言信息的字典，格式为：
            {
                'language': 语言代码 (如 'en', 'zh-cn', 'ja' 等),
                'confidence': 置信度 (0.0-1.0)
            }
        """
        if not text or not text.strip():
            return {
                'language': 'unknown',
                'confidence': 0.0
            }
        
        if result := handle_special_cases(text):
            return {
                'language': result,
                'confidence': 1.0
            }
        
        try:
            # 使用 fast-langdetect 检测语言（同步调用）
            result = fast_langdetect_detector.detect(text)[0]
            lang_code = result['lang'].lower()
            confidence = result['score']
            
            # 语言代码映射到更友好的名称
            language_substitutes = {
                'yue': 'zh',
                'wuu': 'zh',
                'cmn': 'zh',
            }
            lang_code = language_substitutes.get(lang_code, lang_code)
            
            return {
                'language': lang_code,
                'confidence': confidence  # fast-langdetect 提供置信度
            }
        
        except Exception as e:
            print(f"语言检测错误: {e}")
            return {
                'language': 'error',
                'confidence': 0.0
            }
    
    async def detect_async(self, text: str) -> dict:
        """
        异步检测文本的语言（在线程池中运行同步方法）
        
        Args:
            text: 要检测的文本
        
        Returns:
            包含语言信息的字典
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.detect, text)


# 创建全局检测器实例
detector = FasttextDetector()


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("语言检测测试")
    print("=" * 60)
    
    test_texts = [
        "Hello, how are you?",
        "你好，你好吗？",
        "こんにちは、元気ですか？",
        "Bonjour, comment allez-vous?",
        "Hola, ¿cómo estás?",
        "안녕하세요, 어떻게 지내세요?",
        "Привет, как дела?",
        "مرحبا، كيف حالك؟",
        "哎",
        "哎呀",
        "我",
        "我々",
        "僕は",
        "",
    ]
    
    print()
    
    async def _run_tests():
        for text in test_texts:
            result = detector.detect(text)
            print(f"文本: {text}")
            print(f"  语言: {result['language']}")
            print(f"  置信度: {result['confidence']:.2%}")
            print()
        
        print("=" * 60)
        print("测试完成")
        print("=" * 60)
    
    asyncio.run(_run_tests())
