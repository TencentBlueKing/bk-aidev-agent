<template>
  <div class="share-container" role="main" aria-label="AI 分享内容">
    <div class="ai-share-container">
      <div class="ai-share-header">
        <div class="ai-share-header-left">
          <img src="@/assets/svg/ai-logo.svg" alt="AI助手logo" />
          <h1 class="ai-share-header-title">{{ title }}</h1>
        </div>
        <div class="ai-share-header-right">
          <span v-if="agentName" class="ai-share-header-text">{{ `分享于 "${agentName}"` }}</span>
          <span v-if="agentName" class="ai-share-header-divider" aria-hidden="true"></span>
          <span
            v-bk-tooltips="{
              content: asideCollapsed ? '展开侧栏' : '收起侧栏',
              delay: [300, 0],
            }"
            class="aside-toggle"
            @click="asideCollapsed = !asideCollapsed"
          >
            <AsideToggleIcon />
          </span>
        </div>
      </div>
      <div
        class="share-content"
        v-bkloading="{
          loading,
          theme: 'primary',
          mode: 'spin',
        }"
      >
        <!-- 错误状态 -->
        <div v-if="hasError" class="error-state" role="alert" aria-live="polite">
          <bk-exception class="exception-wrap-item exception-part" :description="errorMessage" scene="part" type="empty">
            <template #default>
              <bk-button v-if="canRetry" theme="primary" @click="handleRetry" class="retry-button"> 重新加载 </bk-button>
            </template>
          </bk-exception>
        </div>
        <!-- 数据展示 -->
        <div v-else-if="hasValidData" class="share-data">
          <ChatContainer
            v-model:aside-collapsed="asideCollapsed"
            :messages="messages"
            :message-status="MessageStatus.Complete"
            message-tools-status="hidden"
            placement="right"
            render-mode="share"
            :on-artifact-click="handleArtifactClick"
            :resize-props="shareResizeProps"
          />
        </div>
      </div>
    </div>
    <div class="share-tip">内容由 AI 大模型生成，请仔细甄别</div>
  </div>
</template>

