import logging
import os
import signal  # for keyboard events handling (press "Ctrl+C" to terminate recording)
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import pyaudio
import keyboard  # for global hotkey support

from dotenv import load_dotenv
from osc_manager import osc_manager
from translators.context_aware_translator import ContextAwareTranslator
from hot_words_manager import HotWordsManager

from translators.translation_apis.google_dictionary_api import GoogleDictionaryAPI as BackwardsTranslationAPI
from speech_recognizers.base_speech_recognizer import (
    RecognitionEvent,
    SpeechRecognitionCallback,
    SpeechRecognizer,
)
from speech_recognizers.recognizer_factory import (
    init_dashscope_api_key,
    create_recognizer,
    select_backend,
)

# 加载 .env 文件中的环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# ============ 配置常量 ============

# 语音识别后端配置
VALID_ASR_BACKENDS = {'dashscope', 'qwen'}
ASR_BACKEND = os.environ.get('ASR_BACKEND', 'qwen').strip().lower()
if ASR_BACKEND not in VALID_ASR_BACKENDS:
    ASR_BACKEND = 'dashscope'

# 音频参数配置
SAMPLE_RATE = 16000  # 采样率 (Hz)
CHANNELS = 1  # 单声道
DTYPE = 'int16'  # 数据类型
BITS = 16  # 每个采样的位数
FORMAT_PCM = 'pcm'  # 音频数据格式
BLOCK_SIZE = 1600  # 每个缓冲区的帧数

# 翻译语言配置
SOURCE_LANGUAGE = 'auto'  # 翻译源语言（'auto' 为自动检测，或指定如 'en', 'ja' 等）
TARGET_LANGUAGE = 'en'  # 翻译目标语言（'zh-CN'=简体中文, 'en'=英文, 'ja'=日文 等）
FALLBACK_LANGUAGE = 'zh'  # 备用翻译语言（当源语言和目标语言相同时使用）
                             # 设置为 None（非字符串）则禁用备用语言功能

# 语言识别配置
# from language_detectors.fasttext_detector import FasttextDetector as LanguageDetector  # FastText 通用语言检测器
from language_detectors.cjke_detector import CJKEDetector as LanguageDetector  # 专用中日韩英语言检测器
# from language_detectors.enzh_detector import EnZhDetector as LanguageDetector  # 专用中英语言检测器

# 翻译API配置
# from translators.translation_apis.google_web_api import GoogleWebAPI as TranslationAPI  # 标准的 Google Translate API，开箱即用，如果下面这个能用，就不推荐用这个
# from translators.translation_apis.google_dictionary_api import GoogleDictionaryAPI as TranslationAPI  # 更快的 Google Translate API，开箱即用
from translators.translation_apis.deepl_api import DeepLAPI as TranslationAPI  # DeepL API，需配置 DEEPL_API_KEY 环境变量
# from translators.translation_apis.openrouter_api import OpenRouterAPI as TranslationAPI  # OpenRouter API，需配置 OPENROUTER_API_KEY 环境变量

# 翻译上下文
CONTEXT_PREFIX = "This is an audio transcription of a conversation within the online multiplayer social game VRChat:"  # 上下文前缀文本

# 麦克风控制配置
ENABLE_MIC_CONTROL = True  # 是否考虑游戏内麦克风的开关情况
                           # True: 根据 VRChat 麦克风状态控制识别的启动/停止
                           # False: 程序启动时立即开始识别,忽略麦克风开关消息

MUTE_DELAY_SECONDS = 0.2  # 收到静音消息后延迟停止识别的秒数
                          # 设置为 0 则立即停止

# 热词配置
ENABLE_HOT_WORDS = True  # 是否启用热词功能

