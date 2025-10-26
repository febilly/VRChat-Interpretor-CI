"""
简单的中英文语言检测器
基于字符范围判断文本是中文还是英文
"""
import re
from typing import Dict
from language_detectors.base_language_detector import BaseLanguageDetector


class EnZhDetector(BaseLanguageDetector):
    """简单的中英文语言检测器"""
    
    def __init__(self):
        # 中文字符的 Unicode 范围
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
        # 英文字符的模式（字母）
        self.english_pattern = re.compile(r'[a-zA-Z]')
    
    def detect(self, text: str) -> Dict[str, any]:
        """
        同步检测文本的语言
        
        Args:
            text: 要检测的文本
        
        Returns:
            包含语言信息的字典
        """
        if not text or not text.strip():
            return {
                'language': 'unknown',
                'confidence': 0.0
            }
        
        # 统计中文和英文字符数量
        chinese_chars = len(self.chinese_pattern.findall(text)) * 3
        english_chars = len(self.english_pattern.findall(text))
        
        total_chars = chinese_chars + english_chars
        
        # 如果没有中英文字符，返回未知
        if total_chars == 0:
            return {
                'language': 'unknown',
                'confidence': 0.0
            }
        
        # 计算中文和英文的比例
        chinese_ratio = chinese_chars / total_chars
        english_ratio = english_chars / total_chars
        
        # 判断语言
        if chinese_ratio > english_ratio:
            return {
                'language': 'zh-cn',
                'confidence': chinese_ratio
            }
        else:
            return {
                'language': 'en',
                'confidence': english_ratio
            }
    
    async def detect_async(self, text: str) -> Dict[str, any]:
        """
        异步检测文本的语言
        
        Args:
            text: 要检测的文本
        
        Returns:
            包含语言信息的字典
        """
        # 对于简单的检测，直接调用同步方法
        return self.detect(text)


# 测试代码
if __name__ == "__main__":
    detector = EnZhDetector()
    
    # 测试用例
    test_cases = [
        "Hello, how are you?",
        "你好，今天天气怎么样？",
        "This is a mixed 混合 sentence",
        "完全是中文的句子",
        "Completely English sentence",
        "中英mixed很多",
        "123456",
        "",
    ]
    
    print("=" * 60)
    print("中英文语言检测器测试")
    print("=" * 60)
    
    for text in test_cases:
        result = detector.detect(text)
        print(f"\n文本: {text if text else '(空字符串)'}")
        print(f"语言: {result['language']}")
        print(f"置信度: {result['confidence']:.2f}")
