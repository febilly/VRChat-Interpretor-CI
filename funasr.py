import logging
import os
import signal  # for keyboard events handling (press "Ctrl+C" to terminate recording)
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor

import dashscope
import pyaudio
from dashscope.audio.asr import *

from dotenv import load_dotenv
from osc_manager import osc_manager
from translators.context_aware_translator import ContextAwareTranslator
from hot_words_manager import HotWordsManager

from translators.translation_apis.google_dictionary_api import GoogleDictionaryAPI as BackwardsTranslationAPI


# 加载 .env 文件中的环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# ============ 配置常量 ============
# 翻译语言配置
SOURCE_LANGUAGE = 'auto'  # 翻译源语言（'auto' 为自动检测，或指定如 'en', 'ja' 等）
TARGET_LANGUAGE = 'ja'  # 翻译目标语言（'zh-CN'=简体中文, 'en'=英文, 'ja'=日文 等）
FALLBACK_LANGUAGE = 'zh'  # 备用翻译语言（当源语言和目标语言相同时使用）
                             # 设置为 None（非字符串）则禁用备用语言功能

# 语言识别配置
# from language_detectors.fasttext_detector import FasttextDetector as LanguageDetector  # FastText 通用语言检测器
from language_detectors.cjke_detector import CJKEDetector as LanguageDetector  # 专用中日韩英语言检测器
# from language_detectors.enzh_detector import EnZhDetector as LanguageDetector  # 专用中英语言检测器

# 翻译API配置
# from translators.translation_apis.google_web_api import GoogleWebAPI as TranslationAPI  # 标准的 Google Translate API，开箱即用
# from translators.translation_apis.google_dictionary_api import GoogleDictionaryAPI as TranslationAPI  # 更快的 Google Translate API，开箱即用
from translators.translation_apis.deepl_api import DeepLAPI as TranslationAPI  # DeepL API，需配置 DEEPL_API_KEY 环境变量

# 翻译上下文
CONTEXT_PREFIX = "This is an audio transcription of a conversation within the online multiplayer social game VRChat:"  # 上下文前缀文本

# 麦克风控制配置
ENABLE_MIC_CONTROL = True  # 是否考虑游戏内麦克风的开关情况
                           # True: 根据 VRChat 麦克风状态控制识别的启动/停止
                           # False: 程序启动时立即开始识别,忽略麦克风开关消息

MUTE_DELAY_SECONDS = 0.3  # 收到静音消息后延迟停止识别的秒数
                          # 设置为 0 则立即停止

# 热词配置
ENABLE_HOT_WORDS = True  # 是否启用热词功能

# 显示配置
SHOW_PARTIAL_RESULTS = False  # 是否显示识别中的部分结果（ongoing）
                             # True: 显示部分识别结果到聊天框（可能覆盖掉之前的翻译结果）
                             # False: 只显示完整识别结果
                             
# ================================

mic = None
stream = None
executor = ThreadPoolExecutor(max_workers=8)
stop_event = asyncio.Event()
recognition_active = False  # 标记识别是否正在运行
recognition_instance = None  # 全局识别实例
mute_delay_task = None  # 延迟停止任务

vocabulary_id = None  # 热词表 ID

translation_api = TranslationAPI()  # 翻译 API 实例
translator = ContextAwareTranslator(
    translation_api=translation_api, 
    max_context_size=6,
    target_language=TARGET_LANGUAGE,
    context_aware=True
)

backwards_translation_api = BackwardsTranslationAPI()  # 反向翻译 API 实例
backwards_translator = ContextAwareTranslator(
    translation_api=backwards_translation_api, 
    max_context_size=6,
    target_language="en",  # 实际进行翻译的时候不会使用这个值
    context_aware=True
)  # 反向翻译 API 实例

language_detector = LanguageDetector()  # 语言检测器实例

# Set recording parameters
sample_rate = 16000  # sampling rate (Hz)
channels = 1  # mono channel
dtype = 'int16'  # data type
bits = 16  # bits per sample
format_pcm = 'pcm'  # the format of the audio data
block_size = 1600  # number of frames per buffer


