"""
分页功能使用示例
Example of using the pagination feature

本示例展示如何启用和使用分页功能来处理超长文本
This example demonstrates how to enable and use pagination for handling long text
"""

# ============ 配置示例 ============

# 在 main.py 中的配置：
# Configuration in main.py:

# 1. 禁用分页（默认行为）- 使用截断方式
# Disabled pagination (default) - using truncation
ENABLE_PAGINATION = False  # 默认值 / Default value
PAGE_INTERVAL = 3.0

# 效果：超过144字符的文本会被截断，删除前面的句子保留后面的内容
# Effect: Text exceeding 144 characters will be truncated, removing front sentences to keep rear content

# 2. 启用分页 - 将长文本拆分成多页
# Enable pagination - split long text into multiple pages
ENABLE_PAGINATION = True
PAGE_INTERVAL = 3.0  # 每页之间的间隔时间（秒）/ Interval between pages (seconds)

# 效果：超过144字符的文本会被智能分割成多页，每页带有页码标记如 [1/3]、[2/3]、[3/3]
# Effect: Text exceeding 144 characters will be split into multiple pages with page markers like [1/3], [2/3], [3/3]

# ============ 使用场景示例 ============

# 场景1：短文本（不需要分页）
# Scenario 1: Short text (no pagination needed)
text1 = "Hello, this is a short message."
# 结果：直接显示 / Result: Display directly
# "Hello, this is a short message."

# 场景2：长文本 - 禁用分页
# Scenario 2: Long text - pagination disabled
text2 = "这是第一句。" * 30 + "这是最后一句。"  # 超过144字符 / Over 144 chars
# 结果（ENABLE_PAGINATION=False）：
# Result (ENABLE_PAGINATION=False):
# "...这是第一句。这是第一句。这是第一句。这是最后一句。"
# （删除了前面的句子，保留后面的内容，总长度≤144）
# (Front sentences removed, rear content kept, total length ≤144)

# 场景3：长文本 - 启用分页
# Scenario 3: Long text - pagination enabled
text3 = "This is sentence 1. This is sentence 2. This is sentence 3." * 5
# 结果（ENABLE_PAGINATION=True）：
# Result (ENABLE_PAGINATION=True):
# 第1页 / Page 1 (立即显示 / Immediate): "[1/3] This is sentence 1. This is sentence 2..."
# 第2页 / Page 2 (3秒后 / After 3s): "[2/3] This is sentence 3. This is sentence 1..."
# 第3页 / Page 3 (6秒后 / After 6s): "[3/3] This is sentence 2. This is sentence 3."

# ============ 高级配置 ============

# 调整分页间隔时间
# Adjust pagination interval
PAGE_INTERVAL = 2.5  # 更快的翻页速度 / Faster page turning
PAGE_INTERVAL = 5.0  # 更慢的翻页速度，给更多阅读时间 / Slower, more reading time

# ============ 技术细节 ============

# 1. 智能分割
# Smart splitting:
# - 优先在句子边界（句号、问号、感叹号等）分割
#   Prioritize splitting at sentence boundaries (period, question mark, exclamation, etc.)
# - 支持多语言标点符号（中文、日文、韩文等）
#   Support multi-language punctuation (Chinese, Japanese, Korean, etc.)
# - 如果没有合适的分割点，在空格处分割避免切断单词
#   If no suitable split point, split at spaces to avoid breaking words
# - 最后手段：在固定长度处强制分割
#   Last resort: force split at fixed length

# 2. 页码标记
# Page markers:
# - 格式：[当前页/总页数] 内容 / Format: [current/total] content
# - 示例：[1/3] This is page 1 content
# - 如果加上页码标记后超过144字符，会自动截断内容
#   If adding marker exceeds 144 chars, content will be auto-truncated

# 3. 任务管理
# Task management:
# - 新的长文本到达时，会取消之前未完成的分页任务
#   New long text will cancel previous incomplete pagination task
# - 使用锁确保分页任务串行化，避免竞态条件
#   Uses lock to serialize pagination tasks, avoiding race conditions

# 4. ongoing 消息处理
# Ongoing message handling:
# - ongoing 消息（实时识别结果）不使用分页
#   Ongoing messages (real-time recognition results) don't use pagination
# - 这避免了频繁的分页操作干扰实时显示
#   This avoids frequent pagination disrupting real-time display

# ============ 推荐设置 ============

# 场景A：追求完整性 - 使用分页
# Scenario A: Pursue completeness - use pagination
ENABLE_PAGINATION = True
PAGE_INTERVAL = 3.0
# 优点：可以看到完整的翻译结果
# Advantage: Can see complete translation
# 缺点：需要等待多次显示
# Disadvantage: Need to wait for multiple displays

# 场景B：追求即时性 - 使用截断
# Scenario B: Pursue immediacy - use truncation
ENABLE_PAGINATION = False
# 优点：立即看到结果，无需等待
# Advantage: See result immediately, no waiting
# 缺点：可能丢失前面的内容
# Disadvantage: May lose front content

# ============ 测试建议 ============

# 建议先在测试环境中尝试不同的配置，找到最适合自己的设置
# Recommend testing different configurations to find what works best for you

# 测试步骤：
# Test steps:
# 1. 设置 ENABLE_PAGINATION = False，说一段长话，观察截断效果
#    Set ENABLE_PAGINATION = False, speak long text, observe truncation
# 2. 设置 ENABLE_PAGINATION = True，说同样的长话，观察分页效果
#    Set ENABLE_PAGINATION = True, speak same long text, observe pagination
# 3. 调整 PAGE_INTERVAL，找到合适的翻页速度
#    Adjust PAGE_INTERVAL to find suitable page turning speed
