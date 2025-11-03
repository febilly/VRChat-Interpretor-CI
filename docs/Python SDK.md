# 实时语音识别（Qwen-ASR-Realtime）Python SDK

本文档介绍如何使用 DashScope Python SDK 调用实时语音识别（Qwen-ASR-Realtime）模型。

\*\*用户指南：\*\*模型介绍、功能特性和示例代码请参见[实时语音识别-通义千问](https://help.aliyun.com/zh/model-studio/qwen-real-time-speech-recognition)

-----

## 请求参数

  * 以下参数通过 `OmniRealtimeConversation` 的构造方法设置。

| 参数 | 类型 | 是否必须 | 说明 |
| :--- | :--- | :--- | :--- |
| `model` | `str` | 是 | 指定要使用的[模型](https://help.aliyun.com/zh/model-studio/qwen-real-time-speech-recognition#ff8c59ef0busr)名称。 |
| `callback` | [`OmniRealtimeCallback`](https://www.google.com/search?q=%23%E5%9B%9E%E8%B0%83%E6%8E%A5%E5%8F%A3-omnirealtimecallback) | 是 | 用于处理服务端事件的回调对象实例。 |

  * 以下参数通过 `OmniRealtimeConversation` 的 `update_session` 方法设置。

| 参数 | 类型 | 是否必须 | 说明 |
| :--- | :--- | :--- | :--- |
| `output_modalities` | `List[MultiModality]` | 是 | 模型输出模态，固定为 `[MultiModality.TEXT]`。 |
| `enable_turn_detection` | `bool` | 否 | 是否开启服务端语音活动检测（VAD）。关闭后，需手动调用 `commit()` 方法触发识别。<br>默认值：`True`。<br>取值范围：<br>\<ul\>\<li\>`True`：开启\</li\>\<li\>`False`：关闭\</li\>\</ul\> |
| `turn_detection_type` | `str` | 否 | 服务端 VAD 类型，固定为 `server_vad`。 |
| `turn_detection_threshold` | `float` | 否 | VAD 检测阈值。<br>默认值：`0.2`。<br>取值范围：`[-1.0, 1.0]`。<br>较低的阈值会提高 VAD 的灵敏度，可能将背景噪音误判为语音。较高的阈值则降低灵敏度，有助于在嘈杂环境中减少误触发。 |
| `turn_detection_silence_duration_ms` | `int` | 否 | VAD 断句检测阈值（ms）。静音持续时长超过该阈值将被认为是语句结束。<br>默认值：`800`。<br>取值范围：`[200, 6000]`。<br>较低的值（如 300ms）可使模型更快响应，但可能导致在自然停顿处发生不合理的断句。较高的值（如 1200ms）可更好地处理长句内的停顿，但会增加整体响应延迟。 |
| `transcription_params` | [`TranscriptionParams`](https://www.google.com/search?q=%23transcriptionparams-%E5%8F%82%E6%95%B0) | 否 | 语音识别相关配置。 |

  * \<span id="transcriptionparams-参数"\>以下参数通过 `TranscriptionParams` 的构造方法设置。\</span\>

| 参数 | 类型 | 是否必须 | 说明 |
| :--- | :--- | :--- | :--- |
| `language` | `str` | 否 | 音频源语言。<br>取值范围参见 [ISO 639-1 标准](https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes)。 |
| `sample_rate` | `int` | 否 | 音频采样率（Hz）。支持 `16000` 和 `8000`。<br>默认值：`16000`。<br>设置为 `8000` 时，服务端会先升采样到 16000Hz 再进行识别，可能引入微小延迟。建议仅在源音频为 8000Hz（如电话线路）时使用。 |
| `input_audio_format` | `str` | 否 | 音频格式。支持 `pcm` 和 `opus`。<br>默认值：`pcm`。 |
| `corpus_text` | `str` | 否 | ASR 语料文本。提供与业务场景强相关的专有词汇（如产品名、人名），可以提升模型对这些词汇的识别准确度。 |

-----

## 关键接口

### OmniRealtimeConversation 类

OmniRealtimeConversation 通过 `from dashscope.audio.qwen_omni import OmniRealtimeConversation` 方法引入。

| 方法签名 | 服务端响应事件（通过回调下发） | 说明 |
| :--- | :--- | :--- |
| `def connect(self,) -> None` | [session.created](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-server-events#2c04b24bc3wlo)<br>\<blockquote\>会话已创建\</blockquote\>[session.updated](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-server-events#4d6ed9dd62vmj)<br>\<blockquote\>会话配置已更新\</blockquote\> | 和服务端创建连接。 |
| `def update_session(self,`<br>`                        output_modalities: List[MultiModality], `<br>`                        voice: str = None, `<br>`                        input_audio_format: AudioFormat = AudioFormat. `<br>`                        PCM_16000HZ_MONO_16BIT, `<br>`                        output_audio_format: AudioFormat = AudioFormat. `<br>`                        PCM_24000HZ_MONO_16BIT, `<br>`                        enable_input_audio_transcription: bool = True, `<br>`                        input_audio_transcription_model: str = None, `<br>`                        enable_turn_detection: bool = True, `<br>`                        turn_detection_type: str = 'server_vad', `<br>`                        prefix_padding_ms: int = 300, `<br>`                        turn_detection_threshold: float = 0.2, `<br>`                        turn_detection_silence_duration_ms: int = 800, `<br>`                        turn_detection_param: dict = None, `<br>`                        translation_params: TranslationParams = None, `<br>`                        transcription_params: TranscriptionParams = None, `<br>`                        **kwargs) -> None ` | [session.updated](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-server-events#4d6ed9dd62vmj)<br>\<blockquote\>会话配置已更新\</blockquote\> | 用于更新会话配置，建议在连接建立后首先调用该方法进行设置。若未调用该方法，系统将使用默认配置。只需关注[请求参数](https://www.google.com/search?q=%23%E8%AF%B7%E6%B1%82%E5%8F%82%E6%95%B0)中的涉及到的参数。 |
| `def append_audio(self, audio_b64: str) -> None` | 无 | 将 Base64 编码后的音频数据片段追加到云端输入音频缓冲区。 <br>\<ul\>\<li\>[请求参数](https://www.google.com/search?q=%23%E8%AF%B7%E6%B1%82%E5%8F%82%E6%95%B0) `enable_turn_detection` 设为 `True`，音频缓冲区用于检测语音，服务端决定何时提交。\</li\>\<li\>[请求参数](https://www.google.com/search?q=%23%E8%AF%B7%E6%B1%82%E5%8F%82%E6%95%B0) `enable_turn_detection` 设为 `False`，客户端可以选择每个事件中放置多少音频量，最多放置 15 MiB。 例如，从客户端流式处理较小的数据块可以让 VAD 响应更迅速。\</li\>\</ul\> |
| `def commit(self, ) -> None` | [input\_audio\_buffer.committed](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-server-events#1108a3764an0e)<br>\<blockquote\>服务端收到提交的音频\</blockquote\> | 提交之前通过 append 添加到云端缓冲区的音视频，如果输入的音频缓冲区为空将产生错误。<br>\<b\>禁用场景：\</b\>[请求参数](https://www.google.com/search?q=%23%E8%AF%B7%E6%B1%82%E5%8F%82%E6%95%B0) `enable_turn_detection` 设为 `True` 时。 |
| `def cancel_response(self, ) -> None` | 无 | 取消正在进行的响应。如果没有任何响应可供取消，服务端将以一个错误进行响应。 |
| `def close(self, ) -> None` | 无 | 终止任务，并关闭连接。 |
| `def get_session_id(self) -> str` | 无 | 获取当前任务的 session\_id。 |
| `def get_last_response_id(self) -> str` | 无 | 获取最近一次 response 的 response\_id。 |
| `def get_last_first_text_delay(self)` | 无 | 获取最近一次 response 的首包文本延迟。 |
| `def get_last_first_audio_delay(self)` | 无 | 获取最近一次 response 的首包音频延迟。 |

### 回调接口（OmniRealtimeCallback）

服务端会通过回调的方式，将服务端响应事件和数据返回给客户端。

继承此类并实现相应方法以处理服务端事件。

通过 `from dashscope.audio.qwen_omni import OmniRealtimeCallback` 引入。

| 方法签名 | 参数 | 说明 |
| :--- | :--- | :--- |
| `def on_open(self) -> None` | 无 | WebSocket 连接成功建立时触发。 |
| `def on_event(self, message: str) -> None` | message：[服务端事件](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-server-events) | 收到服务端事件时触发。 |
| `def on_close(self, close_status_code, close_msg) -> None` | close\_status\_code：状态码<br>close\_msg：WebSocket 连接关闭时的日志信息 | WebSocket 连接关闭时触发。 |