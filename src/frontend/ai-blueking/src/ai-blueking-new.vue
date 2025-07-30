<template>
  <teleport :to="teleportTo">
    <div class="ai-blueking-wrapper">
      <vue-draggable-resizable
        v-if="isShow"
        ref="resizeWrapper"
        :active="isShow"
        :draggable="props.draggable"
        :h="height"
        :max-width="maxWidth"
        :min-height="minHeight"
        :min-width="minWidth"
        :parent="true"
        :prevent-deactivation="true"
        :resizable="true"
        :w="width"
        :x="left"
        :y="top"
        class-name="ai-blueking-container-wrapper"
        drag-handle=".drag-handle"
        @dragging="handleDragging"
        @resizing="handleResizing"
      >
        <div class="ai-blueking-container">
          <LoadingOverlay :show="isLoadingSessionContents" />
          <!-- 顶部栏 -->
          <AiBluekingHeader
            v-if="!props.hideHeader"
            :title="props.title"
            :is-compression-height="isCompressionHeight"
            :draggable="props.draggable"
            :show-history-icon="props.showHistoryIcon"
            :show-new-chat-icon="props.showNewChatIcon"
            @close="handleClose"
            @toggle-compression="toggleCompression"
            @new-chat="handleNewChat"
          />
          <div class="content-wrapper">
            <!-- 主要内容区域 -->
            <div :class="`main-content ${!hasSessionContents ? 'greeting-layout' : 'chat-layout'}`">
              <motion.div
                v-if="!hasSessionContents"
                class="greeting-box"
                :transition="{
                  duration: 0.5,
                  ease: [0.33, 1, 0.68, 1],
                  type: 'tween',
                }"
                :animate="{ opacity: 1 }"
                :initial="{ opacity: 1 }"
              >
                <div class="greeting-title">
                  {{ props.helloText }}
                </div>
                <div class="greeting-anmition-wrapper">
                  <motion.div
                    class="greeting-text"
                    :transition="{
                      duration: .5,
                      ease: [0.25, 0.46, 0.45, 0.94],
                      delay: 0,
                    }"
                    :animate="{
                      opacity: 1,
                      y: 0
                    }"
                    :initial="{
                      opacity: 0,
                      y: -20
                    }"
                  >
                    <div
                      ref="greetingTextRef"
                      class="greeting-markdown"
                      v-html="renderedGreetingText"
                    ></div>
                  </motion.div>
                </div>
              </motion.div>
              <div ref="messageWrapper" :style="{ opacity: hasSessionContents ? 1 : 0 }" class="message-wrapper">
                <render-message
                  v-for="(message, index) in sessionContents"
                  :index="index"
                  :key="message.id"
                  :message="message"
                  @delete="handleDelete"
                  @regenerate="handleRegenerate"
                  @resend="handleResend"
                />
              </div>
              <motion.div
                :transition="{
                  duration: 0.5,
                  ease: [0.33, 1, 0.68, 1],
                  type: 'tween',
                  layoutId: 'chat-input',
                }"
                :class="`chat-input-container ${!hasSessionContents ? 'centered' : 'bottom'}`"
                :style="hasSessionContents ? undefined : inputContainerStyle"
                layout
              >
                <div v-if="currentSessionLoading || showScrollToBottom" class="bottom-tools-bar">
                  <BarButton v-if="currentSessionLoading" color="#EA3636" icon="bkaitingzhishengcheng" text="停止生成" @click="handleStop" />
                  <BarButton v-if="showScrollToBottom" color="#979BA5" icon="bkaijiantou" text="返回底部" @click="scrollMainToBottom" />
                </div>
                <ChatInputBox
                  ref="chatInputBoxRef"
                  v-model="inputMessage"
                  :loading="currentSessionLoading"
                  :prompts="promptList"
                  :shortcuts="shortcuts || []"
                  :disabled="props.disabledInput"
                  :placeholder="props.placeholder"
                  @height-change="handleInputHeightChange"
                  @send="handleSendMessage"
                  @shortcut-click="handleShortcutClick"
                  @stop="handleStop"
                />
              </motion.div>
            </div>
          </div>
        </div>
      </vue-draggable-resizable>
      <Nimbus
        v-if="!props.hideNimbus"
        v-model:is-panel-show="isShow"
        :default-minimize="defaultMinimize"
        :size="props.nimbusSize"
        v-model:is-minimize="isNimbusMinimize"
        @click="handleNimbusClick"
      />
      <RenderPopup :shortcuts="shortcuts || []" @click="isShow = true" @shortcut-click="handleShortcutClick" />
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { computed, provide, ref, nextTick, watch, defineExpose, Ref, onMounted, onBeforeUnmount } from "vue"
import VueDraggableResizable from "vue-draggable-resizable"
import type { IRequestOptions } from "./types"

