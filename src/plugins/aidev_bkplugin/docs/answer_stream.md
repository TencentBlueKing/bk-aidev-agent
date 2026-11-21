# 节点只读回答流

`GET /bk_plugin/plugin_api/answer_stream/{trace_id}/` 为 SOPS 节点详情提供
`text/event-stream`。插件模板已整体挂载 `aidev_bkplugin.urls`，安装包含本功能的公共包后
无需再为每个插件编写回答流模块或添加独立路由。

## 行为

- 执行中从 AIDev 消息队列独立回放思考过程和正文；不登记消费者、不清理队列、不写 Schedule。
- 执行结束后经 `SessionManager.list_session_contents()` 按 `turn_id` 返回当前轮次思考过程；
  正文以节点正式输出为准。
- SSE 事件：`ready`、`reset`、`agui`、`end`。不存在的执行返回 404；不支持的执行返回 409。
- 执行记录结构异常时返回 409；流开始后发生异常时，实时流和历史流都发送 `end`（`reason=error`）后关闭连接。
- 支持 chat 类 Agent 的异步轮询版本和支持 replay 的跨进程消息处理器（RabbitMQ / Redis）。
  flow、同步版本的执行中展示和 InMemory 跨进程读取暂不支持。

## 配置

| Django setting | 默认值 | 用途 |
| --- | --- | --- |
| `ANSWER_STREAM_OUTPUT_KEY` | `output` | 对应的插件输出字段 |
| `ANSWER_STREAM_MAX_SECONDS` | `1800` | 单连接最长时长（秒） |
| `ANSWER_STREAM_EVENT_TYPES` | 正文和思考过程事件 | 允许转发的 AG-UI 事件集合 |

实时回答和历史思考过程使用同一事件白名单，历史内容转换后逐条过滤。

接口与 BPF schedule 接口一样不要求浏览器登录，调用者通过随机 `trace_id` 定位执行。
SOPS 在代理回答流前须校验任务查看权限；插件入口访问控制、代理超时和并发容量应随部署确认。

## 插件升级与验收

1. 安装包含本功能的 `aidev-bkplugin` 发行版本，并重新部署。
2. 若插件曾私有实现 `bk_plugin.answer_stream`，删除私有路由及模块，避免旧路由优先命中。
3. 请求不存在的 trace_id，应返回 404 JSON；POST 应返回 405。
4. 执行异步 chat 节点，确认思考过程与正文逐段到达；多页面观看不影响原执行。
5. 执行结束后刷新页面，确认本轮思考过程仍可读取，正式正文与原节点输出一致。

新模板的 `output` 声明为 `contentMediaType="text/markdown"`。模板依赖版本应在公共包
正式发版时同步更新，不应将未发布的版本号写入初始化模板。

## 测试

在 `src/plugins/aidev_bkplugin` 下运行：

```bash
uv run --no-sync pytest tests/services/test_answer_stream.py tests/views/test_answer_stream_view.py
```

只读回放、轮次隔离、历史转换及 HTTP 行为由单元测试覆盖；正式验收还应验证真实模型、
真实 IAM、代理和部署环境的连接容量。回退公共包版本后，SOPS 对不支持的插件保持原显示方式。
