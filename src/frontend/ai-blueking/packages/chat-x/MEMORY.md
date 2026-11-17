# chat-x MEMORY

## 设计约定 Changelog

### 2026-11-17 · InfoMessage 分叉点样式

- **场景**：分支会话「从其他会话中继续」分隔线
- **做法**：
  - 文案默认 `$color-primary`（`#3a84ff`），hover 加深为 `#1768ef`（与输入区快捷入口交互蓝一致）
  - 两侧虚线改为 `linear-gradient` 自定义：4px 实段 + 4px 空隙，比浏览器默认 `border-style: dashed` 更疏
- **为什么**：设计走查反馈虚线偏密；文案需明确 hover 反馈
- **反例**：不要用默认 `dashed` 指望跨浏览器密度一致；不要把 hover 色改成与默认相同的 `#3a84ff`

### 2026-11-17 · ModelSelector 触发器箭头方向

- **场景**：输入框模型选择器 `.ai-model-selector-trigger-arrow`
- **做法**：`ArrowLeftIcon` 默认 `rotate(-90deg)` 朝下；`.is-expanded` 时 `rotate(90deg)` 朝上
- **为什么**：下拉未开时应朝下示意可展开，打开后朝上
- **反例**：不要把默认态设为朝上

### 2026-11-17 · 提问吸附态阴影

- **场景**：真正贴顶吸附中的提问气泡（Figma `1945:13976`）
- **做法**：
  - 可吸附：`.is-sticky`（`position: sticky` + 白底）
  - 正在吸附：滚动几何判定贴顶后加 `.is-stuck`
  - 阴影仅 `.is-sticky.is-stuck .ai-user-message-content`：`box-shadow: 0 2px 6px 0 #c6d0e0`
- **为什么**：正常流式位置不要投影；只有吸顶时气泡才需要分层阴影
- **反例**：不要在仅有 `.is-sticky` 时就加阴影；不要把投影加到整组吸附条
