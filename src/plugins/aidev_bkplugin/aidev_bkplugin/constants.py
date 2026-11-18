# -*- coding: utf-8 -*-

# AG-UI 协议版本
AGUI_PROTOCOL_VERSION = "v2"

# 用户授权页参数，拼在智能体访问地址后；页面需请求插件 ping 接口写入 bkoauth access_token
AUTHORIZE_PAGE_QUERY = "?authorization=success"

# 对话入口授权校验开关：默认校验；变量名虽带 ENABLED，但只要配置了非空值就关闭校验
# （与取值无关，``=false`` 同样关闭）。直接读环境变量，避免依赖尚未发布的 aidev_agent 配置项。
AUTHORIZATION_CHECK_ENV = "BKAI_AGENT_AUTHORIZATION_CHECK_ENABLED"

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
