// API基础URL
const API_BASE = '/api';

// 自动保存定时器
let autoSaveTimer = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    loadConfig();
    loadAPIKeys();
    updateStatus();
    // 每2秒更新一次状态
    setInterval(updateStatus, 2000);
});

// 从localStorage加载API Keys
function loadAPIKeys() {
    const dashscopeKey = localStorage.getItem('dashscope_api_key');
    const deeplKey = localStorage.getItem('deepl_api_key');
    const openrouterKey = localStorage.getItem('openrouter_api_key');
    
    if (dashscopeKey) document.getElementById('dashscope-api-key').value = dashscopeKey;
    if (deeplKey) document.getElementById('deepl-api-key').value = deeplKey;
    if (openrouterKey) document.getElementById('openrouter-api-key').value = openrouterKey;
    
    // 添加API Key change事件监听
    document.getElementById('dashscope-api-key').addEventListener('input', saveAPIKey);
    document.getElementById('deepl-api-key').addEventListener('input', saveAPIKey);
    document.getElementById('openrouter-api-key').addEventListener('input', saveAPIKey);
}

// 保存API Key到localStorage
function saveAPIKey(event) {
    const id = event.target.id;
    const value = event.target.value;
    const keyName = id.replace('-', '_');
    
    if (value) {
        localStorage.setItem(keyName, value);
        // 写入.env文件
        updateEnvFile(keyName, value);
    } else {
        localStorage.removeItem(keyName);
    }
}

// 更新.env文件（通过显示提示信息）
function updateEnvFile(keyName, value) {
    // 这里只是提示用户，实际的.env文件需要用户手动更新或服务端支持
    console.log(`请将 ${keyName.toUpperCase()}=${value} 添加到 .env 文件中`);
}

// 加载配置
async function loadConfig() {
    try {
        const response = await fetch(`${API_BASE}/config`);
        const config = await response.json();
        
        // 填充表单
        document.getElementById('enable-translation').checked = config.translation.enable_translation;
        document.getElementById('target-language').value = config.translation.target_language;
        document.getElementById('fallback-language').value = config.translation.fallback_language || '';
        document.getElementById('translation-api-type').value = config.translation.api_type;
        
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
        
        // 根据翻译开关显示/隐藏翻译选项
        toggleTranslationOptions();
        
    } catch (error) {
        console.error('加载配置失败:', error);
        showMessage('加载配置失败', 'error');
    }
}

// 切换翻译选项的显示/隐藏
function toggleTranslationOptions() {
    const enableTranslation = document.getElementById('enable-translation').checked;
    const translationOptions = document.getElementById('translation-options');
    
    if (enableTranslation) {
        translationOptions.classList.remove('hidden');
    } else {
        translationOptions.classList.add('hidden');
    }
}

// 当设置改变时自动保存（延迟保存，避免频繁请求）
function onSettingChange() {
    // 清除之前的定时器
    if (autoSaveTimer) {
        clearTimeout(autoSaveTimer);
    }
    
    // 500ms后自动保存
    autoSaveTimer = setTimeout(async () => {
        await saveConfig(true); // true表示是自动保存，不重启服务
        
        // 如果服务正在运行，自动重启
        const statusResponse = await fetch(`${API_BASE}/status`);
        const status = await statusResponse.json();
        if (status.running) {
            await restartService();
        }
    }, 500);
}

// 保存配置
async function saveConfig(autoSave = false) {
    try {
        const config = {
            translation: {
                enable_translation: document.getElementById('enable-translation').checked,
                target_language: document.getElementById('target-language').value,
                fallback_language: document.getElementById('fallback-language').value || null,
                api_type: document.getElementById('translation-api-type').value,
                source_language: document.getElementById('source-language').value,
                show_partial_results: false,  // 默认不显示部分结果
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
            if (!autoSave) {
                showMessage('配置保存成功！', 'success');
            }
        } else {
            showMessage('配置保存失败: ' + result.message, 'error');
        }
    } catch (error) {
        console.error('保存配置失败:', error);
        if (!autoSave) {
            showMessage('保存配置失败', 'error');
        }
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

// 重启服务
async function restartService() {
    try {
        const response = await fetch(`${API_BASE}/service/restart`, {
            method: 'POST',
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log('服务已重启');
            setTimeout(updateStatus, 500);
        }
    } catch (error) {
        console.error('重启服务失败:', error);
    }
}

// 恢复默认设置
async function resetToDefaults() {
    if (!confirm('确定要恢复默认设置吗？（API Keys将被保留）')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/config/defaults`);
        const defaults = await response.json();
        
        // 填充表单
        document.getElementById('enable-translation').checked = defaults.translation.enable_translation;
        document.getElementById('target-language').value = defaults.translation.target_language;
        document.getElementById('fallback-language').value = defaults.translation.fallback_language || '';
        document.getElementById('translation-api-type').value = defaults.translation.api_type;
        
        document.getElementById('enable-mic-control').checked = defaults.mic_control.enable_mic_control;
        document.getElementById('mute-delay').value = defaults.mic_control.mute_delay_seconds;
        
        document.getElementById('asr-backend').value = defaults.asr.preferred_backend;
        document.getElementById('enable-hot-words').checked = defaults.asr.enable_hot_words;
        document.getElementById('enable-vad').checked = defaults.asr.enable_vad;
        document.getElementById('vad-threshold').value = defaults.asr.vad_threshold;
        document.getElementById('vad-silence-duration').value = defaults.asr.vad_silence_duration_ms;
        document.getElementById('keepalive-interval').value = defaults.asr.keepalive_interval;
        
        document.getElementById('language-detector').value = defaults.language_detector.type;
        document.getElementById('source-language').value = defaults.translation.source_language;
        
        // 保存配置
        await saveConfig();
        showMessage('已恢复默认设置', 'success');
        
        // 如果服务正在运行，重启
        const statusResponse = await fetch(`${API_BASE}/status`);
        const status = await statusResponse.json();
        if (status.running) {
            await restartService();
        }
    } catch (error) {
        console.error('恢复默认设置失败:', error);
        showMessage('恢复默认设置失败', 'error');
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
    
    // 更新图标
    if (content.classList.contains('collapsed')) {
        icon.textContent = '▶';
    } else {
        icon.textContent = '▼';
    }
}
