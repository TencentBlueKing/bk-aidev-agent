# chat_completion stream_mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `@blueking/chat-helper` 调用 `chat_completion/` 时显式传 `execute_kwargs.stream_mode`（`start` | `attach`），区分新开执行与接管续流，对齐后端 #779。

**Architecture:** 单一出口 `useAgent.streamRequest`；默认 `start`；仅 `resumeStreamingChat` 与静默重连传 `attach`。`isReconnect` 只管前端重连状态机，不推导后端语义。落点分支：`feat/artifacts_modelSelect`。

**Tech Stack:** Vue 3 + TypeScript（chat-helper）；后端 `ExecuteKwargs.stream_mode` / `attach_only`。

---

## File map

| File | Responsibility |
|------|----------------|
| `packages/chat-helper/src/agent/type.ts` | 导出 `StreamMode` |
| `packages/chat-helper/src/agent/use-agent.ts` | `streamRequest` 入参 + 请求体 + 续流入口 |
| `packages/ai-blueking/skills/ai-blueking-dev/references/chat-helper-api.md` | API 文档 |
| `packages/ai-blueking/skills/ai-blueking-dev/SKILL.md` | bump version |

---

### Task 1: 类型 `StreamMode`

**Files:**
- Modify: `src/frontend/ai-blueking/packages/chat-helper/src/agent/type.ts`
- Already exported via `agent/index.ts` (`export * from './type'`)

- [x] **Step 1: 在 `type.ts` 末尾增加类型**

```ts
/**
 * chat_completion execute_kwargs.stream_mode
 * - start: 可创建生产者，开新一轮执行（默认）
 * - attach: 仅接管/回放已有流，不允许新建生产者
 */
export type StreamMode = 'start' | 'attach';
```

---

### Task 2: `streamRequest` 传 `stream_mode` + 续流入口

**Files:**
- Modify: `src/frontend/ai-blueking/packages/chat-helper/src/agent/use-agent.ts`

- [x] **Step 1: import `StreamMode`，扩展 `activeStreamContext` 存 `streamMode`**
- [x] **Step 2: `streamRequest` 增加 `streamMode = 'start'`，写入 `execute_kwargs.stream_mode`**
- [x] **Step 3: `attemptSilentReconnect` 传 `streamMode: 'attach'`**
- [x] **Step 4: `resumeStreamingChat` 传 `streamMode: 'attach'`**
- [x] **Step 5: 其余 call site（chat / resend / HITL / userOperation）不传，走默认 `start`**

请求体形状：

```ts
execute_kwargs: {
  stream: true,
  stream_mode: streamMode,
  persist_input: !!input,
  last_message_id: lastMessageId,
  resume,
}
```

---

### Task 3: attach 失败不误重连

**Files:**
- Modify: `use-agent.ts`

- [x] **Step 1: 增加 `isStreamAttachUnavailableError(error)`**（匹配 `No active or replayable stream`）
- [x] **Step 2: `onError` / silent reconnect 路径：若当前 `activeStreamContext.streamMode === 'attach'` 且命中该错误 → 不重连；session 非 Running 则 `finishSuccessfully`，否则安静结束 `isChatting=false`**

---

### Task 4: Skill 文档

**Files:**
- Modify: `packages/ai-blueking/skills/ai-blueking-dev/references/chat-helper-api.md`
- Modify: `packages/ai-blueking/skills/ai-blueking-dev/SKILL.md`（`metadata.version` 5.12 → 5.13）

- [x] **Step 1: `streamRequest` 文档增加 `streamMode` 与请求体 `stream_mode`**
- [x] **Step 2: 注明 `resumeStreamingChat` / 静默重连使用 `attach`**
- [x] **Step 3: bump skill version**

---

### Task 5: 验证

- [x] **Step 1: `pnpm exec vue-tsc --noEmit` in chat-helper（已通过）**
- [ ] **Step 2: 自测矩阵（有后端 stream_mode 时）**

| 场景 | 期望 |
|------|------|
| 正常发消息 | `stream_mode=start` |
| 静默重连 | `attach` |
| chooseSession Running | `attach` |
| HITL resume | `start` + `resume` |
| resend | `start` |

**Note:** chat-helper 包内无 vitest；不为此单独搭测试脚手架。验证以类型检查 + 手工/联调为准。

---

## Out of scope

- 删除 `last_message_id`
- 把 `streamMode` 暴露到 ChatBot / BusinessManager
- 改 FetchClient
- 裸 cherry-pick `046ba646`（会丢当前分支的 `model` 等改动）