# VAD配置（仅Qwen后端）
ENABLE_VAD = True  # 是否启用服务器端VAD（语音活动检测）
                   # True: 启用VAD，服务器自动检测语音结束并断句
                   # False: 禁用VAD，需要手动调用commit()来触发断句
                   # 注意：VAD和手动commit不能同时使用
                   # - 启用VAD时，pause()会发送静音音频触发断句，而不是调用commit()
                   # - 禁用VAD时，pause()会调用commit()手动断句
VAD_THRESHOLD = 0.2  # VAD阈值（0.0-1.0），值越小越敏感
VAD_SILENCE_DURATION_MS = 800  # VAD静音持续时间（毫秒），检测到此时长的静音后触发断句

# 显示配置
SHOW_PARTIAL_RESULTS = False  # 是否显示识别中的部分结果（ongoing）
                             # True: 显示部分识别结果到聊天框（可能覆盖掉之前的翻译结果）
                             # False: 只显示完整识别结果

# 快捷键配置
ENABLE_HOTKEYS = True  # 是否启用全局快捷键
                      # True: 启用快捷键功能（需要管理员权限）
                      # False: 禁用快捷键功能

HOTKEY_TOGGLE_RECOGNITION = 'ctrl+shift+t'  # 快速开关翻译器的快捷键
                                            # 默认: Ctrl+Shift+T

HOTKEY_SWITCH_LANGUAGE = 'ctrl+shift+l'  # 切换目标语言的快捷键
                                         # 默认: Ctrl+Shift+L

# 可切换的目标语言列表（按顺序循环切换）
LANGUAGE_CYCLE = ['en', 'zh-CN', 'ja', 'ko']  # 英语、简体中文、日语、韩语
                                               # 可根据需要修改顺序和语言
                             
# ================================

# ============ 全局变量 ============
mic = None
stream = None
executor = ThreadPoolExecutor(max_workers=8)
stop_event = asyncio.Event()
recognition_active = False  # 标记识别是否正在运行
recognition_started = False  # 标记是否已建立识别会话
recognition_instance: Optional[SpeechRecognizer] = None  # 全局识别实例
mute_delay_task = None  # 延迟停止任务
CURRENT_ASR_BACKEND = ASR_BACKEND
vocabulary_id = None  # 热词表 ID

# 初始化当前语言索引（基于 TARGET_LANGUAGE）
current_language_index = 0
if TARGET_LANGUAGE in LANGUAGE_CYCLE:
    current_language_index = LANGUAGE_CYCLE.index(TARGET_LANGUAGE)

hotkey_toggle_enabled = False  # 标记快捷键切换是否已启用

# ============ 初始化服务实例 ============
translation_api = TranslationAPI()
translator = ContextAwareTranslator(
    translation_api=translation_api, 
    max_context_size=6,
    target_language=TARGET_LANGUAGE,
    context_aware=True
)

backwards_translation_api = BackwardsTranslationAPI()
backwards_translator = ContextAwareTranslator(
    translation_api=backwards_translation_api, 
    max_context_size=6,
    target_language="en",
    context_aware=True
)

language_detector = LanguageDetector()
# ================================


def validate_translation(translated_text, source_language, target_language):
    """
    对翻译结果进行反向翻译，从目标语言翻译回原始语言
    
    Args:
        translated_text: 已翻译的文本
        source_language: **本方法进行的翻译的** 源语言代码
        target_language: **本方法进行的翻译的** 目标语言代码
    
    Returns:
        反向翻译后的文本
    """
    try:
        backwards_translated = backwards_translator.translate(
            translated_text,
            source_language=source_language,
            target_language=target_language
        )
        print(f'反向翻译：{backwards_translated}')
        return backwards_translated
    except Exception as e:
        print(f'反向翻译失败: {e}')
        return None