<script setup lang="ts">
  import { cloneVNode, computed, defineComponent, onBeforeMount, ref } from "vue"
  import { useRoute } from "vue-router"
  import { Message, Exception as BkException, Button as BkButton, bkTooltips as vBkTooltips } from "bkui-vue"
  import { ChatContainer, CollapsedAsideIcon, MessageStatus, type AIFileInfo, type OnArtifactClick } from "@blueking/chat-x"
  import "@blueking/chat-x/dist/index.css"
  import { transferMessageApi2Message, type IMessageApi, type IMessage } from "@blueking/chat-helper"

  // TypeScript 接口定义
  interface ShareData {
    session_contents: IMessageApi[]
    session_name: string
    agent_name: string
    /** 原会话编码；缺省时从消息 session_code 兜底 */
    session_code?: string
  }

  interface ApiResponse {
    result?: boolean
    code?: string
    message?: string
    trace_id?: string
    data: ShareData
  }

  interface ArtifactUrlApiData {
    download_url?: string
    preview_url?: string
  }

  interface ErrorMessage {
    message: string
    userMessage: string
    canRetry: boolean
  }

  // 错误消息映射表
  const ERROR_MESSAGES: Record<number, ErrorMessage> = {
    404: {
      message: "分享内容不存在",
      userMessage: "分享内容不存在，请检查链接是否正确",
      canRetry: false,
    },
    403: {
      message: "无权访问此分享内容",
      userMessage: "您没有权限访问此分享内容",
      canRetry: true,
    },
    401: {
      message: "未授权访问",
      userMessage: "请先登录后再访问",
      canRetry: true,
    },
    500: {
      message: "服务器内部错误",
      userMessage: "服务器暂时无法处理请求，请稍后重试",
      canRetry: true,
    },
  }

  const DEFAULT_ERROR: ErrorMessage = {
    message: "网络请求失败",
    userMessage: "网络请求失败，请稍后重试",
    canRetry: true,
  }

  // 组件状态
  const title = ref<string>("")
  const agentName = ref<string>("")
  const url = ref<string>(window.BK_API_PREFIX || "")
  const loading = ref<boolean>(false)
  const messages = ref<IMessage[]>([])
  const error = ref<string | null>(null)
  const currentShareCode = ref<string>("")
  /** 产物取链用的原会话编码 */
  const sessionCode = ref<string>("")

  const route = useRoute()

  /** CollapsedAsideIcon 是预创建 VNode，不能当 SFC 用，需 cloneVNode 包一层 */
  const AsideToggleIcon = defineComponent({
    name: "AsideToggleIcon",
    setup() {
      return () => cloneVNode(CollapsedAsideIcon)
    },
  })

  /** 嵌入式 ChatContainer 不自带侧栏开关，由分享页 Header 受控 */
  const asideCollapsed = ref(true)

  /**
   * 分享页侧栏（文件产物 / 执行情况）宽度：对齐工作台 ChatBot 默认 560，
   * 略加大 initialDivide，避免产物预览区被文件列表挤窄。
   */
  const shareResizeProps = {
    initialDivide: 640,
    min: 480,
    max: 800,
  }

  // 计算属性
  const hasValidData = computed(() => messages.value.length > 0)
  const hasError = computed(() => error.value !== null)
  const errorMessage = computed(() => error.value || "")
  const canRetry = computed(() => {
    if (!currentShareCode.value || !hasError.value) return false
    const status = getErrorStatus(error.value)
    return ERROR_MESSAGES[status]?.canRetry ?? DEFAULT_ERROR.canRetry
  })

  /**
   * 点击文件产物：签发临时 download_url / preview_url，供侧栏 FileArtifactPanel 渲染。
   * 未传此回调时侧栏可打开，但预览区会一直为空。
   */
  const handleArtifactClick: OnArtifactClick = async (file: AIFileInfo) => {
    const code = sessionCode.value || messages.value.find((item) => item.sessionCode)?.sessionCode || ""
    if (!code) {
      throw new Error("[Share] Cannot resolve artifact URL: no session code")
    }

    const params = new URLSearchParams({ path: file.outputId })
    const response = await fetch(`${url.value}/session/${encodeURIComponent(code)}/pv_files/download_url/?${params}`, {
      method: "GET",
      credentials: "include",
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const result = (await response.json()) as {
      data?: ArtifactUrlApiData
      download_url?: string
      preview_url?: string
    }
    const data = result.data ?? result

    return {
      download_url: data.download_url,
      preview_url: data.preview_url,
    }
  }

  // 获取错误状态码
  const getErrorStatus = (errorMessage: string | null): number => {
    if (!errorMessage) return 0
    const match = errorMessage.match(/HTTP (\d+)/)
    return match ? parseInt(match[1]) : 0
  }

  // 错误处理函数
  const handleError = (status: number, statusText: string): void => {
    const errorInfo = ERROR_MESSAGES[status] || DEFAULT_ERROR
    error.value = `${errorInfo.message}: ${status} ${statusText}`
    Message({
      theme: "error",
      message: errorInfo.userMessage,
      delay: 3000,
    })
  }

  // 异步请求数据
  const fetchShareData = async (shareCode: string): Promise<void> => {
    if (!shareCode?.trim()) {
      handleError(0, "分享码为空")
      return
    }

    loading.value = true
    error.value = null
    currentShareCode.value = shareCode.trim()

    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 30000) // 30秒超时

      const response = await fetch(`${url.value}/share/${shareCode.trim()}`, {
        method: "GET",
        credentials: "include",
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result: ApiResponse = await response.json()

      // 数据验证
      if (!result?.data?.session_contents) {
        throw new Error("Invalid response data structure")
      }

      messages.value = (result.data.session_contents as unknown as IMessageApi[]).map(transferMessageApi2Message)
      title.value = result.data.session_name || "AI 对话分享"
      agentName.value = result.data.agent_name || ""
      sessionCode.value = result.data.session_code || messages.value.find((item) => item.sessionCode)?.sessionCode || ""
    } catch (err) {
      console.error("获取分享数据失败:", err)

      if (err instanceof Error) {
        if (err.name === "AbortError") {
          error.value = "请求超时，请稍后重试"
          Message({
            theme: "error",
            message: "请求超时，请稍后重试",
            delay: 3000,
          })
        } else {
          const statusMatch = err.message.match(/HTTP (\d+)/)
          if (statusMatch) {
            handleError(parseInt(statusMatch[1]), err.message)
          } else {
            error.value = DEFAULT_ERROR.message
            Message({
              theme: "error",
              message: DEFAULT_ERROR.userMessage,
              delay: 3000,
            })
          }
        }
      } else {
        error.value = DEFAULT_ERROR.message
        Message({
          theme: "error",
          message: DEFAULT_ERROR.userMessage,
          delay: 3000,
        })
      }
    } finally {
      loading.value = false
    }
  }

  // 重试处理
  const handleRetry = (): void => {
    if (currentShareCode.value) {
      fetchShareData(currentShareCode.value)
    }
  }

  // 生命周期钩子
  onBeforeMount(async () => {
    const shareCode = route.params.shareCode as string
    if (shareCode?.trim()) {
      await fetchShareData(shareCode.trim())
    } else {
      handleError(0, "分享码不存在")
    }
  })
</script>

<style lang="postcss" scoped>
  .share-container {
    width: 100%;
    min-height: 100vh;
    opacity: 0.89;
    background-image: linear-gradient(0deg, #c6cdeb 0%, #fdf7f6 20%, #ebf3f8 38%, #f8f8ff 71%, #bae6fd 100%);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 40px 20px;
    box-sizing: border-box;
    .ai-share-container {
      /* 必须用 height（不能只用 max-height）：ChatContainer 的 height:100% 依赖父级明确高度，
         否则会按内容撑开，侧栏产物预览再被 overflow 裁切。与 ai-blueking 宿主一致。 */
      width: min(1280px, 100%);
      height: calc(100vh - 120px);
      min-height: 300px;
      background: #ffffff;
      border-radius: 16px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      box-sizing: border-box;
      overflow: hidden;
      .ai-share-header {
        height: 57px;
        flex: 0 0 57px;
        width: 100%;
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        border-bottom: 1px solid #dddee6;
        .ai-share-header-left {
          display: flex;
          align-items: center;
          gap: 12px;
          .ai-share-header-title {
            font-weight: 700;
            font-size: 18px;
            color: #313238;
            line-height: 20px;
          }
        }
        .ai-share-header-right {
          display: flex;
          align-items: center;
          flex-shrink: 0;
          gap: 12px;
          font-size: 12px;
          color: #979ba5;
          line-height: 32px;
        }

        .ai-share-header-divider {
          flex-shrink: 0;
          width: 1px;
          height: 12px;
          background: #c4c6cc;
        }

        .aside-toggle {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 20px;
          height: 20px;
          color: #63656e;
          cursor: pointer;
          border-radius: 2px;

          &:hover {
            color: #4d4f56;
            background: #eaebf0;
          }

          :deep(svg) {
            width: 14px;
            height: 14px;
          }
        }
      }

      .share-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        margin-top: 24px;
        min-height: 0;
        overflow: hidden;

        .share-data {
          flex: 1;
          min-height: 0;
          display: flex;
          flex-direction: column;

          :deep(.ai-chat-container) {
            flex: 1;
            min-height: 0;
            height: 100%;
          }
        }

        .error-state {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 200px;
        }

        .retry-button {
          margin-top: 16px;
        }
      }
    }
    .share-tip {
      margin-top: 24px;
      line-height: 16px;
      font-size: 12px;
      color: #979ba5;
      flex-shrink: 0;
    }
  }
</style>
