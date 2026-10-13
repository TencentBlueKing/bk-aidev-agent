<template>
  <div class="atomic-assembly-demo">
    <div class="atomic-assembly-demo__chat">
      <MessageContainer
        v-model:selected-user-messages="selectedUserMessages"
        :messages="messages"
        :message-status="messageStatus"
        :message-tools-status="messageToolsStatus"
        :enable-selection="shareSelectionMode"
        :on-agent-action="handleAgentAction"
        :on-agent-feedback="handleAgentFeedback"
        :on-user-action="handleUserAction"
        @stop-streaming="handleStop"
      />
      <div v-if="shareSelectionMode" class="atomic-assembly-demo__selection-bar" role="status">
        <span
          >多选模式：勾选各轮用户消息（助手轮会联动高亮）。业务侧用 <code>v-model:selected-user-messages</code> 取选中项，再调
          <code>message.shareMessages(sessionCode, selectedUserMessages)</code>（网关 <code>POST share/</code>）。</span
        >
        <button type="button" class="atomic-assembly-demo__selection-exit" @click="exitShareSelection">退出多选</button>
      </div>
      <ChatInput
        ref="chatInputRef"
        v-model="userInput"
        v-model:cite="citeContent"
        :message-status="inputMessageStatus"
        placeholder="输入后发送，查看 AG-UI 流式渲染…"
        :support-upload="false"
        :on-send-message="handleSend"
        :on-stop-sending="handleStop"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"
  import { Message as BkMessage } from "bkui-vue"
  import { ChatInput, MessageContainer, MessageRole, MessageStatus, MessageToolsStatus } from "@blueking/chat-x"
  import { AGUIProtocol, useChatHelper } from "@blueking/chat-helper"
  import type { TagSchema } from "@blueking/chat-x"
  import type { UserMessage, Message, IToolBtn } from "@blueking/chat-x"
  import type { IMessage } from "@blueking/chat-helper"

  /** 关键动作的文字记录，供外层展示时间线（可删除） */
  const emit = defineEmits<{ trace: [text: string] }>()

  /** 会话标识，对应后端的 session code */
  const DEMO_SESSION_CODE = "atomic-stream-demo"

  const API_PREFIX = import.meta.env.BASE_URL + "mock-agui/api/"

  interface MessageLike {
    id?: number | string
    role: string
  }

  /** 查找指定消息前最近的用户消息（用于重新生成、删除等操作） */
  function findLastUserMessageBefore<T extends MessageLike>(list: T[], targetMessage: T): T | null {
    let last: T | null = null
    for (const m of list) {
      if (m.role === "user" && m.id !== undefined) {
        last = m
      }
      if (m === targetMessage) {
        break
      }
    }
    return last
  }

  function findLastUserMessageIdBefore(list: MessageLike[], targetMessage: MessageLike): number | undefined {
    const user = findLastUserMessageBefore(list, targetMessage)
    if (user?.id === undefined) return undefined
    return typeof user.id === "number" ? user.id : Number(user.id)
  }

  /** 请求失败时的错误提示 */
  function apiFailMessage(err: unknown, verb: string): string {
    const e = err as { response?: { status?: number }; message?: string }
    const msg = typeof e.message === "string" ? e.message : ""
    return `${verb}失败${msg ? `：${msg}` : "，详见控制台"}`
  }

  const userInput = ref("")
  const citeContent = ref("")
  const chatInputRef = ref<{ focus?: () => void } | null>(null)

  /** 分享模式：进入多选，用户勾选消息后调用分享接口 */
  const shareSelectionMode = ref(false)
  const selectedUserMessages = ref<Message[]>([])

  const exitShareSelection = () => {
    shareSelectionMode.value = false
    selectedUserMessages.value = []
  }

  const protocol = new AGUIProtocol({
    onError: (err) => {
      console.error("[AtomicAssemblyDemo] protocol error", err)
    },
  })

  const chatHelper = useChatHelper({
    requestData: {
      urlPrefix: typeof window !== "undefined" ? `${window.location.origin}${API_PREFIX}` : API_PREFIX,
    },
    protocol,
  })

  const { agent, message, session } = chatHelper

  const messages = computed(() => message.list.value as Message[])

  const messageStatus = computed(() => (agent.isChatting.value ? MessageStatus.Streaming : MessageStatus.Complete))

  const inputMessageStatus = computed(() => (agent.isChatting.value ? MessageStatus.Streaming : MessageStatus.Complete))

  const messageToolsStatus = computed<MessageToolsStatus | undefined>(() => (agent.isChatting.value ? MessageToolsStatus.Disabled : undefined))

  watch(agent.isChatting, (chatting) => emit("trace", chatting ? "流式开始（agent.isChatting = true）" : "流式结束"))

  const focusInput = () => {
    chatInputRef.value?.focus?.()
  }

  const handleSend = async (content: UserMessage["content"], _doc: TagSchema) => {
    const text = typeof content === "string" ? content : String(content ?? "")
    if (!text.trim()) return
    userInput.value = ""
    const cite = citeContent.value.trim()
    citeContent.value = ""
    emit("trace", `agent.chat(${JSON.stringify(text.slice(0, 20))}${cite ? ", { extra: { cite } }" : ""})`)
    await agent.chat(text, DEMO_SESSION_CODE, undefined, undefined, cite ? { extra: { cite } } : undefined)
  }

  const handleStop = async () => {
    emit("trace", "agent.abortChat()")
    agent.abortChat()
  }

  const handleDeleteAiGroup = async (aiMessages: Message[]) => {
    const list = message.list.value as Message[]
    if (!aiMessages.length) return
    const userMsg = findLastUserMessageBefore(list, aiMessages[0])
    if (!userMsg) {
      BkMessage({ theme: "warning", message: "未找到本轮对应的用户消息" })
      return
    }
    await message.deleteMessages([userMsg, ...aiMessages] as IMessage[])
  }

  const handleDeleteUserRound = async (userMessage: Message) => {
    const list = message.list.value as Message[]
    const idx = list.findIndex((m) => m === userMessage)
    if (idx === -1) return
    const tail: Message[] = [userMessage]
    for (let i = idx + 1; i < list.length; i++) {
      if (list[i].role === MessageRole.User) break
      tail.push(list[i])
    }
    await message.deleteMessages(tail as IMessage[])
  }

  const handleAgentAction = async (tool: IToolBtn, aiGroup: Message[]): Promise<string[] | void> => {
    const list = message.list.value as Message[]
    emit("trace", `onAgentAction：${tool.id}`)

    if (tool.id === "cite") {
      const text = aiGroup
        .filter((m) => m.role !== MessageRole.Reasoning)
        .map((m) => (typeof m.content === "string" ? m.content : JSON.stringify(m.content ?? "")))
        .join("\n")
      citeContent.value = text
      focusInput()
      return
    }

    if (tool.id === "rebuild") {
      agent.abortChat()
      const userMsg = findLastUserMessageBefore(list, aiGroup[0])
      if (!userMsg?.id) {
        BkMessage({ theme: "warning", message: "无法重新生成：缺少用户消息 id" })
        return
      }
      try {
        await agent.resendMessage(String(userMsg.id), DEMO_SESSION_CODE)
      } catch (e) {
        console.error(e)
        BkMessage({ theme: "error", message: apiFailMessage(e, "重新生成") })
      }
      return
    }

    if (tool.id === "delete") {
      try {
        await handleDeleteAiGroup(aiGroup)
      } catch (e) {
        console.error(e)
        BkMessage({ theme: "error", message: apiFailMessage(e, "删除") })
      }
      return
    }

    if (tool.id === "share") {
      shareSelectionMode.value = true
      selectedUserMessages.value = []
      BkMessage({
        theme: "primary",
        message: "已进入分享多选模式，请勾选对话轮次；完成后点「退出多选」。详见本页文档。",
      })
      return
    }

    if (tool.id === "like" || tool.id === "unlike") {
      const rate = tool.id === "like" ? 5 : 0
      try {
        const reasons = await session.getSessionFeedbackReasons(rate)
        return reasons ?? []
      } catch (e) {
        console.error(e)
        return []
      }
    }
  }

  const handleAgentFeedback = async (tool: IToolBtn, aiGroup: Message[], reasonList: string[], otherReason: string) => {
    const list = message.list.value as Message[]
    const userMessageId = findLastUserMessageIdBefore(list, aiGroup[0])
    if (userMessageId === undefined) {
      BkMessage({ theme: "warning", message: "无法提交反馈：未找到用户消息" })
      return
    }
    const rate = tool.id === "like" ? 5 : 0
    emit("trace", `session.postSessionFeedback({ rate: ${rate} })`)
    try {
      await session.postSessionFeedback({
        sessionCode: DEMO_SESSION_CODE,
        sessionContentIds: [userMessageId],
        rate,
        labels: reasonList,
        comment: otherReason,
      })
      BkMessage({ theme: "success", message: "反馈已提交" })
    } catch (e) {
      console.error(e)
      BkMessage({ theme: "error", message: apiFailMessage(e, "反馈提交") })
    }
  }

  const handleUserAction = async (tool: IToolBtn, msg: Message): Promise<void> => {
    emit("trace", `onUserAction：${tool.id}`)
    if (tool.id === "delete") {
      try {
        await handleDeleteUserRound(msg)
      } catch (e) {
        console.error(e)
        BkMessage({ theme: "error", message: apiFailMessage(e, "删除") })
      }
      return
    }
    if (tool.id === "cite") {
      const text = typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content ?? "")
      citeContent.value = text
      focusInput()
    }
  }

  onMounted(() => {
    protocol.injectMessageModule(message)
  })

  onBeforeUnmount(() => {
    exitShareSelection()
    agent.abortChat()
    void agent.stopChat(DEMO_SESSION_CODE).catch(() => {})
  })