def init_dashscope_api_key():
    """
        Set your DashScope API-key. More information:
        https://github.com/aliyun/alibabacloud-bailian-speech-demo/blob/master/PREREQUISITES.md
    """

    if 'DASHSCOPE_API_KEY' in os.environ:
        dashscope.api_key = os.environ[
            'DASHSCOPE_API_KEY']  # load API-key from environment variable DASHSCOPE_API_KEY
    else:
        dashscope.api_key = '<your-dashscope-api-key>'  # set API-key manually


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
class Callback(RecognitionCallback):
    def __init__(self):
        super().__init__()
        self.loop = None  # 将在主线程中设置
    
    def on_open(self) -> None:
        logger.info('RecognitionCallback open.')

    def on_close(self) -> None:
        logger.info('RecognitionCallback close.')

    def on_complete(self) -> None:
        logger.info('RecognitionCallback completed.')  # recognition completed

    def on_error(self, message) -> None:
        logger.error('RecognitionCallback task_id: %s', message.request_id)
        logger.error('RecognitionCallback error: %s', message.message)
        # if self.loop:
        #     self.loop.call_soon_threadsafe(stop_event.set)
        # else:
        #     stop_event.set()

    def on_event(self, result: RecognitionResult) -> None:
        sentence = result.get_sentence()
        
        is_translated = False
        
        if sentence and 'text' in sentence:
            text = sentence['text']
            is_ongoing = not RecognitionResult.is_sentence_end(sentence)
            
            if is_ongoing:
                # 部分结果：显示原文
                print(f'部分：{text}', end='\r')
                display_text = text
            else:
                # 完整句子：检测语言并翻译
                # 使用同步方法检测语言
                source_lang_info = language_detector.detect(text)
                source_lang = source_lang_info['language']
                
                # 标准化语言代码以便比较
                def normalize_lang(lang):
                    """标准化语言代码"""
                    lang_lower = lang.lower()
                    # 处理中文的各种变体
                    if lang_lower in ['zh', 'zh-cn', 'zh-tw', 'zh-hans', 'zh-hant']:
                        return 'zh'
                    # 处理英语
                    if lang_lower in ['en', 'en-us', 'en-gb']:
                        return 'en'
                    return lang_lower
                
                normalized_source = normalize_lang(source_lang)
                normalized_target = normalize_lang(TARGET_LANGUAGE)
                
                # 判断是否需要使用备用语言
                if FALLBACK_LANGUAGE and normalized_source == normalized_target:
                    # 源语言和目标语言相同，使用备用语言
                    actual_target = FALLBACK_LANGUAGE
                    print(f'原文：{text} [{source_lang_info["language"]}]')
                    print(f'检测到源语言与目标语言相同，使用备用语言: {FALLBACK_LANGUAGE}')
                else:
                    # 使用默认目标语言
                    actual_target = TARGET_LANGUAGE
                    print(f'原文：{text} [{source_lang_info["language"]}]')
                
                # 执行翻译
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
            
            # 根据配置决定是否发送部分结果
            should_send = (not is_ongoing) or SHOW_PARTIAL_RESULTS
            
            # 从其他线程安全地调度协程到主事件循环
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
            elif not self.loop:
                print('[OSC] Warning: Event loop not set, cannot send OSC message.')

            if is_translated:
                # 反向翻译
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
            channels=channels,
            rate=sample_rate,
            input=True,
            frames_per_buffer=block_size
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
            return stream.read(block_size, exception_on_overflow=False)
        except Exception as e:
            print(f'Error reading audio data: {e}')
            return None
    
    return await loop.run_in_executor(executor, _read)


async def send_audio_frame_async(recognition, data):
    """异步发送音频帧"""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(executor, recognition.send_audio_frame, data)
    except Exception as e:
        pass
    

async def audio_capture_task(recognition):
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
                await send_audio_frame_async(recognition, data)
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


async def stop_recognition_async(recognition):
    """异步停止识别服务"""
    global recognition_active
    if not recognition_active:
        return  # 已经停止
    
    # 发送静音音频帧，确保本次识别至少发送了一个音频帧，否则会报错
    silence_frames = block_size
    silence_data = b'\x00' * (bits // 8 * silence_frames)
    
    # 发送静音数据
    await send_audio_frame_async(recognition, silence_data)
    
    recognition_active = False
    
    # 等待一小段时间确保静音数据被处理
    await asyncio.sleep(0.1)
    
    # 停止识别
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, recognition.stop)
    except Exception as e:
        pass
    
    

async def start_recognition_async(recognition):
    """异步开始识别服务"""
    global recognition_active
    if recognition_active:
        print('Recognition already active.')
        return  # 已经在运行中
    
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, recognition.start)
    except Exception as e:
        pass

    recognition_active = True


