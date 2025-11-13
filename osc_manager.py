"""
OSC (Open Sound Control) 管理模块
负责处理VRChat的OSC通信，包括接收静音消息和发送聊天框消息
"""
import asyncio
import logging
import time
from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

logger = logging.getLogger(__name__)

# 定义发送到VRChat聊天框的最大文本长度
MAX_LENGTH=144

class OSCManager:
    """OSC管理器单例类，负责OSC服务器和客户端的管理"""
    
    _instance = None
    _server = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OSCManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._server = None
            self._transport = None  # 保存transport用于关闭
            self._client = None
            self._mute_callback = None  # 静音状态变化的回调函数
            
            # OSC客户端配置（发送到VRChat）
            self._osc_client_host = "127.0.0.1"
            self._osc_client_port = 9000
            
            # OSC服务器配置（接收来自VRChat）
            self._osc_server_host = "127.0.0.1"
            self._osc_server_port = 9001
            
            # 速率限制配置（令牌桶算法）
            self._rate_limit_interval = 2  # 每条消息间隔
            self._rate_limit_burst = 2  # 爆发容量
            self._tokens = self._rate_limit_burst  # 当前令牌数
            self._last_refill_time = time.time()  # 上次补充令牌的时间
            
            logger.info("[OSC] OSC管理器已初始化")
    
    def set_mute_callback(self, callback):
        """
        设置静音状态变化的回调函数
        
        Args:
            callback: 回调函数，接收一个布尔参数 (mute_value)
                     当收到 MuteSelf=True 时调用 callback(True)
                     当收到 MuteSelf=False 时调用 callback(False)
        """
        self._mute_callback = callback
        logger.info("[OSC] 已设置静音状态回调函数")
    
    def clear_mute_callback(self):
        """清除静音状态回调函数"""
        self._mute_callback = None
        logger.info("[OSC] 已清除静音状态回调函数")
    
    def get_udp_client(self):
        """获取OSC UDP客户端实例（用于发送消息）"""
        if self._client is None:
            self._client = udp_client.SimpleUDPClient(
                self._osc_client_host,
                self._osc_client_port
            )
            logger.info(f"[OSC] OSC客户端已创建，目标地址: {self._osc_client_host}:{self._osc_client_port}")
        return self._client
    
    def _handle_mute_self(self, address, *args):
        """处理来自OSC的MuteSelf消息"""
        if args and len(args) > 0:
            mute_value = args[0]
            logger.info(f"[OSC] 收到MuteSelf消息: {mute_value}")
            
            # 如果设置了回调函数，则调用它
            if self._mute_callback is not None:
                try:
                    # 如果回调是协程函数，需要创建任务
                    if asyncio.iscoroutinefunction(self._mute_callback):
                        asyncio.create_task(self._mute_callback(mute_value))
                    else:
                        self._mute_callback(mute_value)
                except Exception as e:
                    logger.error(f"[OSC] 调用静音回调函数时出错: {e}")
            else:
                logger.debug(f"[OSC] 未设置静音回调函数，忽略MuteSelf消息")
    
    async def start_server(self):
        """启动OSC服务器监听（全局单例）"""
        if self._server is not None:
            logger.info("[OSC] OSC服务器已在运行中")
            return
        
        dispatcher = Dispatcher()
        dispatcher.map("/avatar/parameters/MuteSelf", self._handle_mute_self)
        
        self._server = AsyncIOOSCUDPServer(
            (self._osc_server_host, self._osc_server_port),
            dispatcher,
            asyncio.get_event_loop()
        )
        
        self._transport, protocol = await self._server.create_serve_endpoint()
        logger.info(f"[OSC] OSC服务器已启动，监听地址: {self._osc_server_host}:{self._osc_server_port}")
        return self._transport
    
    async def stop_server(self):
        """停止OSC服务器"""
        if self._transport is not None:
            self._transport.close()
            logger.info("[OSC] OSC服务器transport已关闭")
            self._transport = None
        
        if self._server is not None:
            self._server = None
            logger.info("[OSC] OSC服务器已停止")
    
    def _truncate_text(self, text: str, max_length: int = 144) -> str:
        """
        截断过长的文本，优先删除前面的句子
        
        Args:
            text: 需要截断的文本
            max_length: 最大长度限制
            
        Returns:
            截断后的文本
        """
        if len(text) <= max_length:
            return text
        
        # 句子结束标记
        SENTENCE_ENDERS = [
            '.', '?', '!', ',',           # Common
            '。', '？', '！', '，',        # CJK
            '…', '...', '‽',             # Stylistic & Special (includes 3-dot ellipsis)
            '։', '؟', ';', '،',           # Armenian, Arabic, Greek (as question mark), Arabic comma
            '।', '॥', '።', '။', '།',    # Indic, Ethiopic, Myanmar, Tibetan
            '、', '‚', '٫'               # Japanese enumeration comma, low comma, Arabic decimal separator
        ]
        
        # 当文本超长时，删除最前面的句子而不是截断末尾
        while len(text) > max_length:
            # 尝试找到第一个句子的结束位置
            first_sentence_end = -1
            for ender in SENTENCE_ENDERS:
                idx = text.find(ender)
                if idx != -1 and (first_sentence_end == -1 or idx < first_sentence_end):
                    first_sentence_end = idx
            
            if first_sentence_end != -1:
                # 删除第一个句子（包括标点符号后的空格）
                text = text[first_sentence_end + 1:].lstrip()
            else:
                # 如果没有找到标点符号，删除前面的字符直到长度合适
                text = text[len(text) - max_length:]
                break
        
        return text
    
    def _refill_tokens(self):
        """
        补充令牌（令牌桶算法）
        根据经过的时间补充令牌，但不超过爆发容量
        """
        current_time = time.time()
        elapsed_time = current_time - self._last_refill_time
        
        # 计算应该补充的令牌数
        tokens_to_add = int(elapsed_time / self._rate_limit_interval)
        tokens_to_add = min(tokens_to_add, self._rate_limit_burst - self._tokens)
        
        if tokens_to_add >= 1:
            self._tokens = self._tokens + tokens_to_add
            self._last_refill_time += tokens_to_add * self._rate_limit_interval
        
        # 保证elapsed_time不会过大
        self._last_refill_time = max(self._last_refill_time, current_time - self._rate_limit_interval * (self._rate_limit_burst - self._tokens))
    
    def _can_send(self, force_send: bool) -> bool:
        """
        检查是否可以发送 ongoing 消息（速率限制）
        
        Returns:
            如果有可用令牌返回 True，否则返回 False
        """
        self._refill_tokens()
        
        if not force_send and self._tokens <= 0:
            return False
        
        self._tokens -= 1
        return True
    
    async def set_typing(self, typing: bool):
        """
        设置 VRChat 聊天框的 typing 状态
        
        Args:
            typing: True 表示正在输入，False 表示停止输入
        """
        try:
            client = self.get_udp_client()
            client.send_message("/chatbox/typing", typing)
            logger.debug(f"[OSC] 设置 typing 状态: {typing}")
        except Exception as e:
            logger.error(f"[OSC] 设置 typing 状态失败: {e}")
    
    async def send_text(self, text: str, ongoing: bool):
        """
        发送文本到VRChat聊天框
        
        Args:
            text: 要发送的文本
            ongoing: 是否正在输入中（ongoing 消息会受到速率限制）
        """
        # 对 ongoing 消息实施速率限制
        if ongoing:
            if not self._can_send(not ongoing):
                logger.debug(f"[OSC] ongoing 消息被速率限制阻止")
                return
            else:
                logger.debug(f"[OSC] 发送ongoing消息，当前令牌数: {self._tokens}")
        
        # 截断过长的文本
        text = self._truncate_text(text, max_length=MAX_LENGTH)
        
        try:
            client = self.get_udp_client()
            client.send_message("/chatbox/typing", ongoing)
            client.send_message("/chatbox/input", [text, True, not ongoing])
        except Exception as e:
            logger.error(f"[OSC] 发送OSC消息失败: {e}")
        finally:
            logger.info(f"[OSC] 发送聊天框消息: '{text}' (ongoing={ongoing})")


# 创建全局单例实例
osc_manager = OSCManager()