import { useChat, useStyle, useClickProxy } from "@blueking/ai-ui-sdk/hooks"
import { ShortCut } from "@blueking/ai-ui-sdk/types"
import { SessionContentRole } from "@blueking/ai-ui-sdk/enums"
import { motion } from "motion-v"

import AiBluekingHeader from "./components/ai-header.vue"
import BarButton from "./components/bar-button.vue"
import ChatInputBox from "./components/chat-input-box.vue"
import renderMessage from "./components/render-message.vue"
import RenderPopup from "./components/render-popup.vue"
import LoadingOverlay from "./components/loading-overlay.vue"
import { POPUP_INJECTION_KEY } from "./composables/use-popup-props"
import { useResizableContainer } from "./composables/use-resizable-container"
import { useSelect } from "./composables/use-select-pop"
import { DEFAULT_SHORTCUTS, HIDE_ROLE_LIST } from "./config"
import { t } from "./lang"
import { scrollToBottom, escapeHtml, normalizeUrl } from "./utils"
import Nimbus from "./views/nimbus.vue"
import { provideSessionStore } from "./composables/use-session-store"
import { useMarkdown } from "./composables/use-markdown"

import "vue-draggable-resizable/style.css"

// 类型定义
interface Props {
  title?: string
  helloText?: string
  enablePopup?: boolean
  shortcuts?: ShortCut[]
  url?: string
  prompts?: string[]
  hideNimbus?: boolean
  requestOptions?: IRequestOptions
  defaultMinimize?: boolean
  teleportTo?: string
  draggable?: boolean
  defaultWidth?: number
  defaultHeight?: number
  defaultTop?: number
  defaultLeft?: number
  hideHeader?: boolean
  disabledInput?: boolean
  nimbusSize?: "small" | "normal" | "large"
  showHistoryIcon?: boolean
  showNewChatIcon?: boolean
  placeholder?: string
  miniPadding?: number
}

// Props 定义
const props = withDefaults(defineProps<Props>(), {
  title: '',
  helloText: t("你好，我是小鲸"),
  enablePopup: true,
  shortcuts: () => DEFAULT_SHORTCUTS,
  url: "",
  prompts: () => [],
  hideNimbus: false,
  requestOptions: () => ({}),
  defaultMinimize: false,
  teleportTo: "body",
  draggable: true,
  defaultWidth: undefined,
  defaultHeight: undefined,
  defaultTop: undefined,
  defaultLeft: undefined,
  hideHeader: false,
  disabledInput: false,
  nimbusSize: "normal",
  showHistoryIcon: true,
  showNewChatIcon: true,
  placeholder: t('输入 "/" 唤出 Prompt\n通过 Shift + Enter 进行换行输入'),
  miniPadding: 0,
})

// Emits 定义
const emit = defineEmits<{
  (e: "shortcut-click", shortcut: ShortCut): void
  (e: "close" | "show" | "stop" | "receive-start" | "receive-text" | "receive-end"): void
  (e: "send-message", message: string): void
  (e: "session-initialized", data: { openingRemark: string; predefinedQuestions: string[] }): void
}>()

// 提供 popup 注入
provide(POPUP_INJECTION_KEY, props.enablePopup)

