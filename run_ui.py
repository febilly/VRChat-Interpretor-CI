#!/usr/bin/env python3
"""
VRChat 翻译器 Web UI 启动器
"""
import sys
import os

# 添加ui目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui'))

from ui.app import app
import webbrowser

if __name__ == '__main__':
    print("WebUI is now running at http://127.0.0.1:5001")
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        webbrowser.open("http://127.0.0.1:5001")
    app.run(host='127.0.0.1', port=5001, debug=False)
