// API基础URL
const API_BASE = '/api';

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    loadConfig();
    updateStatus();
    // 每2秒更新一次状态
    setInterval(updateStatus, 2000);
});

// 加载配置
async function loadConfig() {
    try {
        const response = await fetch(`${API_BASE}/config`);
        const config = await response.json();
        
        // 填充表单
        document.getElementById('enable-translation').checked = config.translation.enable_translation;
        document.getElementById('target-language').value = config.translation.target_language;
        document.getElementById('fallback-language').value = config.translation.fallback_language || '';
        document.getElementById('translation-api').value = config.translation.api_type;
        document.getElementById('show-partial-results').checked = config.translation.show_partial_results;
        
        document.getElementById('enable-mic-control').checked = config.mic_control.enable_mic_control;
        document.getElementById('mute-delay').value = config.mic_control.mute_delay_seconds;
        
        document.getElementById('asr-backend').value = config.asr.preferred_backend;
        document.getElementById('enable-hot-words').checked = config.asr.enable_hot_words;
        document.getElementById('enable-vad').checked = config.asr.enable_vad;
        document.getElementById('vad-threshold').value = config.asr.vad_threshold;
        document.getElementById('vad-silence-duration').value = config.asr.vad_silence_duration_ms;
        document.getElementById('keepalive-interval').value = config.asr.keepalive_interval;
        
        document.getElementById('language-detector').value = config.language_detector.type;
        document.getElementById('source-language').value = config.translation.source_language;
        
    } catch (error) {
        console.error('加载配置失败:', error);
        showMessage('加载配置失败', 'error');
    }
}

// 保存配置
async function saveConfig() {
    const saveBtn = document.getElementById('save-btn');
    saveBtn.disabled = true;
    saveBtn.textContent = '保存中...';
    
    try {
        const config = {
            translation: {
                enable_translation: document.getElementById('enable-translation').checked,
                target_language: document.getElementById('target-language').value,
                fallback_language: document.getElementById('fallback-language').value || null,
                api_type: document.getElementById('translation-api').value,
                show_partial_results: document.getElementById('show-partial-results').checked,
                source_language: document.getElementById('source-language').value,
            },
            mic_control: {
                enable_mic_control: document.getElementById('enable-mic-control').checked,
                mute_delay_seconds: parseFloat(document.getElementById('mute-delay').value),
            },
            asr: {
                preferred_backend: document.getElementById('asr-backend').value,
                enable_hot_words: document.getElementById('enable-hot-words').checked,
                enable_vad: document.getElementById('enable-vad').checked,
                vad_threshold: parseFloat(document.getElementById('vad-threshold').value),
                vad_silence_duration_ms: parseInt(document.getElementById('vad-silence-duration').value),
                keepalive_interval: parseInt(document.getElementById('keepalive-interval').value),
            },
            language_detector: {
                type: document.getElementById('language-detector').value,
            }
        };
        
        const response = await fetch(`${API_BASE}/config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config),
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage('配置保存成功！如需生效，请重启服务。', 'success');
        } else {
            showMessage('配置保存失败: ' + result.message, 'error');
        }
    } catch (error) {
        console.error('保存配置失败:', error);
        showMessage('保存配置失败', 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = '保存配置';
    }
}

// 更新服务状态
async function updateStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const status = await response.json();
        
        const statusText = document.getElementById('status-text');
        const statusDot = document.getElementById('status-dot');
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        
        if (status.running) {
            statusText.textContent = '服务运行中';
            statusDot.classList.add('running');
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            statusText.textContent = '服务未运行';
            statusDot.classList.remove('running');
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
    } catch (error) {
        console.error('更新状态失败:', error);
    }
}

// 启动服务
async function startService() {
    const startBtn = document.getElementById('start-btn');
    startBtn.disabled = true;
    startBtn.textContent = '启动中...';
    
    try {
        const response = await fetch(`${API_BASE}/service/start`, {
            method: 'POST',
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage('服务启动成功', 'success');
            setTimeout(updateStatus, 500);
        } else {
            showMessage('服务启动失败: ' + result.message, 'error');
            startBtn.disabled = false;
        }
    } catch (error) {
        console.error('启动服务失败:', error);
        showMessage('启动服务失败', 'error');
        startBtn.disabled = false;
    } finally {
        startBtn.textContent = '启动服务';
    }
}

// 停止服务
async function stopService() {
    const stopBtn = document.getElementById('stop-btn');
    stopBtn.disabled = true;
    stopBtn.textContent = '停止中...';
    
    try {
        const response = await fetch(`${API_BASE}/service/stop`, {
            method: 'POST',
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage('服务停止成功', 'success');
            setTimeout(updateStatus, 500);
        } else {
            showMessage('服务停止失败: ' + result.message, 'error');
            stopBtn.disabled = false;
        }
    } catch (error) {
        console.error('停止服务失败:', error);
        showMessage('停止服务失败', 'error');
        stopBtn.disabled = false;
    } finally {
        stopBtn.textContent = '停止服务';
    }
}

// 显示消息
function showMessage(text, type) {
    const messageEl = document.getElementById('message');
    messageEl.textContent = text;
    messageEl.className = 'message ' + type;
    
    // 3秒后自动隐藏
    setTimeout(() => {
        messageEl.className = 'message';
    }, 3000);
}

// 折叠/展开面板
function toggleCollapsible(id) {
    const content = document.getElementById(id);
    const icon = document.getElementById(id + '-icon');
    
    content.classList.toggle('collapsed');
    icon.classList.toggle('collapsed');
}