// 状态管理
const resizeWrapper = ref<InstanceType<typeof VueDraggableResizable>>()
const chatInputBoxRef = ref<InstanceType<typeof ChatInputBox>>()
const isShow = ref(false)
const inputMessage = ref("")
const messageWrapper = ref<HTMLElement>()
const greetingTextRef = ref<HTMLElement>()
const showScrollToBottom = ref(false)
const isNimbusMinimize = ref(props.defaultMinimize)
let lastScrollTop = 0 // 上一次的滚动位置, 用于判断是否向下滑动
const isSessionInitialized = ref(false)
let initSessionPromise: Promise<void> | null = null // 用于避免重复初始化会话
const openingRemark = ref("") // 接口获取的开场白
const predefinedQuestions: Ref<string[]> = ref([]) // 接口获取的预设问题

// 提供会话存储实例
const sessionStore = provideSessionStore()

const greetingText = computed(() => openingRemark.value || t("输入你的问题，助你高效的完成工作"))

// 响应式的窗口高度
const windowHeight = ref(window.innerHeight)

// 动态计算 greeting 最大高度
const greetingMaxHeight = computed(() => windowHeight.value - 367) // 367 是其余组件占据空间

// 使用 markdown 渲染功能
const { renderMarkdown } = useMarkdown()

// 渲染后的问候语（支持 markdown）
const renderedGreetingText = computed(() => {
  return renderMarkdown(greetingText.value)
})

const promptList = computed(() => {
  return [...props.prompts, ...predefinedQuestions.value]
})

const hasSessionContents = computed(() => {
  return sessionContents.value.filter((item) => !HIDE_ROLE_LIST.includes(item.role)).length > 0
})

// 标准化的URL，自动匹配当前页面协议
const normalizedUrl = computed(() => {
  return normalizeUrl(props.url)
})

// 动态计算 greeting text 的高度，用于调整输入框位置
const greetingTextHeight = ref(0)

// 监听 greeting text 内容变化，重新计算高度
const updateGreetingTextHeight = () => {
  nextTick(() => {
    if (greetingTextRef.value) {
      greetingTextHeight.value = greetingTextRef.value.offsetHeight
    }
  })
}

// 计算输入框的动态位置
const inputContainerStyle = computed(() => {
  if (!hasSessionContents.value) {
    // 当没有消息时，根据 greeting text 的高度动态调整位置
    const baseTop = 188 // 原始的 top 值
    const greetingHeight = greetingTextHeight.value

    // 如果 greeting text 超过了基础高度，需要向下调整输入框位置
    const additionalOffset = Math.min(greetingHeight - 22, greetingMaxHeight.value - 22) // 22 是单行高度
    const dynamicTop = baseTop + Math.max(0, additionalOffset)

    return {
      top: `${dynamicTop}px`
    }
  }
  return {}
})

// 使用可调整大小的容器
const { minWidth, minHeight, maxWidth, top, left, width, height, isCompressionHeight, handleDragging, handleResizing, toggleCompression } =
  useResizableContainer({
    maxWidthPercent: 80,
    initWidth: props.defaultWidth,
    defaultHeight: props.defaultHeight,
    defaultTop: props.defaultTop,
    defaultLeft: props.defaultLeft,
    miniPadding: props.miniPadding,
  })

const inputHeight = ref(68)

const handleInputHeightChange = (height: number) => {
  inputHeight.value = height
}

const contentMarginBottom = computed(() => {
  const toolsBarHeight = 40
  const offSetHeight = selectedText.value ? 100 : 70
  return inputHeight.value + toolsBarHeight + offSetHeight
})

const { selectedText, citeText, setCiteText } = useSelect(props.enablePopup)

const handleClose = () => {
  isShow.value = false
  emit("close")
}

const handleShow = () => {
  isShow.value = true
  emit("show")

  // 弹窗打开时，如果有 URL 且未初始化会话，则初始化会话
  if (normalizedUrl.value && !isSessionInitialized.value) {
    initSession()
  }

  updateGreetingTextHeight()
}

const handleNimbusClick = () => {
  handleShow()
}

// 初始化样式和点击代理
useStyle()
useClickProxy()

// 添加用户滚动跟踪变量
const userScrolling = ref(false)

// 重置用户滚动状态的函数
const resetUserScrolling = () => {
  userScrolling.value = false
}