# Real-time speech recognition callback
class VRChatRecognitionCallback(SpeechRecognitionCallback):
    def __init__(self):
        self.loop = None  # 将在主线程中设置
    
    def on_session_started(self) -> None:
        logger.info('Speech recognizer session opened.')

    def on_session_stopped(self) -> None:
        logger.info('Speech recognizer session closed.')

    def on_error(self, error: Exception) -> None:
        logger.error('Speech recognizer failed: %s', error)

    def on_result(self, event: RecognitionEvent) -> None:
        text = event.text
        if not text:
            return

        is_translated = False
        display_text = None
        is_ongoing = not event.is_final

        if is_ongoing:
            print(f'部分：{text}', end='\r')
            display_text = text
        else:
            source_lang_info = language_detector.detect(text)
            source_lang = source_lang_info['language']

            def normalize_lang(lang):
                """标准化语言代码"""
                lang_lower = lang.lower()
                if lang_lower in ['zh', 'zh-cn', 'zh-tw', 'zh-hans', 'zh-hant']:
                    return 'zh'
                if lang_lower in ['en', 'en-us', 'en-gb']:
                    return 'en'
                return lang_lower

            normalized_source = normalize_lang(source_lang)
            normalized_target = normalize_lang(TARGET_LANGUAGE)

            if FALLBACK_LANGUAGE and normalized_source == normalized_target:
                actual_target = FALLBACK_LANGUAGE
                print(f'原文：{text} [{source_lang_info["language"]}]')
                print(f'检测到源语言与目标语言相同，使用备用语言: {FALLBACK_LANGUAGE}')
            else:
                actual_target = TARGET_LANGUAGE
                print(f'原文：{text} [{source_lang_info["language"]}]')

            translated_text = translator.translate(
                text,
                source_language=SOURCE_LANGUAGE,
                target_language=actual_target,
                context_prefix=CONTEXT_PREFIX,
            )
            is_translated = True
            print(f'译文：{translated_text}')

            display_text = f"[{normalized_source}→{actual_target}] {translated_text}"

        if display_text is None:
            return

        should_send = (not is_ongoing) or SHOW_PARTIAL_RESULTS

        if self.loop:
            if should_send:
                asyncio.run_coroutine_threadsafe(
                    osc_manager.send_text(display_text, ongoing=is_ongoing),
                    self.loop
                )
            elif is_ongoing:
                asyncio.run_coroutine_threadsafe(
                    osc_manager.set_typing(is_ongoing),
                    self.loop
                )
        else:
            print('[OSC] Warning: Event loop not set, cannot send OSC message.')

        if is_translated:
            validate_translation(translated_text, actual_target, normalized_source)


async def init_audio_stream():
    """异步初始化音频流"""
    global mic, stream
    loop = asyncio.get_event_loop()
    
    def _init():
        global mic, stream
        mic = pyaudio.PyAudio()
        stream = mic.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=BLOCK_SIZE
        )
        return stream
    
    return await loop.run_in_executor(executor, _init)


async def close_audio_stream():
    """异步关闭音频流"""
    global mic, stream
    loop = asyncio.get_event_loop()
    
    def _close():
        global mic, stream
        if stream:
            stream.stop_stream()
            stream.close()
        if mic:
            mic.terminate()
        stream = None
        mic = None
    
    await loop.run_in_executor(executor, _close)


async def read_audio_data():
    """异步读取音频数据"""
    global stream
    if not stream:
        return None
    
    loop = asyncio.get_event_loop()
    
    def _read():
        try:
            return stream.read(BLOCK_SIZE, exception_on_overflow=False)
        except Exception as e:
            print(f'Error reading audio data: {e}')
            return None
    
    return await loop.run_in_executor(executor, _read)


async def send_audio_frame_async(recognizer: SpeechRecognizer, data: bytes):
    """异步发送音频帧"""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(executor, recognizer.send_audio_frame, data)
    except Exception as e:
        pass
    

