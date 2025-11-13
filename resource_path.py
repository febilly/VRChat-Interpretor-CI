"""
资源路径管理模块
提供统一的资源文件路径解析，支持开发环境和PyInstaller打包环境
"""
import os
import sys
from pathlib import Path


def get_resource_path(relative_path: str) -> str:
    """
    获取资源文件的绝对路径
    
    在开发环境下，返回相对于项目根目录的路径
    在PyInstaller打包环境下，返回相对于临时解压目录的路径
    
    Args:
        relative_path: 相对路径（相对于项目根目录）
                      例如: 'hot_words/zh-cn.txt', 'ui/templates/index.html'
    
    Returns:
        资源文件的绝对路径
    
    Examples:
        >>> get_resource_path('hot_words/zh-cn.txt')
        'C:\\path\\to\\project\\hot_words\\zh-cn.txt'  # 开发环境
        'C:\\Users\\xxx\\AppData\\Local\\Temp\\_MEIxxxxxx\\hot_words\\zh-cn.txt'  # 打包环境
    """
    # 检查是否在PyInstaller打包环境中运行
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller打包环境：使用临时解压目录
        base_path = sys._MEIPASS
    else:
        # 开发环境：使用当前文件所在目录（项目根目录）
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    # 组合基础路径和相对路径
    resource_path = os.path.join(base_path, relative_path)
    
    return resource_path


def get_base_path() -> str:
    """
    获取项目基础路径
    
    Returns:
        项目根目录的绝对路径
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))


def ensure_dir(directory_path: str) -> None:
    """
    确保目录存在，如果不存在则创建
    
    Args:
        directory_path: 目录路径（可以是相对路径或绝对路径）
    """
    # 如果是相对路径，转换为绝对路径
    if not os.path.isabs(directory_path):
        directory_path = get_resource_path(directory_path)
    
    # 创建目录（如果不存在）
    os.makedirs(directory_path, exist_ok=True)


def get_user_data_path(relative_path: str = '') -> str:
    """
    获取用户数据目录路径（用于存储配置、日志等可写文件）
    
    在打包环境下，PyInstaller的_MEIPASS目录是只读的，
    需要使用用户数据目录来存储可写文件
    
    Args:
        relative_path: 相对于用户数据目录的路径
    
    Returns:
        用户数据目录的绝对路径
    """
    if getattr(sys, 'frozen', False):
        # 打包环境：使用可执行文件所在目录
        base_path = os.path.dirname(sys.executable)
    else:
        # 开发环境：使用项目根目录
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    if relative_path:
        return os.path.join(base_path, relative_path)
    return base_path


# 便捷函数
def get_hot_words_path(filename: str) -> str:
    """获取公共热词文件路径"""
    return get_resource_path(os.path.join('hot_words', filename))


def get_hot_words_private_path(filename: str) -> str:
    """获取私人热词文件路径（可写）"""
    return get_user_data_path(os.path.join('hot_words_private', filename))


def get_ui_template_path(filename: str) -> str:
    """获取UI模板文件路径"""
    return get_resource_path(os.path.join('ui', 'templates', filename))


def get_ui_static_path(filename: str) -> str:
    """获取UI静态文件路径"""
    return get_resource_path(os.path.join('ui', 'static', filename))
