# -*- coding: utf-8 -*-

# AG-UI 协议版本
AGUI_PROTOCOL_VERSION = "v2"

# 用户授权页参数，拼在智能体访问地址后；页面需请求插件 ping 接口写入 bkoauth access_token
AUTHORIZE_PAGE_QUERY = "?authorization=success"

# 对话入口授权校验开关：默认校验（未设置 / 空值都校验），仅显式配成下列“假值”之一才关闭。
# 无法识别的取值按校验处理，避免写错值导致授权拦截被意外关闭。
# 直接读环境变量，避免依赖尚未发布的 aidev_agent 配置项。
AUTHORIZATION_CHECK_ENV = "BKAI_AGENT_AUTHORIZATION_CHECK_ENABLED"
AUTHORIZATION_CHECK_OFF_VALUES = frozenset({"false", "0", "no", "off"})

# 会话列表默认分页参数
DEFAULT_SESSION_PAGE = 1
DEFAULT_SESSION_PAGE_SIZE = 20

# 用户操作类型
# - FLOW_NODE_RETRY：重试 flow 节点
# - FLOW_NODE_SKIP：跳过 flow 节点
# - APPROVAL_CANCEL：取消人工审批
OPERATION_FLOW_NODE_RETRY = "flow_node_retry"
OPERATION_FLOW_NODE_SKIP = "flow_node_skip"
OPERATION_APPROVAL_CANCEL = "approval_cancel"
OPERATION_CHOICES = (
    OPERATION_FLOW_NODE_RETRY,
    OPERATION_FLOW_NODE_SKIP,
    OPERATION_APPROVAL_CANCEL,
)
