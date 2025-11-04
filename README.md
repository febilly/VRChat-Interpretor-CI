# VRChat 翻译器 非流式输出版

更适合中国 [~~计科~~](#局限性) 宝宝体质的 VRChat 语音翻译器（翻译你自己的声音）

- 使用阿里的 [qwen3实时语音识别（默认）](https://bailian.console.aliyun.com/?tab=model#/model-market/detail/qwen3-asr-flash) 或 [Fun-ASR](https://bailian.console.aliyun.com/?tab=model#/model-market/detail/fun-asr-realtime) 进行语音转文本
- 使用 DeepL 进行翻译
    - 可以切换为开箱即用的谷歌翻译（当然你的网得行）
- 将结果通过 OSC 发送至游戏
- ~~其实就是把一堆 API 粘在了一起~~

有一些特殊功能，请看下文

## 不是已经有人做过了吗，为什么要再做一个翻译器？？？

目前，语音翻译最大的短板在语音识别上。而现有的给 VRChat 做的翻译器识别中文及带中文口音的英语的效果并不好。
_可以说我就是为了这点醋包的这顿饺子_

### 语音识别方面
- 准确性方面：
    - 断句断不准是最致命的问题，这个解决不了的话其他都白干
    - Whisper识别汉语效果实在是一坨
    - Edge的WebSpeech面对中国人口音识别效果不好
    - VRChat里经常出现一些一般的语音识别认不出来的词，需要用热词功能提升识别效果
- 一些细节的优化问题：
    - VAD断句需要一两秒的时间来等待说话结束
    - 闭麦时可能会漏掉用户说的最后一个字

### 翻译方面
- 翻译需要上下文
    - 没有上下文的话，比如看这句翻译：
        - 现在总行 _(xíng)_ 了吧？
        - Is the head office now?

## 特点

### 语音识别方面

- 准确性：
    - 使用阿里的 qwen3 或者 Fun-ASR：我试了好几个 STT 的 API，感觉阿里这个是挺好的，以及他有给免费额度
        - 但我对比的大部分都是国外的 API，感觉不是很公平...... 有更好的 API 可以跟我说一声！
    - 增加了热词词库
        - 自带一部分公共的词库
            - 部分比较， _咳咳，不太好_ 的词被我删掉了，请自行添加
        - 可自己添加私人的词库
- 断句：
    - 游戏内语音模式请使用 toggle 模式。说完一句话后，按下静音键，即视为一句话说完，马上全部进行转录。这样能提高响应速度。
        - 停止录制时会额外继续录制一小段音频（默认0.3s），防止漏掉最后一个字
    - VAD：仍然有 VAD 作为补充断句方法

### 翻译方面

- 实现了翻译的上下文，默认附带一条简短的场景说明，和最近的6条消息
- 附带备用语言选项，如果识别到的源语言和主目标语言相同，则翻译至备用语言
    - 可以实现两种语言之间的互译
- 默认使用Deepl翻译
    - 可以指定翻译的正式程度（比如对于日语来说）
    - 原生支持上下文
    - 可以自定义词库（本项目还没实现）
- 可以切换为开箱即用的谷歌翻译（但有网络连通性问题，及速率限制）
- 可以切换为使用大模型进行翻译，但由于延迟问题，默认不使用

## 局限性
- 你得会配环境（
- 目前没（懒得）写 GUI，所有配置需要在 `main.py` 里面直接改
- 使用脚本启动时系统的默认麦克风
- 需要用商业服务的API Key，有一定免费额度，但免费额度用完后需要付钱
    - 阿里云的免费额度是一次性的，但是大学生可以拿到每年的免费额度
    - DeepL的免费额度每月重置，但是怎么拿到Key需要自己想办法
        - 实在懒得折腾可以把翻译器换成谷歌的
- 目前暂不支持和其他 OSC 程序同时运行
- 语言识别默认使用一个简单的中日韩英检测器
    - 如需其他语言，请自行修改配置

## 快速开始

懒得自己写了，下面的东西让 AI 写了，我看了下，基本上写的没毛病，就凑合看一下吧，抱歉抱歉

### 1. 克隆项目

```bash
git clone https://github.com/febilly/VRChat-Interpretor-CI
cd VRChat-Interpretor-CI
```

### 2. 创建虚拟环境（推荐，非必须）

```bash
python -m venv .
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

在项目根目录创建 `.env` 文件，添加以下内容：

```env
# 必需：阿里云百炼 API Key
DASHSCOPE_API_KEY=your_dashscope_api_key_here

# 可选：DeepL API Key（如果使用默认的 DeepL 翻译）
DEEPL_API_KEY=your_deepl_api_key_here
```

### 5. 运行程序

```bash
python main.py
```

## API Key 获取

- 阿里云百炼：https://bailian.console.aliyun.com/?tab=model#/model-market/detail/fun-asr-realtime
- DeepL：https://www.deepl.com/en/pro-api

## 配置说明

在 `main.py` 文件顶部有详细的配置选项。这里的说明可能已过时，请以源码为准。

<details>

### 翻译语言配置

```python
SOURCE_LANGUAGE = 'auto'  # 翻译源语言
# 'auto': 自动检测
# 或指定：'en'=英文, 'ja'=日文, 'zh-CN'=简体中文 等

TARGET_LANGUAGE = 'ja'  # 翻译目标语言
# 'zh-CN': 简体中文
# 'en': 英文
# 'ja': 日文
# 'ko': 韩文
# 'es': 西班牙语
# 'fr': 法语 等

FALLBACK_LANGUAGE = 'zh'  # 备用翻译语言
# 当检测到源语言与目标语言相同时，自动使用此语言
# 设置为 None 则禁用此功能
```

### 语言检测器配置

```python
# 选择语言检测器（取消注释一行）
# from language_detectors.fasttext_detector import FasttextDetector as LanguageDetector  # 通用检测器
from language_detectors.cjke_detector import CJKEDetector as LanguageDetector  # 中日韩英检测器（推荐）
# from language_detectors.enzh_detector import EnZhDetector as LanguageDetector  # 中英检测器
```

**推荐配置：**
- 主要使用中日韩英语言 → 使用 `CJKEDetector`（速度快、准确度高）
- 只使用中英双语 → 使用 `EnZhDetector`
- 需要更多语言支持 → 使用 `FasttextDetector`
    - 附带一些针对中文和日语的特殊规则，提高短文本准确性

### 翻译 API 配置

```python
# 选择翻译 API（取消注释一行）
# from translators.translation_apis.google_web_api import GoogleWebAPI as TranslationAPI  # Google 标准版（免费）
# from translators.translation_apis.google_dictionary_api import GoogleDictionaryAPI as TranslationAPI  # Google 快速版（免费）
from translators.translation_apis.deepl_api import DeepLAPI as TranslationAPI  # DeepL（需 API Key）
```

**API 对比：**
| API | 优点 | 缺点 | API Key |
|-----|------|------|---------|
| Google Web | 免费、稳定 | 速度较慢 | 不需要 |
| Google Dictionary | 免费、快速 | 可能会被谷歌封杀掉 | 不需要 |
| DeepL | 质量最高 | 有免费额度限制 | 需要 |

### 翻译上下文

```python
CONTEXT_PREFIX = "This is an audio transcription of a conversation within the online multiplayer social game VRChat:"
# 为翻译提供上下文信息，提高翻译质量
# 可根据实际场景修改
```

### 麦克风控制配置

```python
ENABLE_MIC_CONTROL = True  # 是否启用 VRChat 麦克风控制
# True: 根据 VRChat 内麦克风开关控制识别启停
# False: 程序启动后立即开始识别，忽略麦克风状态

MUTE_DELAY_SECONDS = 0.3  # 静音后延迟停止的秒数
# 避免频繁开关导致识别中断
# 设置为 0 则立即停止
```

### 热词配置

```python
ENABLE_HOT_WORDS = True  # 是否启用热词功能
# True: 使用热词表提高特定词汇识别准确度
# False: 不使用热词
```

### 显示配置

```python
SHOW_PARTIAL_RESULTS = False  # 是否显示部分识别结果
# True: 识别过程中实时显示部分结果（可能覆盖掉之前的翻译结果）
# False: 只显示完整句子的识别结果（推荐）
```

### 长文本处理配置

```python
ENABLE_PAGINATION = False  # 是否启用分页功能处理超长文本（超过144字符）
# True: 将超长文本分割成多页，按间隔时间依次发送
# False: 使用截断方式，删除前面的句子保留后面的内容（默认行为）

PAGE_INTERVAL = 3.0  # 分页间隔时间（秒），启用分页时各页之间的发送间隔
# 建议设置为 2.5-5.0 秒，给玩家足够时间阅读每一页
```

**长文本处理方式对比：**

| 模式 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 截断模式（默认） | 立即显示，无延迟 | 可能丢失前面的内容 | 追求即时性，对话内容较短 |
| 分页模式 | 完整显示所有内容 | 需要等待多次显示 | 追求完整性，需要翻译长段落 |

**分页模式特点：**
- 智能分割：优先在句子边界处分割，保持语义完整
- 多语言支持：识别中日韩英等多种语言的标点符号
- 页码标记：自动添加 `[1/3]`、`[2/3]` 等页码标记
- 自动管理：新消息会取消之前未完成的分页任务

详细使用示例请参考 `docs/pagination-example.py`

</details>

## 热词配置

热词功能可以显著提高特定词汇的识别准确度，特别适合专业术语、人名、地名等。
以及某些 VRChat 的 _特殊_ 词汇

<details>

### 热词文件结构

```
STT/
├── hot_words/          # 公共热词目录（会被提交到 Git）
│   ├── zh-cn.txt      # 中文热词
│   ├── en.txt         # 英文热词
│   └── ...
└── hot_words_private/  # 私人热词目录（不会被提交到 Git）
    ├── zh-cn.txt      # 中文私人热词
    ├── en.txt         # 英文私人热词
    └── ...
```

### 热词文件格式

每个热词文件是纯文本格式，每行一个词

**注意事项：**
- 每行一个热词，不要有多余空格
- 空行会被忽略
- 总热词数量不超过 500 个（阿里云限制）

### 如何设置私人热词

- **编辑私人热词文件**

   打开 `hot_words_private/` 目录下对应语言的文件（如不存在则请手动创建）：
   例如：

   ```
   hot_words_private/zh-cn.txt
   hot_words_private/en.txt
   ```

- **启用的语言配置**

   在 `hot_words_manager.py` 中配置要加载的语言：
   
   ```python
   # 要加载的语言列表
   ENABLED_LANGUAGES = ['zh-cn', 'en']  
   # 可添加更多：['zh-cn', 'en', 'ja', 'ko']
   ```

</details>

## VRChat OSC 配置

### 启用 OSC

1. 启动 VRChat
2. 打开快捷菜单（Action Menu）
3. 进入 Options → OSC
4. 点击 "Enable" 启用 OSC

## 常见问题

### 1. 没有任何转录

- 检查系统的默认麦克风是否为你在用的麦克风
- 检查麦克风有没有声音

### 2. VRChat 聊天框没有显示

- 确认 VRChat OSC 已启用
- 如果你修改了 OSC 端口，请在 `main.py` 中同步修改 `OSC_PORT` 配置

## 附录

- 要翻译别人的声音的话建议用 [soniox](https://console.soniox.com/org/e784abf7-3ab5-4127-8823-ecfc18f68b90/projects/2b220fdd-f158-4b7a-9b12-447947b5098a/playground/speech-to-text/)，用它的网页端 Playground 就行，配合 Powertoys 的窗口裁剪器
    - 也可以试试 [LiveCaptions Translator](https://github.com/SakiRinn/LiveCaptions-Translator)
- 我还没太试过国内其他家的识别服务效果怎样，如果有更好的（并且有不少免费额度的）请告诉我谢谢

## 致谢
- 本项目部分基于阿里给的 Fun-ASR 示例代码
- 快速的 Google Translate API 来自 https://github.com/SakiRinn/LiveCaptions-Translator