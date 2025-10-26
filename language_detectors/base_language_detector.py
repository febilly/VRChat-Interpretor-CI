"""
语言检测器抽象基类
定义了语言检测器的通用接口
"""
from abc import ABC, abstractmethod
from typing import Dict


class BaseLanguageDetector(ABC):
    """语言检测器抽象基类"""
    
    @abstractmethod
    def detect(self, text: str) -> Dict[str, any]:
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
        pass
    
    @abstractmethod
    async def detect_async(self, text: str) -> Dict[str, any]:
        """
        异步检测文本的语言
        
        Args:
            text: 要检测的文本
        
        Returns:
            包含语言信息的字典，格式为：
            {
                'language': 语言代码 (如 'en', 'zh-cn', 'ja' 等),
                'confidence': 置信度 (0.0-1.0)
            }
        """
        pass
