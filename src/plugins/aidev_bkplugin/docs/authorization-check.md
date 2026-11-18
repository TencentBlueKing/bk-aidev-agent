# 对话入口授权校验开关

Web `chat` 接口与企微 wxbot 在进入 Agent 执行前，会检查当前用户是否已有可用的
bkoauth `access_token`；没有则返回授权提示，引导用户到授权页完成授权后重新发送消息。
两个入口共用 `AgentHelper.get_authorize_prompt`，开关也在该方法内统一生效。

## 默认行为

默认开启校验，存量环境升级后行为不变，无需补任何配置。

## 关闭校验

配置环境变量 `BKAI_AGENT_AUTHORIZATION_CHECK_ENABLED`（任意非空值）即关闭校验：

```bash
export BKAI_AGENT_AUTHORIZATION_CHECK_ENABLED=1
```

注意变量名历史沿用，**语义是“配置了就关闭”**，与取值无关：`=false`、`=0` 同样会关闭。
要恢复校验，需要删除该变量，而不是改成 `false`。Web 与企微入口共用同一个开关，
应在两个进程里保持一致。

## 影响范围

- 只影响对话入口的授权拦截，授权页（`?authorization=success`）和授权状态查询接口不变。
- 关闭后，没有 `access_token` 的用户会直接进入 Agent 执行；依赖用户态 token 的工具调用
  在没有 token 时仍会按各自逻辑失败。
- flow 节点、子智能体等内部调用本来就没有这层校验，不受开关影响。