// 处理用户滚动事件
const handleUserScroll = () => {
  if (!messageWrapper.value) return

  userScrolling.value = true

  const { scrollTop, scrollHeight, clientHeight } = messageWrapper.value
  const isNearBottom = scrollTop + clientHeight >= scrollHeight - 50

  // 更新返回底部按钮的显示状态
  showScrollToBottom.value = !isNearBottom && scrollHeight > clientHeight

  // 只有向下滑动且接近底部时才重置滚动状态
  if (isNearBottom && scrollTop > lastScrollTop) {
    resetUserScrolling()
  }
  lastScrollTop = scrollTop
}

// 监听滚动容器
watch(messageWrapper, (el, oldEl) => {
  // 移除旧元素的事件监听器
  if (oldEl) {
    oldEl.removeEventListener("scroll", handleUserScroll)
    oldEl.removeEventListener("mermaid-rendered", handleMermaidRendered)
  }

  if (el) {
    el.addEventListener("scroll", handleUserScroll)
    // 监听 mermaid 渲染完成事件
    el.addEventListener("mermaid-rendered", handleMermaidRendered)
  }
})

// 处理 mermaid 渲染完成事件
const handleMermaidRendered = () => {
  // 在 mermaid 渲染完成后，如果用户没有在滚动，则自动滚动到底部
  nextTick(() => {
    scrollToBottomIfNeeded()
  })
}

// 使用聊天功能
const {
  currentSession,
  sessionContents,
  isLoadingSessionContents,
  plusSessionContent,
  plusSessionApi,
  chat,
  stopChat,
  setCurrentSession,
  setCurrentSessionChain,
  currentSessionLoading,
  reGenerateChat,
  reSendChat,
  deleteChat,
  updateRequestOptions,
  getAgentInfoApi,
  getSessionsApi,
  getSessionContentsApi,
  modifySessionApi,
  deleteSessionApi,
  setSessionContents,
  handleCompleteRole,
} = useChat({
  handleStart: () => {
    scrollToBottomIfNeeded()
    emit("receive-start")
  },
  handleText: () => {
    scrollToBottomIfNeeded()
    emit("receive-text")
  },
  handleEnd: () => {
    scrollToBottomIfNeeded()
    emit("receive-end")
  },
  requestOptions: {
    url: normalizedUrl.value,
    ...props.requestOptions,
  },
})

// 注册 SDK 的 setCurrentSession 方法
sessionStore.registerSdkMethods({
  setCurrentSession,
  setCurrentSessionChain,
  setSessionContents,
  modifySessionApi,
  deleteSessionApi,
  getSessionContentsApi,
  getSessionsApi,
  getAgentInfoApi,
  plusSessionApi,
  handleCompleteRole,
})

// 封装会话初始化逻辑
const initSession = async () => {
  // 如果已经有正在进行的初始化，则等待其完成
  if (initSessionPromise) {
    await initSessionPromise
    return
  }

  // 如果已经初始化完成，则直接返回
  if (isSessionInitialized.value && !initSessionPromise) {
    return
  }

  // 创建新的初始化Promise
  initSessionPromise = (async () => {
    try {
      const { conversationSettings } = await sessionStore.initSession()
      openingRemark.value = conversationSettings?.openingRemark || ""
      predefinedQuestions.value = conversationSettings?.predefinedQuestions || []
      isSessionInitialized.value = true
      
      // 派发初始化完成事件
      emit("session-initialized", {
        openingRemark: openingRemark.value,
        predefinedQuestions: predefinedQuestions.value,
      })
    } finally {
      // 无论成功还是失败，都要清理Promise
      initSessionPromise = null
      // 更新 greeting text 的高度
      updateGreetingTextHeight()
    }
  })()

  await initSessionPromise
}

// 监听 url 变化
watch(
  () => normalizedUrl.value,
  (newUrl, oldUrl) => {
    if (newUrl !== oldUrl && newUrl) {
      // 更新请求选项
      updateRequestOptions({
        url: newUrl,
        ...props.requestOptions,
      })
      // URL 变化时重置初始化状态并重新初始化会话
      isSessionInitialized.value = false
      initSessionPromise = null
      initSession()
    }
  }
)

// 监听 requestOptions 变化
watch(
  () => props.requestOptions,
  (newOptions) => {
    updateRequestOptions({
      url: normalizedUrl.value,
      ...newOptions,
    })
  },
  { deep: true }
)

