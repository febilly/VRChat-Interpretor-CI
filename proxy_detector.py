"""
系统代理检测工具
自动检测并应用系统网络代理设置
"""
import os
import urllib.request


def detect_system_proxy():
    """
    检测系统代理设置
    
    Returns:
        dict: 包含代理信息的字典，如果没有代理则返回 None
              格式: {'http': 'http://proxy:port', 'https': 'https://proxy:port'}
    """
    proxies = {}
    
    # 检查环境变量中的代理设置
    http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    
    if http_proxy:
        proxies['http'] = http_proxy
    if https_proxy:
        proxies['https'] = https_proxy
    
    # 如果环境变量中没有设置，尝试使用 urllib 的系统代理检测
    if not proxies:
        try:
            proxy_handler = urllib.request.ProxyHandler()
            if proxy_handler.proxies:
                proxies = proxy_handler.proxies
        except Exception:
            pass
    
    return proxies if proxies else None


def print_proxy_info(proxies):
    """
    在命令行输出代理信息
    
    Args:
        proxies: 代理信息字典
    """
    if not proxies:
        return
    
    print('[代理] 检测到系统网络代理设置，正在使用：')
    for protocol, proxy_url in proxies.items():
        print(f'  {protocol.upper()}: {proxy_url}')
