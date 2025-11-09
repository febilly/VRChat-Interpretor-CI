"""
Web UI for VRChat Translator
提供配置管理和服务控制的Web界面
"""
import asyncio
import json
import threading
from typing import Optional
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import sys
import os

# 添加父目录到路径以导入config和main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

app = Flask(__name__)
CORS(app)

# 全局状态
service_status = {
    'running': False,
    'recognition_active': False,
    'backend': config.PREFERRED_ASR_BACKEND
}

service_thread: Optional[threading.Thread] = None
service_loop: Optional[asyncio.AbstractEventLoop] = None
stop_event: Optional[asyncio.Event] = None


def get_config_dict():
    """获取当前配置"""
    return {
        # 语音识别配置
        'asr': {
            'preferred_backend': config.PREFERRED_ASR_BACKEND,
            'enable_vad': config.ENABLE_VAD,
            'vad_threshold': config.VAD_THRESHOLD,
            'vad_silence_duration_ms': config.VAD_SILENCE_DURATION_MS,
            'keepalive_interval': config.KEEPALIVE_INTERVAL,
            'enable_hot_words': config.ENABLE_HOT_WORDS,
        },
        # 翻译配置
        'translation': {
            'enable_translation': config.ENABLE_TRANSLATION,
            'source_language': config.SOURCE_LANGUAGE,
            'target_language': config.TARGET_LANGUAGE,
            'fallback_language': config.FALLBACK_LANGUAGE,
            'api_type': config.TRANSLATION_API_TYPE,
            'show_partial_results': config.SHOW_PARTIAL_RESULTS,
        },
        # 麦克风控制配置
        'mic_control': {
            'enable_mic_control': config.ENABLE_MIC_CONTROL,
            'mute_delay_seconds': config.MUTE_DELAY_SECONDS,
        },
        # 语言检测器配置
        'language_detector': {
            'type': config.LANGUAGE_DETECTOR_TYPE,
        },
        # OSC配置
        'osc': {
            'server_ip': config.OSC_SERVER_IP,
            'server_port': config.OSC_SERVER_PORT,
            'client_ip': config.OSC_CLIENT_IP,
            'client_port': config.OSC_CLIENT_PORT,
        },
    }


def update_config(config_data):
    """更新配置"""
    try:
        # 更新ASR配置
        if 'asr' in config_data:
            asr = config_data['asr']
            if 'preferred_backend' in asr:
                config.PREFERRED_ASR_BACKEND = asr['preferred_backend']
            if 'enable_vad' in asr:
                config.ENABLE_VAD = asr['enable_vad']
            if 'vad_threshold' in asr:
                config.VAD_THRESHOLD = float(asr['vad_threshold'])
            if 'vad_silence_duration_ms' in asr:
                config.VAD_SILENCE_DURATION_MS = int(asr['vad_silence_duration_ms'])
            if 'keepalive_interval' in asr:
                config.KEEPALIVE_INTERVAL = int(asr['keepalive_interval'])
            if 'enable_hot_words' in asr:
                config.ENABLE_HOT_WORDS = asr['enable_hot_words']
        
        # 更新翻译配置
        if 'translation' in config_data:
            trans = config_data['translation']
            if 'enable_translation' in trans:
                config.ENABLE_TRANSLATION = trans['enable_translation']
            if 'source_language' in trans:
                config.SOURCE_LANGUAGE = trans['source_language']
            if 'target_language' in trans:
                config.TARGET_LANGUAGE = trans['target_language']
            if 'fallback_language' in trans:
                config.FALLBACK_LANGUAGE = trans['fallback_language'] if trans['fallback_language'] else None
            if 'api_type' in trans:
                config.TRANSLATION_API_TYPE = trans['api_type']
            if 'show_partial_results' in trans:
                config.SHOW_PARTIAL_RESULTS = trans['show_partial_results']
        
        # 更新麦克风控制配置
        if 'mic_control' in config_data:
            mic = config_data['mic_control']
            if 'enable_mic_control' in mic:
                config.ENABLE_MIC_CONTROL = mic['enable_mic_control']
            if 'mute_delay_seconds' in mic:
                config.MUTE_DELAY_SECONDS = float(mic['mute_delay_seconds'])
        
        # 更新语言检测器配置
        if 'language_detector' in config_data:
            ld = config_data['language_detector']
            if 'type' in ld:
                config.LANGUAGE_DETECTOR_TYPE = ld['type']
        
        return True
    except Exception as e:
        print(f'Error updating config: {e}')
        return False


def run_service_async():
    """在独立线程中运行异步服务"""
    global service_loop, stop_event
    
    # 创建新的事件循环
    service_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(service_loop)
    
    # 导入main模块并运行
    try:
        import main
        main.stop_event.clear()
        stop_event = main.stop_event
        service_loop.run_until_complete(main.main())
    except Exception as e:
        print(f'Service error: {e}')
    finally:
        service_loop.close()
        service_loop = None


@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置"""
    return jsonify(get_config_dict())


@app.route('/api/config', methods=['POST'])
def update_config_api():
    """更新配置"""
    try:
        config_data = request.json
        if update_config(config_data):
            return jsonify({'success': True, 'message': '配置已更新'})
        else:
            return jsonify({'success': False, 'message': '配置更新失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取服务状态"""
    return jsonify(service_status)


@app.route('/api/service/start', methods=['POST'])
def start_service():
    """启动服务"""
    global service_thread, service_status
    
    if service_status['running']:
        return jsonify({'success': False, 'message': '服务已在运行中'})
    
    try:
        service_thread = threading.Thread(target=run_service_async, daemon=True)
        service_thread.start()
        service_status['running'] = True
        return jsonify({'success': True, 'message': '服务已启动'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'启动失败: {str(e)}'}), 500


@app.route('/api/service/stop', methods=['POST'])
def stop_service():
    """停止服务"""
    global service_thread, service_status, service_loop, stop_event
    
    if not service_status['running']:
        return jsonify({'success': False, 'message': '服务未运行'})
    
    try:
        if stop_event and service_loop:
            service_loop.call_soon_threadsafe(stop_event.set)
        
        # 等待线程结束（最多10秒）
        if service_thread:
            service_thread.join(timeout=10)
        
        service_status['running'] = False
        service_status['recognition_active'] = False
        return jsonify({'success': True, 'message': '服务已停止'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'停止失败: {str(e)}'}), 500


if __name__ == '__main__':
    print('='*60)
    print('VRChat 翻译器 Web UI')
    print('访问 http://localhost:5000 打开控制面板')
    print('按 Ctrl+C 退出')
    print('='*60)
    app.run(host='0.0.0.0', port=5000, debug=False)