async def audio_capture_task(recognizer: SpeechRecognizer):
    """异步音频捕获任务"""
    global recognition_active
    print('Starting audio capture...')
    try:
        while not stop_event.is_set():
            # 始终读取音频数据,避免缓冲区积压
            data = await read_audio_data()
            if not data:
                break
            
            # 只有在识别激活时才发送音频数据,否则丢弃
            if recognition_active:
                await send_audio_frame_async(recognizer, data)
            # 静音时数据被读取但不发送,自动丢弃
            
            await asyncio.sleep(0.001)  # 避免阻塞事件循环
    except asyncio.CancelledError:
        print('Audio capture task cancelled.')
    except Exception as e:
        print(f'Audio capture error: {e}')
    finally:
        print('Audio capture stopped.')


def signal_handler(sig, frame):
    print('Ctrl+C pressed, stop recognition ...')
    # 在异步环境中安全地设置停止事件
    try:
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(stop_event.set)
    except:
        stop_event.set()


async def stop_recognition_async(recognizer: SpeechRecognizer):
    """异步暂停或停止识别服务"""
    global recognition_active, recognition_started
    if not recognition_active:
        return  # 已经暂停

    loop = asyncio.get_event_loop()

    recognition_active = False

    if CURRENT_ASR_BACKEND == 'dashscope':
        # 发送静音音频帧，确保本次识别至少发送了一个音频帧，否则会报错
        silence_frames = BLOCK_SIZE
        silence_data = b'\x00' * (BITS // 8 * silence_frames)
        await send_audio_frame_async(recognizer, silence_data)
        await asyncio.sleep(0.1)
        try:
            await loop.run_in_executor(executor, recognizer.stop)
        except Exception:
            pass
        recognition_started = False
    else:
        try:
            await loop.run_in_executor(executor, recognizer.pause)
        except Exception:
            pass


async def start_recognition_async(recognizer: SpeechRecognizer):
    """异步开始或恢复识别服务"""
    global recognition_active, recognition_started
    if recognition_active:
        print('Recognition already active.')
        return  # 已经在运行中

    loop = asyncio.get_event_loop()

    try:
        if CURRENT_ASR_BACKEND == 'qwen' and recognition_started:
            await loop.run_in_executor(executor, recognizer.resume)
        else:
            await loop.run_in_executor(executor, recognizer.start)
            recognition_started = True
    except Exception:
        pass

    recognition_active = True


async def handle_mute_change(is_muted):
    """
    处理静音状态变化的回调函数
    
    Args:
        is_muted: True表示静音(停止识别), False表示取消静音(开始识别)
    """
    global recognition_active, recognition_instance, mute_delay_task, recognition_started
    
    # 如果禁用了麦克风控制，则忽略所有麦克风状态变化
    if not ENABLE_MIC_CONTROL:
        return
    
    if recognition_instance is None:
        print('[ASR] 识别实例未初始化')
        return
    
    stop_word = '暂停' if CURRENT_ASR_BACKEND == 'qwen' else '停止'
    start_word = '恢复' if CURRENT_ASR_BACKEND == 'qwen' and recognition_started else '开始'

    if is_muted:
        # 静音状态 - 延迟停止识别
        if recognition_active:
            # 如果已有延迟任务在运行，先取消它
            if mute_delay_task and not mute_delay_task.done():
                mute_delay_task.cancel()
            
            if MUTE_DELAY_SECONDS > 0:
                print(f'[ASR] 检测到静音，将在 {MUTE_DELAY_SECONDS} 秒后{stop_word}语音识别...')
                
                async def delayed_stop():
                    global recognition_active
                    try:
                        await asyncio.sleep(MUTE_DELAY_SECONDS)
                        if recognition_active:  # 再次检查，确保期间没有取消静音
                            print(f'[ASR] 延迟时间到，{stop_word}语音识别')
                            await stop_recognition_async(recognition_instance)
                            logger.info(f'[ASR] 语音识别已{stop_word}')
                    except asyncio.CancelledError:
                        print('[ASR] 停止识别已取消（取消静音）')
                
                mute_delay_task = asyncio.create_task(delayed_stop())
            else:
                # 延迟为0，立即停止
                print(f'[ASR] 检测到静音，立即{stop_word}语音识别...')
                await stop_recognition_async(recognition_instance)
                logger.info(f'[ASR] 语音识别已{stop_word}')
    else:
        # 取消静音 - 开始识别
        # 如果有延迟停止任务，取消它
        if mute_delay_task and not mute_delay_task.done():
            mute_delay_task.cancel()
            print('[ASR] 检测到取消静音，已取消延迟停止任务')
        
        if not recognition_active:
            print(f'[ASR] 检测到取消静音，{start_word}语音识别...')
            await start_recognition_async(recognition_instance)
            logger.info(f'[ASR] 语音识别已{start_word}')


def on_toggle_recognition_hotkey():
    """
    快捷键处理：切换识别开关
    """
    global recognition_instance, recognition_active, hotkey_toggle_enabled
    
    if recognition_instance is None:
        print('[Hotkey] 识别实例未初始化，无法切换')
        return
    
    # 创建异步任务切换识别状态
    loop = asyncio.get_event_loop()
    
    if recognition_active and not hotkey_toggle_enabled:
        # 当前识别开启，切换为关闭
        print('[Hotkey] 快捷键：关闭翻译器')
        hotkey_toggle_enabled = True
        asyncio.run_coroutine_threadsafe(stop_recognition_async(recognition_instance), loop)
    elif not recognition_active and hotkey_toggle_enabled:
        # 当前识别关闭，切换为开启
        print('[Hotkey] 快捷键：开启翻译器')
        hotkey_toggle_enabled = False
        asyncio.run_coroutine_threadsafe(start_recognition_async(recognition_instance), loop)
    elif not recognition_active and not hotkey_toggle_enabled:
        # 由麦克风控制关闭的状态，不允许通过快捷键开启
        print('[Hotkey] 快捷键：开启翻译器（已禁用麦克风控制）')
        hotkey_toggle_enabled = True
        asyncio.run_coroutine_threadsafe(start_recognition_async(recognition_instance), loop)
    else:
        # 由麦克风控制开启的状态，可以通过快捷键关闭
        print('[Hotkey] 快捷键：关闭翻译器')
        hotkey_toggle_enabled = True
        asyncio.run_coroutine_threadsafe(stop_recognition_async(recognition_instance), loop)


def on_switch_language_hotkey():
    """
    快捷键处理：切换目标语言
    """
    global current_language_index, translator
    
    # 切换到下一个语言
    current_language_index = (current_language_index + 1) % len(LANGUAGE_CYCLE)
    new_language = LANGUAGE_CYCLE[current_language_index]
    
    # 更新translator的目标语言
    translator.target_language = new_language
    
    # 显示语言切换信息
    language_names = {
        'en': '英语',
        'zh-CN': '简体中文',
        'zh': '简体中文',
        'ja': '日语',
        'ko': '韩语',
        'es': '西班牙语',
        'fr': '法语',
        'de': '德语',
        'ru': '俄语',
    }
    language_display = language_names.get(new_language, new_language)
    print(f'[Hotkey] 目标语言已切换为: {language_display} ({new_language})')
    
    # 通过OSC发送通知到VRChat聊天框
    loop = asyncio.get_event_loop()
    asyncio.run_coroutine_threadsafe(
        osc_manager.send_text(f'[系统] 目标语言: {language_display}', ongoing=False),
        loop
    )


def setup_hotkeys():
    """
    设置全局热键
    """
    if not ENABLE_HOTKEYS:
        return
    
    try:
        # 注册切换识别的快捷键
        keyboard.add_hotkey(HOTKEY_TOGGLE_RECOGNITION, on_toggle_recognition_hotkey)
        print(f'[Hotkey] 已注册快捷键 {HOTKEY_TOGGLE_RECOGNITION} 用于切换翻译器开关')
        
        # 注册切换语言的快捷键
        keyboard.add_hotkey(HOTKEY_SWITCH_LANGUAGE, on_switch_language_hotkey)
        print(f'[Hotkey] 已注册快捷键 {HOTKEY_SWITCH_LANGUAGE} 用于切换目标语言')
        
        print('[Hotkey] 快捷键功能已启用')
    except Exception as e:
        print(f'[Hotkey] 快捷键注册失败: {e}')
        print('[Hotkey] 将继续运行但不使用快捷键功能')


def cleanup_hotkeys():
    """
    清理全局热键
    """
    if not ENABLE_HOTKEYS:
        return
    
    try:
        keyboard.unhook_all_hotkeys()
        print('[Hotkey] 快捷键已清理')
    except Exception as e:
        print(f'[Hotkey] 清理快捷键时出错: {e}')


async def main():
    """主异步函数"""
    global recognition_instance, recognition_active, vocabulary_id, CURRENT_ASR_BACKEND, recognition_started
    vocabulary_id = None
    corpus_text: Optional[str] = None

    # 初始化 DashScope API Key
    init_dashscope_api_key()
    print('Initializing ...')

    # 选择可用的识别后端
    backend = select_backend(ASR_BACKEND, VALID_ASR_BACKENDS)
    if backend != ASR_BACKEND:
        print(f'[ASR] 已切换语音识别后端为 {backend}')
    else:
        print(f'[ASR] 目标识别后端: {backend}')

    CURRENT_ASR_BACKEND = backend
    recognition_active = False
    recognition_started = False

    # 初始化热词（如果启用）
    if ENABLE_HOT_WORDS:
        print('\n[热词] 初始化热词资源...')
        try:
            hot_words_manager = HotWordsManager()
            hot_words_manager.load_all_hot_words()
            if backend == 'qwen':
                words = [entry.get('text') for entry in hot_words_manager.get_hot_words() if entry.get('text')]
                if words:
                    corpus_text = "\n".join(words)
                    print(f'[热词] 已生成 Qwen 语料文本，共 {len(words)} 条\n')
                else:
                    print('[热词] 未加载到热词条目，跳过 Qwen 语料配置\n')
            else:
                vocabulary_id = hot_words_manager.create_vocabulary(target_model='fun-asr-realtime')
                print(f'[热词] 热词表创建成功，ID: {vocabulary_id}\n')
        except Exception as e:
            print(f'[热词] 热词初始化失败: {e}')
            print('[热词] 将继续运行但不使用热词\n')
            vocabulary_id = None
            corpus_text = None

    # 启动OSC服务器
    print('[OSC] 启动OSC服务器...')
    await osc_manager.start_server()
    
    # 设置静音状态回调
    osc_manager.set_mute_callback(handle_mute_change)
    print('[OSC] 已设置静音状态回调')

    # 创建识别回调
    callback = VRChatRecognitionCallback()
    callback.loop = asyncio.get_event_loop()

    # 使用工厂创建识别实例
    recognition_instance = create_recognizer(
        backend=backend,
        callback=callback,
        sample_rate=SAMPLE_RATE,
        audio_format=FORMAT_PCM,
        source_language=SOURCE_LANGUAGE,
        vocabulary_id=vocabulary_id,
        corpus_text=corpus_text,
        enable_vad=ENABLE_VAD,
        vad_threshold=VAD_THRESHOLD,
        vad_silence_duration_ms=VAD_SILENCE_DURATION_MS,
    )
    
    if vocabulary_id and backend == 'dashscope':
        print(f'[ASR] 使用热词表: {vocabulary_id}')
    
    if backend == 'qwen':
        vad_status = '启用' if ENABLE_VAD else '禁用'
        print(f'[ASR] VAD状态: {vad_status}')
        if ENABLE_VAD:
            print(f'[ASR] VAD配置: 阈值={VAD_THRESHOLD}, 静音时长={VAD_SILENCE_DURATION_MS}ms')
    
    print('[ASR] 识别实例已创建')
    
    # 初始化音频流
    await init_audio_stream()
    
    # 设置全局快捷键
    setup_hotkeys()

    signal.signal(signal.SIGINT, signal_handler)
    
    # 根据配置决定是否立即启动识别
    if ENABLE_MIC_CONTROL:
        stop_hint = '暂停' if backend == 'qwen' else '停止'
        resume_hint = '恢复' if backend == 'qwen' else '开始'
        print("=" * 60)
        print("[模式] 麦克风控制模式已启用")
        print("等待VRChat静音状态变化...")
        print(f"取消静音(MuteSelf=False)将{resume_hint}语音识别")
        print(f"启用静音(MuteSelf=True)将{stop_hint}语音识别")
        if ENABLE_HOTKEYS:
            print(f"快捷键 '{HOTKEY_TOGGLE_RECOGNITION}' 可切换翻译器开关")
            print(f"快捷键 '{HOTKEY_SWITCH_LANGUAGE}' 可切换目标语言")
        print("按 'Ctrl+C' 退出程序")
        print("=" * 60)
    else:
        print("=" * 60)
        print("[模式] 麦克风控制模式已禁用")
        print("语音识别将立即启动，忽略麦克风开关状态")
        if ENABLE_HOTKEYS:
            print(f"快捷键 '{HOTKEY_TOGGLE_RECOGNITION}' 可切换翻译器开关")
            print(f"快捷键 '{HOTKEY_SWITCH_LANGUAGE}' 可切换目标语言")
        print("按 'Ctrl+C' 退出程序")
        print("=" * 60)
        # 立即启动识别
        await start_recognition_async(recognition_instance)
        print('[ASR] 语音识别已启动')

    # 创建音频捕获任务
    capture_task = asyncio.create_task(audio_capture_task(recognition_instance))
    
    try:
        # 等待停止事件
        await stop_event.wait()
        
        # 取消捕获任务
        capture_task.cancel()
        
        # 等待捕获任务完成(带超时)
        try:
            await asyncio.wait_for(capture_task, timeout=2.0)
        except asyncio.TimeoutError:
            print('Audio capture task timeout, forcing stop.')
        except asyncio.CancelledError:
            pass
        
        # 如果识别正在运行,停止它
        if recognition_active:
            await stop_recognition_async(recognition_instance)
            halt_word = 'paused' if CURRENT_ASR_BACKEND == 'qwen' else 'stopped'
            print(f'Recognition {halt_word}.')
        
        # 获取统计信息(使用异步方式)
        if recognition_instance:
            loop = asyncio.get_event_loop()
            try:
                request_id = await loop.run_in_executor(executor, recognition_instance.get_last_request_id)
                first_delay = await loop.run_in_executor(executor, recognition_instance.get_first_package_delay)
                last_delay = await loop.run_in_executor(executor, recognition_instance.get_last_package_delay)
                
                print(
                    '[Metric] requestId: {}, first package delay ms: {}, last package delay ms: {}'
                    .format(request_id, first_delay, last_delay))
            except Exception as e:
                print(f'[Metric] 获取统计信息失败: {e}')
    
    finally:
        # 清理快捷键
        cleanup_hotkeys()
        
        # 清除OSC回调
        osc_manager.clear_mute_callback()

        loop = asyncio.get_event_loop()

        if recognition_instance:
            try:
                await loop.run_in_executor(executor, recognition_instance.stop)
            except Exception:
                pass
            recognition_started = False
            recognition_active = False
        
        # 关闭音频流
        await close_audio_stream()
        
        # 停止OSC服务器
        await osc_manager.stop_server()
        
        # 异步关闭线程池
        await loop.run_in_executor(None, executor.shutdown, False)


# main function
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nProgram terminated by user.')
    except Exception as e:
        print(f'Error: {e}')
    finally:
        print('Cleanup completed.')