</script>

<style scoped>
  .atomic-assembly-demo__chat {
    display: flex;
    flex-direction: column;
    height: 480px;
    border: 1px solid var(--vp-c-divider);
    border-radius: 8px;
    overflow: hidden;
    background: var(--vp-c-bg);
  }
  .atomic-assembly-demo__chat :deep(.ai-message-container) {
    flex: 1;
    min-height: 0;
  }
  .atomic-assembly-demo__selection-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    font-size: 12px;
    line-height: 1.5;
    color: var(--vp-c-text-2);
    background: var(--vp-c-bg-soft);
    border-top: 1px solid var(--vp-c-divider);
    flex-shrink: 0;
  }
  .atomic-assembly-demo__selection-bar code {
    font-size: 11px;
  }
  .atomic-assembly-demo__selection-exit {
    margin-left: auto;
    padding: 4px 12px;
    font-size: 12px;
    border-radius: 6px;
    border: 1px solid var(--vp-c-divider);
    background: var(--vp-c-bg);
    color: var(--vp-c-text-1);
    cursor: pointer;
  }
  .atomic-assembly-demo__selection-exit:hover {
    border-color: var(--vp-c-brand-1);
    color: var(--vp-c-brand-1);
  }
  .atomic-assembly-demo__chat :deep(.chat-input-container) {
    border-top: 1px solid var(--vp-c-divider);
    flex-shrink: 0;
  }
</style>
