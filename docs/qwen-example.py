import logging
import os
import base64
import signal
import sys
import time
import pyaudio
import dashscope
from dashscope.audio.qwen_omni import *
from dashscope.audio.qwen_omni.omni_realtime import TranscriptionParams

from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 全局麦克风对象
mic = None
stream = None

def setup_logging():
    """配置日志输出"""
    logger = logging.getLogger('dashscope')
    logger.setLevel(logging.WARNING)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def init_api_key():
    """初始化 API Key"""
    # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用百炼API Key将下行替换为：dashscope.api_key = "sk-xxx"
    dashscope.api_key = os.environ.get('DASHSCOPE_API_KEY', 'YOUR_API_KEY')
    if dashscope.api_key == 'YOUR_API_KEY':
        print('[Warning] Using placeholder API key, set DASHSCOPE_API_KEY environment variable.')


class MyCallback(OmniRealtimeCallback):
    """实时识别回调处理"""
    def __init__(self, conversation):
        self.conversation = conversation
        self.handlers = {
            'session.created': self._handle_session_created,
            'conversation.item.input_audio_transcription.completed': self._handle_final_text,
            'conversation.item.input_audio_transcription.text': self._handle_stash_text,
            'input_audio_buffer.speech_started': lambda r: print('======Speech Start======'),
            'input_audio_buffer.speech_stopped': lambda r: print('======Speech Stop======'),
            'response.done': self._handle_response_done
        }

    def on_open(self):
        global mic
        global stream
        print('Connection opened')
        # 初始化麦克风
        mic = pyaudio.PyAudio()
        stream = mic.open(format=pyaudio.paInt16,
                          channels=1,
                          rate=16000,
                          input=True)

    def on_close(self, code, msg):
        global mic
        global stream
        print(f'Connection closed, code: {code}, msg: {msg}')
        # 清理麦克风资源
        if stream:
            stream.stop_stream()
            stream.close()
        if mic:
            mic.terminate()
        stream = None
        mic = None

    def on_event(self, response):
        try:
            handler = self.handlers.get(response['type'])
            if handler:
                handler(response)
        except Exception as e:
            print(f'[Error] {e}')

    def _handle_session_created(self, response):
        print(f"Start session: {response['session']['id']}")

    def _handle_final_text(self, response):
        print(f"Final recognized text: {response['transcript']}")

    def _handle_stash_text(self, response):
        print(f"Got stash result: {response['stash']}")

    def _handle_response_done(self, response):
        print('======RESPONSE DONE======')
        print(f"[Metric] response: {self.conversation.get_last_response_id()}, "
              f"first text delay: {self.conversation.get_last_first_text_delay()}, "
              f"first audio delay: {self.conversation.get_last_first_audio_delay()}")


def send_audio_from_microphone(conversation):
    """从麦克风实时发送音频数据"""
    global stream
    print("Recording from microphone... Press 'Ctrl+C' to stop.")
    
    while True:
        if stream:
            try:
                # 读取音频数据块
                data = stream.read(3200, exception_on_overflow=False)
                # 编码为 base64 并发送
                audio_b64 = base64.b64encode(data).decode('ascii')
                conversation.append_audio(audio_b64)
            except Exception as e:
                print(f"Error reading audio: {e}")
                break
        else:
            break


def main():
    setup_logging()
    init_api_key()

    conversation = OmniRealtimeConversation(
        model='qwen3-asr-flash-realtime',
        # 以下为北京地域url,若使用新加坡地域的模型,需将url替换为:wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime
        url='wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
        callback=MyCallback(conversation=None)  # 暂时传None,稍后注入
    )

    # 注入自身到回调
    conversation.callback.conversation = conversation

    def handle_exit(sig, frame):
        print('Ctrl+C pressed, exiting...')
        conversation.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)

    conversation.connect()

    transcription_params = TranscriptionParams(
        language='zh',
        sample_rate=16000,
        input_audio_format="pcm"
        # 输入音频的语料,用于辅助识别
        # corpus_text=""
    )

    conversation.update_session(
        output_modalities=[MultiModality.TEXT],
        enable_input_audio_transcription=True,
        transcription_params=transcription_params
    )

    try:
        send_audio_from_microphone(conversation)
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        conversation.close()
        print("Audio processing completed.")


if __name__ == '__main__':
    main()