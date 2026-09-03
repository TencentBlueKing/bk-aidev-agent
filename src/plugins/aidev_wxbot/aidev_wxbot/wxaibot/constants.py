"""
WxAiBot 常量定义。

集中管理企微机器人相关的常量，便于维护和国际化。
"""

# 用户输入提示
EMPTY_INPUT_PROMPT = "请输入您想要咨询的内容~"
WRONG_MENTION_PROMPT = "请先@本机器人，然后输入您想要咨询的内容~"

# 新会话命令。清空上下文重新开始。
NEW_CONVERSATION_CMDS = frozenset({"会话", "新会话", "/new"})

# 中止当前生成。只停这一次回复，不清空上下文，下一句提问仍接着当前会话。
STOP_CMDS = frozenset({"停止", "/stop"})
STOP_REPLY = "已停止本次回复。可继续提问，或发送 /new 开启新会话"
STOP_NO_ACTIVE_REPLY = "当前没有正在生成的回复"
# 追加到被中止那条回复的末尾。已输出的内容保留，只标注它是被截断的而非答完了。
STOP_NOTICE = "（已停止生成）"

PREPARING_REPLY = "正在准备回复中..."
STREAM_ERROR_REPLY = "请求处理失败，请稍后重试"
STREAM_TIMEOUT_REPLY = "处理超过 10 分钟，已终止本次请求"

# 同一会话已有回复在生成时的拒绝提示。长连接下同会话只允许一条流。
BUSY_REPLY = "当前会话正在生成回复，请等待完成，或发送 /stop 结束后再提问"
# 群里占用名额的是别人的提问时用这条：/stop 只能停自己的，让他等而不是让他去停别人的
BUSY_BY_OTHERS_REPLY = "群里有其他成员的提问正在处理，请稍后再试"
# 重试/跳过失败且卡片没能原地更新时的兜底提示。
FLOW_NODE_ACTION_FAILED_REPLY = "节点操作失败，请返回原会话查看任务状态。"
# 本地 thread 已因空闲 30 分钟或 /new 换过；旧卡仍绑着上一场 session_code。
SESSION_SWITCHED_REPLY = "当前会话已切换，此卡片已失效。请在新对话中继续。"

# 收尾时等待 Agent 统一流接口自然结束的上限（秒）。排空由 Bkplugin 有界收尾执行器执行；
# 超时会取消 Agent run，因此既不继续占住生成 worker，也不会为每条流留下新线程。
AGENT_STREAM_DRAIN_TIMEOUT = 30.0

# 帮助。命令集变化时必须同步本文案，因此与命令定义放在一起。
HELP_CMDS = frozenset({"帮助", "/help"})
HELP_REPLY = (
    "可用命令：\n"
    "/new 开启新会话，清空上下文\n"
    "/stop 停止当前正在生成的回复，保留上下文\n"
    "/title 新标题 修改当前会话标题\n"
    "/web 返回当前会话的 AI 小鲸地址\n"
    "/help 显示本说明\n"
    "\n直接发送问题即可开始咨询。群聊中需先 @ 本机器人。"
)

# 聊天类型
GROUP_CHAT_TYPE = "group"
SINGLE_CHAT_TYPE = "single"

# 流式响应提示
THINKING_MESSAGE = "正在思考中..."

# 工具调用渲染：与 Flow 节点状态共用一套图标语言
TOOL_STATUS_ICONS = {
    "calling": "🔄",
    "running": "🔄",
    "ok": "🟢",
    "error": "🔴",
}
TOOL_STATUS_LABELS = {
    "calling": "调用中",
    "running": "执行中",
    "ok": "已完成",
    "error": "执行失败",
}
# 每行的前缀，靠引用块把工具与正文在视觉上分开。
# 若企微不渲染引用块，改成 "▎" 这类竖线字符即可，纯文本下同样有分隔效果。
TOOL_LINE_PREFIX = "> "
# 只展示允许列表中的安全参数作为「操作对象」
TOOL_TARGET_LIMIT = 50

# RabbitMQ 队列自动过期时间
QUEUE_EXPIRES_MS = 360000
WS_INSTANCE_LOCK_CACHE_KEY_PREFIX = "wxaibot:ws:instance:"

# 间隔按 2s、4s、8s… 指数拉长，单次不超过 5 分钟。
APPROVAL_POLL_INITIAL_SECONDS = 2.0
APPROVAL_POLL_MAX_INTERVAL_SECONDS = 300.0
# 单个 poller 的存活预算。卡片过期由企微判定，这里封顶纯粹是不让迟迟不落终态的审批常驻后台。
APPROVAL_POLL_MAX_SECONDS = 86400.0
# 同理，同时在跑的 poller 也要封顶，否则积压的审批会拖垮线程池。
APPROVAL_POLL_MAX_CONCURRENT = 200
# 已改过名的 session_code、已认领续流的中断，都用有界登记簿记录，避免常驻进程无界增长。
ONCE_REGISTRY_MAX_ENTRIES = 4096
# 提问卡重复提交的去重标记保留时长（秒）。与卡片过期无关，只是防止缓存无限堆积。
QUESTION_SUBMIT_CLAIM_TTL = 86400