// 如果初始 URL 存在且弹窗默认显示，则立即初始化会话
if (normalizedUrl.value && !props.defaultMinimize) {
  initSession()
}

// 窗口 resize 事件处理器
const handleWindowResize = () => {
  windowHeight.value = window.innerHeight
}

// 生命周期钩子 - 添加和移除窗口 resize 监听器
onMounted(() => {
  window.addEventListener('resize', handleWindowResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleWindowResize)
})

const scrollMainToBottom = () => {
  messageWrapper.value?.scrollTo({
    top: messageWrapper.value.scrollHeight,
    behavior: "smooth",
  })
}

// 滚动到底部的辅助函数
const scrollToBottomIfNeeded = () => {
  // 如果用户正在滚动查看历史消息，则不自动滚动
  if (userScrolling.value) return

  if (messageWrapper.value) {
    scrollToBottom(messageWrapper.value)
  }
}

// 事件处理
const handleSendMessage = async (message: string) => {
  if (!message.trim()) return

  // 如果会话未初始化，先初始化
  if (!isSessionInitialized.value && normalizedUrl.value) {
    initSession()
  }

  // 发送新消息时重置用户滚动状态
  resetUserScrolling()

  // HTML转义功能 防止被当做 HTML 标签渲染
  const escapedMessage = escapeHtml(message)

  await plusSessionContent(currentSession.value?.sessionCode, {
    role: SessionContentRole.User,
    content: escapedMessage,
    sessionCode: currentSession.value?.sessionCode,
    property: {
      extra: {
        cite: citeText.value,
        ...(typeof props.requestOptions?.context === "function" ? props.requestOptions?.context() : props.requestOptions?.context),
      },
    },
  })

  chat({
    sessionCode: currentSession.value?.sessionCode,
    ...props.requestOptions,
  })

  emit("send-message", escapedMessage)

  // 清空输入
  inputMessage.value = ""
  setCiteText("")
}

const handleRegenerate = (index: number) => {
  const sessionContent = sessionContents.value[index]
  if (sessionContent) {
    reGenerateChat(sessionContent.sessionCode, sessionContent, index)
  }
}

const handleResend = (index: number, { message, cite }: { message: string; cite: string }) => {
  const sessionContent = sessionContents.value[index]
  if (sessionContent) {
    sessionContent.content = escapeHtml(message)
    if (sessionContent?.property?.extra?.cite) {
      sessionContent.property.extra.cite = cite
    }
    reSendChat(sessionContent.sessionCode, sessionContent, index)
  }
}

const handleStop = () => {
  if (currentSession?.value?.sessionCode) {
    stopChat(currentSession.value.sessionCode)
    emit("stop")
  }
}

const handleShortcutClick = async (shortcut: ShortCut) => {
  !isShow.value && handleShow()

  // 如果会话未初始化，先初始化
  if (!isSessionInitialized.value && normalizedUrl.value) {
    initSession()
  }

  await plusSessionContent(currentSession.value?.sessionCode, {
    role: SessionContentRole.User,
    content: shortcut.label,
    sessionCode: currentSession.value?.sessionCode,
    property: {
      extra: {
        cite: selectedText.value || inputMessage.value,
        shortcut,
      },
    },
  })

  chat({
    sessionCode: currentSession.value?.sessionCode,
    ...props.requestOptions,
  })

  emit("shortcut-click", shortcut)
}

const handleDelete = (index: number) => {
  deleteChat(index, currentSession.value?.sessionCode)
}

// 监听消息列表变化，自动滚动到底部
watch(
  sessionContents,
  () => {
    nextTick(scrollToBottomIfNeeded)
  },
  { deep: true }
)

// 监听面板显示状态，面板打开时自动聚焦输入框
watch(
  () => isShow.value,
  (newValue) => {
    if (newValue) {
      // 面板打开时，延迟一下让 DOM 渲染完成后再聚焦
      nextTick(() => {
        chatInputBoxRef.value?.focus()
      })
    }
  }
)

