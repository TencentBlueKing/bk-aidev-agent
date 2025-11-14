<template>
  <div class="share-container" role="main" aria-label="AI 分享内容">
    <div class="ai-share-container">
      <div class="ai-share-header">
        <div class="ai-share-header-left">
          <img src="@/assets/svg/xiaojing.svg" alt="AI助手logo" />
          <h1 class="ai-share-header-title">{{ title }}</h1>
        </div>
        <div class="ai-share-header-right" v-if="agentName">
          {{ `分享于 "${agentName}"` }}
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
          <MessageList
            standalone
            :session-contents="shareData"
            :has-session-contents="true"
            :content-margin-bottom="0"
            :is-select-mode="false"
            :readonly="true"
          />
        </div>
      </div>
    </div>
    <div class="share-tip">内容由 AI 大模型生成，请仔细甄别</div>
  </div>
</template>

<script setup lang="ts">
  import { onBeforeMount, ref, computed } from "vue"
  import { useRoute } from "vue-router"
  import { Message, Exception as BkException, Button as BkButton } from "bkui-vue"
  import { MessageList } from "@blueking/ai-blueking"
  import "@blueking/ai-blueking/dist/vue3/style.css"

  // TypeScript 接口定义
  interface ShareData {
    session_contents: any[]
    session_name: string
    agent_name: string
  }

  interface ApiResponse {
    data: ShareData
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
  const shareData = ref<any[]>([])
  const error = ref<string | null>(null)
  const currentShareCode = ref<string>("")

  const route = useRoute()

  // 计算属性
  const hasValidData = computed(() => shareData.value.length > 0)
  const hasError = computed(() => error.value !== null)
  const errorMessage = computed(() => error.value || "")
  const canRetry = computed(() => {
    if (!currentShareCode.value || !hasError.value) return false
    const status = getErrorStatus(error.value)
    return ERROR_MESSAGES[status]?.canRetry ?? DEFAULT_ERROR.canRetry
  })

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

      shareData.value = result.data.session_contents
      title.value = result.data.session_name || "AI 对话分享"
      agentName.value = result.data.agent_name || ""
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
    height: 100vh;
    opacity: 0.89;
    background-image: linear-gradient(0deg, #c6cdeb 0%, #fdf7f6 20%, #ebf3f8 38%, #f8f8ff 71%, #bae6fd 100%);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    .ai-share-container {
      width: 900px;
      min-height: 300px;
      background: #ffffff;
      border-radius: 16px;
      padding: 24px;
      display: flex;
      flex-direction: column;
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
          font-size: 12px;
          color: #979ba5;
          line-height: 32px;
        }
      }

      .share-content {
        flex: 1;
        margin-top: 24px;
        padding-bottom: 24px;
        min-height: 200px;
        overflow-y: auto;

        /* 自定义滚动条样式 */
        &::-webkit-scrollbar {
          width: 6px;
        }

        &::-webkit-scrollbar-track {
          background: #f5f5f5;
          border-radius: 3px;
        }

        &::-webkit-scrollbar-thumb {
          background: #c4c6cc;
          border-radius: 3px;

          &:hover {
            background: #979ba5;
          }
        }

        .share-data {
          :deep(> .message-wrapper) {
            margin: 0;
            overflow: visible;
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

        .share-data {
          font-size: 12px;
          color: #313238;
          line-height: 1.5;

          pre {
            margin: 0;
            padding: 16px;
            background: #f5f7fa;
            border-radius: 4px;
            overflow-x: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
          }
        }
      }
    }
    .share-tip {
      margin-top: 24px;
      line-height: 16px;
      font-size: 12px;
      color: #979ba5;
    }
  }
</style>