async def handle_mute_change(is_muted):
    """
    处理静音状态变化的回调函数
    
    Args:
        is_muted: True表示静音(停止识别), False表示取消静音(开始识别)
    """
    global recognition_active, recognition_instance, mute_delay_task
    
    # 如果禁用了麦克风控制，则忽略所有麦克风状态变化
    if not ENABLE_MIC_CONTROL:
        return
    
    if recognition_instance is None:
        print('[ASR] 识别实例未初始化')
        return
    
    if is_muted:
        # 静音状态 - 延迟停止识别
        if recognition_active:
            # 如果已有延迟任务在运行，先取消它
            if mute_delay_task and not mute_delay_task.done():
                mute_delay_task.cancel()
            
            if MUTE_DELAY_SECONDS > 0:
                print(f'[ASR] 检测到静音，将在 {MUTE_DELAY_SECONDS} 秒后停止语音识别...')
                
                async def delayed_stop():
                    global recognition_active
                    try:
                        await asyncio.sleep(MUTE_DELAY_SECONDS)
                        if recognition_active:  # 再次检查，确保期间没有取消静音
                            print('[ASR] 延迟时间到，停止语音识别')
                            await stop_recognition_async(recognition_instance)
                            logger.info('[ASR] 语音识别已停止')
                    except asyncio.CancelledError:
                        print('[ASR] 停止识别已取消（取消静音）')
                
                mute_delay_task = asyncio.create_task(delayed_stop())
            else:
                # 延迟为0，立即停止
                print('[ASR] 检测到静音，立即停止语音识别...')
                await stop_recognition_async(recognition_instance)
                logger.info('[ASR] 语音识别已停止')
    else:
        # 取消静音 - 开始识别
        # 如果有延迟停止任务，取消它
        if mute_delay_task and not mute_delay_task.done():
            mute_delay_task.cancel()
            print('[ASR] 检测到取消静音，已取消延迟停止任务')
        
        if not recognition_active:
            print('[ASR] 检测到取消静音，开始语音识别...')
            await start_recognition_async(recognition_instance)
            logger.info('[ASR] 语音识别已开始')


async def main():
    """主异步函数"""
    global recognition_instance, recognition_active, vocabulary_id
    
    init_dashscope_api_key()
    print('Initializing ...')

    # 初始化热词（如果启用）
    if ENABLE_HOT_WORDS:
        print('\n[热词] 初始化热词表...')
        try:
            hot_words_manager = HotWordsManager()
            hot_words_manager.load_all_hot_words()
            # hot_words_manager.print_hot_words_summary()
            
            vocabulary_id = hot_words_manager.create_vocabulary(target_model='fun-asr-realtime')
            print(f'[热词] 热词表创建成功，ID: {vocabulary_id}\n')
        except Exception as e:
            print(f'[热词] 热词初始化失败: {e}')
            print('[热词] 将继续运行但不使用热词\n')
            vocabulary_id = None

    # 启动OSC服务器
    print('[OSC] 启动OSC服务器...')
    await osc_manager.start_server()
    
    # 设置静音状态回调
    osc_manager.set_mute_callback(handle_mute_change)
    print('[OSC] 已设置静音状态回调')

    # Create the recognition callback
    callback = Callback()
    # 设置事件循环引用,以便在回调中使用
    callback.loop = asyncio.get_event_loop()

    # 创建识别实例
    recognition_kwargs = {
        'model': 'fun-asr-realtime',
        'format': format_pcm,
        'sample_rate': sample_rate,
        'semantic_punctuation_enabled': True,
        'callback': callback
    }
    
    # 如果有热词表 ID，添加到参数中
    if vocabulary_id:
        recognition_kwargs['vocabulary_id'] = vocabulary_id
        print(f'[ASR] 使用热词表: {vocabulary_id}')
    
    recognition_instance = Recognition(**recognition_kwargs)
    
    print('[ASR] 识别实例已创建')
    
    # 初始化音频流
    await init_audio_stream()

    signal.signal(signal.SIGINT, signal_handler)
    
    # 根据配置决定是否立即启动识别
    if ENABLE_MIC_CONTROL:
        print("=" * 60)
        print("[模式] 麦克风控制模式已启用")
        print("等待VRChat静音状态变化...")
        print("取消静音(MuteSelf=False)将开始语音识别")
        print("启用静音(MuteSelf=True)将停止语音识别")
        print("按 'Ctrl+C' 退出程序")
        print("=" * 60)
    else:
        print("=" * 60)
        print("[模式] 麦克风控制模式已禁用")
        print("语音识别将立即启动，忽略麦克风开关状态")
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
            print('Recognition stopped.')
        
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
        # 清除OSC回调
        osc_manager.clear_mute_callback()
        
        # 关闭音频流
        await close_audio_stream()
        
        # 停止OSC服务器
        await osc_manager.stop_server()
        
        # 异步关闭线程池
        loop = asyncio.get_event_loop()
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