// 处理新增聊天
const handleNewChat = async () => {
  // 终止当前会话
  stopChat(currentSession.value?.sessionCode)
  // 重置输入框
  inputMessage.value = ""
  setCiteText("")
  // 重置会话内容
  setSessionContents([])
}

defineExpose({
  sessionContents,
  handleShow,
  handleClose,
  handleStop,
  handleSendMessage,
  handleShortcutClick,
  handleDelete,
  handleRegenerate,
  handleResend,
  updateRequestOptions,
  currentSessionLoading,
  isLoadingSessionContents,
  updateGreetingTextHeight,
  setCurrentSession,
  focusInput: () => {
    chatInputBoxRef.value?.focus()
  },
})
</script>

<style lang="scss" scoped>
@import "./styles/mixins.scss";
@import "./styles/markdown.scss";

.ai-blueking-wrapper {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 10000;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
}

.ai-blueking-container-wrapper {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  pointer-events: auto;
  background: #ffffff;
  border-radius: 2px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.2);

  :deep(.handle) {
    background: transparent;
    border: none;

    &.handle-ml,
    &.handle-mr {
      top: 0;
      height: 100%;
      margin-top: 0;
      cursor: ew-resize;
    }

    &.handle-tm,
    &.handle-bm {
      left: 0;
      width: 100%;
      margin-left: 0;
      cursor: ns-resize;
    }

    &.handle-tl,
    &.handle-br {
      cursor: nwse-resize;
    }

    &.handle-tr {
      top: -5px;
      right: -5px;
    }

    &.handle-tl {
      top: -5px;
      left: -5px;
    }

    &.handle-bl {
      bottom: -5px;
      left: -5px;
    }

    &.handle-br {
      right: -5px;
      bottom: -5px;
    }

    &.handle-tr,
    &.handle-bl {
      cursor: nesw-resize;
    }
  }
}

.ai-blueking-container {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
}

.content-wrapper {
  position: relative;
  display: flex;
  flex: 1;
  overflow: hidden;
  justify-content: center;
}

.main-content {
  position: relative;
  max-width: 1000px;
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  padding: 16px;
  overflow-y: auto;

  .bottom-tools-bar {
    display: flex;
    gap: 8px;
    align-items: center;
    justify-content: center;
    margin-bottom: 16px;
  }

  .message-wrapper {
    position: relative;
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: 32px;
    min-height: 0;
    padding: 0 16px;
    margin-right: -16px;
    margin-bottom: v-bind('contentMarginBottom + "px"');
    margin-left: -16px;
    overflow-y: auto;
    transition: opacity 0.5s ease;

    @include custom-scrollbar;
  }

  &.chat-layout {
    gap: 0;
  }

  .greeting-box {
    position: absolute;
    top: 92px;
    left: 50%;
    z-index: 2;
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: center;
    width: 100%;
    transform: translateX(-50%);

    .greeting-anmition-wrapper {
      overflow: hidden;
    }

    .greeting-title {
      margin-bottom: 22px;
      font-size: 21px;
      font-weight: 700;
      line-height: 24px;
      color: #313238;
    }

    .greeting-text {
      width: 100%;
      max-width: 600px;
      max-height: v-bind('greetingMaxHeight + "px"');
      font-size: 14px;
      line-height: 22px;
      color: #4d4f56;
      transform-origin: center top;
      overflow-y: auto; // 添加垂直滚动
      padding: 8px 0;

      // greeting-markdown 样式现在从公共样式文件导入
    }
  }

  .chat-input-container {
    z-index: 3;
    width: 100%;
    outline: none;
    transform-origin: center;
    will-change: transform;

    &.centered {
      position: absolute;
      top: 188px;
      left: 50%;
      width: calc(100% - 32px);

      /* stylelint-disable-next-line declaration-no-important */
      transform: translate(-50%, 0) !important;
    }

    &.bottom {
      position: absolute;
      right: 16px;
      bottom: 16px;
      left: 16px;
      width: calc(100% - 32px);
    }
  }
}

.action-icon {
  cursor: pointer;
  opacity: 0.7;

  &:hover {
    opacity: 1;
  }
}

// 添加 Nimbus 相关样式
:deep(.vdr) {
  background: transparent;
  border: none;
}
</style>
