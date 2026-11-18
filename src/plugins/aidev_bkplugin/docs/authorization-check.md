# 对话入口授权校验开关

Web `chat` 接口与企微 wxbot 在进入 Agent 执行前，会检查当前用户是否已有可用的
bkoauth `access_token`；没有则返回授权提示，引导用户到授权页完成授权后重新发送消息。
两个入口共用 `AgentHelper.get_authorize_prompt`，开关也在该方法内统一生效。

## 默认行为

默认开启校验。未设置环境变量 `BKAI_AGENT_AUTHORIZATION_CHECK_ENABLED` 或值为空时都校验，
存量环境升级后行为不变，无需补任何配置。

## 关闭校验

在对应模块的环境变量里把 `BKAI_AGENT_AUTHORIZATION_CHECK_ENABLED` 配成 `false`：

```bash
export BKAI_AGENT_AUTHORIZATION_CHECK_ENABLED=false
```

取值规则（不分大小写，忽略首尾空格）：

| 取值 | 行为 |
|---|---|
| 未设置 / 空值 | 校验 |
| `true` / `1` / `yes` / `on` | 校验 |
| `false` / `0` / `no` / `off` | **关闭校验** |
| 其它无法识别的值（如拼写错误的 `flase`） | 校验 |

无法识别的值按校验处理，避免写错取值时授权拦截被意外关闭。恢复校验可以删除该变量，
或改成 `true`。Web 与企微入口共用同一个开关，如果两者是不同进程或模块，需要在两边都配。

## 影响范围

- 只影响对话入口的授权拦截，授权页（`?authorization=success`）和授权状态查询接口不变。
- 关闭后，没有 `access_token` 的用户会直接进入 Agent 执行；依赖用户态 token 的工具调用
  在没有 token 时仍会按各自逻辑失败。
- flow 节点、子智能体等内部调用本来就没有这层校验，不受开关影响。
