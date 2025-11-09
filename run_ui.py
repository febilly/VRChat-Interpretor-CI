#!/usr/bin/env python3
"""
VRChat 翻译器 Web UI 启动器
"""
import sys
import os

# 添加ui目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui'))

from ui.app import app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
