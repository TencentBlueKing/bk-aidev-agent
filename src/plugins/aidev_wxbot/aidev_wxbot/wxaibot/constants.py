"""
WxAiBot 常量定义。

集中管理企微机器人相关的常量，便于维护和国际化。
"""

# 用户输入提示
EMPTY_INPUT_PROMPT = "请输入您想要咨询的内容~"
WRONG_MENTION_PROMPT = "请先@本机器人，然后输入您想要咨询的内容~"

# 新会话命令
NEW_CONVERSATION_CMDS = frozenset({"会话", "新会话"})

# 聊天类型
GROUP_CHAT_TYPE = "group"
SINGLE_CHAT_TYPE = "single"

# 流式响应提示
THINKING_MESSAGE = "正在思考中..."

# RabbitMQ 队列自动过期时间
QUEUE_EXPIRES_MS = 360000
WS_INSTANCE_LOCK_CACHE_KEY_PREFIX = "wxaibot:ws:instance:"
