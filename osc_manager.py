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

# 句子结束标记（按优先级排序）
SENTENCE_ENDERS = [
    '.', '。', '！', '!', '？', '?',  # 强句子结束符
    '…', '...', '‽',                  # 省略号和特殊符号
    '，', ',', '；', ';',             # 逗号和分号
    '։', '؟', '،',                    # 其他语言的标点
    '।', '॥', '።', '။', '།',        # 印度语系、埃塞俄比亚语、缅甸语、藏语
    '、', '‚', '٫'                   # 日语顿号、低逗号等
]

# 文本分割配置
MIN_SPLIT_RATIO = 0.5  # 在空格处分割时，至少保留的内容比例

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
            
            # 分页配置
            self._enable_pagination = False  # 是否启用分页功能
            self._page_interval = 3.0  # 分页间隔时间（秒）
            self._pagination_task = None  # 当前正在运行的分页任务
            self._pagination_lock = asyncio.Lock()  # 分页任务的锁，确保串行化
            
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
    
    def configure_pagination(self, enable: bool = True, page_interval: float = 3.0):
        """
        配置分页功能
        
        Args:
            enable: 是否启用分页功能
            page_interval: 分页间隔时间（秒）
        """
        self._enable_pagination = enable
        self._page_interval = page_interval
        logger.info(f"[OSC] 分页配置: 启用={enable}, 间隔={page_interval}秒")
    
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
        
        transport, protocol = await self._server.create_serve_endpoint()
        logger.info(f"[OSC] OSC服务器已启动，监听地址: {self._osc_server_host}:{self._osc_server_port}")
        return transport
    
    async def stop_server(self):
        """停止OSC服务器"""
        if self._server is not None:
            # 注意：AsyncIOOSCUDPServer 没有直接的关闭方法
            # 可以通过关闭transport来停止
            logger.info("[OSC] OSC服务器停止（如需要可实现）")
            self._server = None
        
        # 取消正在运行的分页任务
        if self._pagination_task and not self._pagination_task.done():
            self._pagination_task.cancel()
            try:
                await self._pagination_task
            except asyncio.CancelledError:
                pass
    
    def _split_text_into_pages(self, text: str, max_length: int = 144) -> list:
        """
        将长文本智能分割成多个页面，每页不超过最大长度
        优先在句子边界处分割，保持语义完整性
        
        Args:
            text: 需要分割的文本
            max_length: 每页的最大长度限制
            
        Returns:
            分割后的文本页面列表
        """
        if len(text) <= max_length:
            return [text]
        
        pages = []
        remaining_text = text
        
        while remaining_text:
            if len(remaining_text) <= max_length:
                # 剩余文本可以放入一页
                pages.append(remaining_text)
                break
            
            # 寻找最佳分割点（在 max_length 范围内的最后一个句子结束符）
            best_split_pos = -1
            best_ender = None
            
            # 在前 max_length 字符内查找句子结束符
            search_text = remaining_text[:max_length]
            
            for ender in SENTENCE_ENDERS:
                # 从后向前查找，优先使用靠后的分割点
                pos = search_text.rfind(ender)
                if pos != -1 and pos > best_split_pos:
                    best_split_pos = pos
                    best_ender = ender
            
            if best_split_pos != -1:
                # 在句子边界处分割
                # 包含结束符在当前页中
                current_page = remaining_text[:best_split_pos + 1].strip()
                pages.append(current_page)
                # 移除已处理的部分
                remaining_text = remaining_text[best_split_pos + 1:].lstrip()
            else:
                # 没有找到合适的分割点，强制在 max_length 处分割
                # 尝试在空格处分割以避免切断单词
                search_text = remaining_text[:max_length]
                last_space = search_text.rfind(' ')
                
                if last_space > max_length * MIN_SPLIT_RATIO:  # 至少保留一半以上内容
                    split_pos = last_space
                else:
                    split_pos = max_length
                
                current_page = remaining_text[:split_pos].strip()
                pages.append(current_page)
                remaining_text = remaining_text[split_pos:].lstrip()
        
        return pages
    
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
        支持分页功能，自动处理超长文本
        
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
        
        # 检查是否需要分页
        if self._enable_pagination and len(text) > MAX_LENGTH and not ongoing:
            # 使用锁确保分页任务串行化
            async with self._pagination_lock:
                # 取消之前的分页任务（如果存在）
                if self._pagination_task and not self._pagination_task.done():
                    self._pagination_task.cancel()
                    try:
                        await self._pagination_task
                    except asyncio.CancelledError:
                        pass
                
                # 创建新的分页任务
                self._pagination_task = asyncio.create_task(self._send_paginated_text(text))
        else:
            # 不使用分页，使用原来的截断逻辑
            text = self._truncate_text(text, max_length=MAX_LENGTH)
            await self._send_single_message(text, ongoing)
    
    async def _send_single_message(self, text: str, ongoing: bool):
        """
        发送单条消息到VRChat聊天框
        
        Args:
            text: 要发送的文本（已经过处理）
            ongoing: 是否正在输入中
        """
        try:
            client = self.get_udp_client()
            client.send_message("/chatbox/typing", ongoing)
            client.send_message("/chatbox/input", [text, True, not ongoing])
        except Exception as e:
            logger.error(f"[OSC] 发送OSC消息失败: {e}")
        finally:
            logger.info(f"[OSC] 发送聊天框消息: '{text}' (ongoing={ongoing})")
    
    async def _send_paginated_text(self, text: str):
        """
        分页发送长文本
        
        Args:
            text: 要发送的完整文本
        """
        pages = self._split_text_into_pages(text, max_length=MAX_LENGTH)
        total_pages = len(pages)
        
        logger.info(f"[OSC] 文本过长，分为 {total_pages} 页发送")
        
        for i, page in enumerate(pages):
            page_num = i + 1
            # 计算页码标记
            marker = f"[{page_num}/{total_pages}] "
            page_with_marker = marker + page
            
            # 如果添加页码后超长，则截断内容
            if len(page_with_marker) > MAX_LENGTH:
                available_length = MAX_LENGTH - len(marker)
                page_with_marker = marker + page[:available_length]
            
            # 发送当前页
            await self._send_single_message(page_with_marker, ongoing=False)
            
            # 如果不是最后一页，等待一段时间再发送下一页
            if i < total_pages - 1:
                logger.info(f"[OSC] 等待 {self._page_interval} 秒后发送下一页...")
                await asyncio.sleep(self._page_interval)


# 创建全局单例实例
osc_manager = OSCManager()
