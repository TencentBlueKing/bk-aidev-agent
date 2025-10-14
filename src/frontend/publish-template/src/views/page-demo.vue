<template>
  <div class="chat-wrapper" v-bkloading="loadingConf">
    <div class="chat-container">
      <!-- 会话列表侧边栏 (根据 enableChatSession 控制显示) -->
      <div class="session-list-sidebar" v-if="enableChatSession">
        <!-- 顶部控制区域 -->
        <div class="top-controls">
          <BKInput type="text" class="search-input" placeholder="搜索会话名称" v-model="searchQuery" clearable>
            <template #suffix>
              <span class="input-icon suffix-icon">
                <search />
              </span>
            </template>
          </BKInput>
        </div>

        <!-- 新建会话按钮 -->
        <BKButton class="new-chat-button" @click="createNewSession">
          <plus class="f22" />
          <span>添加会话</span>
        </BKButton>

        <!-- 会话列表 -->
        <div class="conversation-list" :class="{ 'is-empty': filteredSessionList.length === 0 && searchQuery }">
          <template v-if="filteredSessionList.length > 0">
            <div
              v-for="session in filteredSessionList"
              :key="session.sessionCode"
              class="conversation-item"
              :class="{ active: currentSession?.sessionCode === session.sessionCode }"
              @click="switchToSession(session.sessionCode)"
            >
              <div class="conversation-title">{{ session.sessionName }}</div>
              <div class="conversation-subtitle">{{ formatSessionDate(session.createdAt) }}</div>
            </div>
          </template>
          <bk-exception
            v-else
            style="margin-top: 100px"
            :description="searchQuery ? '搜索为空' : '暂无对话'"
            scene="part"
            :type="searchQuery ? 'search-empty' : 'empty'"
          ></bk-exception>
        </div>
      </div>

      <!-- 主聊天区域 -->
      <div class="main-chat-area" :class="{ 'full-width': !enableChatSession }">
        <AIBlueking
          v-if="isComponentReady"
          ref="aiBlueking"
          ext-cls="page-demo-ai-blueking"
          hide-header
          :draggable="false"
          :hide-nimbus="false"
          :url="url"
          :default-top="52"
          :sdk-error="handleSdkError"
          :default-width="defaultWidth"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref, onMounted, reactive, watch, computed } from "vue"
  import { Input as BKInput, Button as BKButton } from "bkui-vue"
  import { Search, Plus } from "bkui-vue/lib/icon"

  import AIBlueking, { AIBluekingExpose } from "@blueking/ai-blueking"
  import "@blueking/ai-blueking/dist/vue3/style.css"
  import router from "../router"
  import { fetchAgentInfo } from "../composables/useAgentInfo"

  const aiBlueking = ref<AIBluekingExpose | null>(null)
  const sessionList = ref<any[]>([])
  const currentSession = ref<any>(null)
  const searchQuery = ref("")
  const agentInfo = ref<any>(null) // 用于存储从agent/info接口获取的数据
  const isComponentReady = ref(false) // 控制 AIBlueking 组件是否准备就绪

  const url = ref(window.BK_API_PREFIX)

  // 获取agent信息的函数
  const getAgentInfo = async () => {
    const data = await fetchAgentInfo(url.value)
    agentInfo.value = data
    return data
  }

  const handleSdkError = (error: any) => {
    console.error("SDK错误:", error)
    router.push("/403")
  }

  // 设置 AIBlueking 组件的宽度为容器宽度减去会话列表宽度
  const AIBluekingWidth = ref(800)

  // 计算 AIBlueking 组件的默认宽度
  const defaultWidth = computed(() => {
    if (typeof window === "undefined") return 800
    // 根据 enableChatSession 的值来决定宽度
    return enableChatSession.value ? window.innerWidth - 280 : window.innerWidth
  })

  const title = ref("加载中...")

  const loading = ref(true)

  const loadingConf = reactive({
    loading,
    title,
  })

  // 过滤会话列表
  const filteredSessionList = computed(() => {
    if (!searchQuery.value) {
      return sessionList.value
    }
    return sessionList.value.filter((session) => session.sessionName.toLowerCase().includes(searchQuery.value.toLowerCase()))
  })

  // 是否启用会话管理 (基于从接口获取的数据)
  const enableChatSession = computed(() => {
    // 如果还没有获取到agent信息，返回false
    if (!agentInfo.value) {
      return false
    }
    // 根据接口返回的配置确定是否启用会话管理
    return agentInfo.value?.conversation_settings?.enable_chat_session ?? true
  })

  // 格式化会话日期
  const formatSessionDate = (dateString: string) => {
    if (!dateString) return ""
    const date = new Date(dateString)
    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)

    if (date.toDateString() === today.toDateString()) {
      return "今天"
    } else if (date.toDateString() === yesterday.toDateString()) {
      return "昨天"
    } else {
      return date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" })
    }
  }

  // 切换到指定会话
  const switchToSession = async (sessionCode: string) => {
    if (aiBlueking.value && typeof aiBlueking.value.switchToSession === "function") {
      try {
        await aiBlueking.value.switchToSession(sessionCode)
        // 更新当前会话状态
        const sessions = sessionList.value
        currentSession.value = sessions.find((s: any) => s.sessionCode === sessionCode) || null
      } catch (error) {
        console.error("切换会话失败:", error)
      }
    }
  }

  // 创建新会话
  const createNewSession = async () => {
    if (aiBlueking.value && typeof aiBlueking.value.addNewSession === "function") {
      try {
        const newSession: any = await aiBlueking.value.addNewSession()
        // 更新会话列表
        if (aiBlueking.value.getSessionList) {
          sessionList.value = await aiBlueking.value.getSessionList()
        }
        // 切换到新会话
        if (newSession && newSession.sessionCode) {
          currentSession.value = newSession
        }
      } catch (error) {
        console.error("创建新会话失败:", error)
      }
    }
  }

  // 获取会话列表
  const fetchSessionList = async () => {
    if (aiBlueking.value && typeof (aiBlueking.value as any).sessionList?.value !== "undefined") {
      // 如果 sessionList 是响应式属性，直接使用
      sessionList.value = (aiBlueking.value as any).sessionList.value
      currentSession.value = sessionList.value[0] || null
    } else if (aiBlueking.value && typeof aiBlueking.value.getSessionList === "function") {
      // 如果有 getSessionList 方法，调用它
      try {
        sessionList.value = await aiBlueking.value.getSessionList()
        currentSession.value = sessionList.value[0] || null
      } catch (error) {
        console.error("获取会话列表失败:", error)
      }
    }
  }

  // 监听 AIBlueking 组件的 sessionList 变化
  watch(
    () => (aiBlueking.value as any)?.sessionList?.value,
    (newSessionList: any) => {
      if (newSessionList) {
        sessionList.value = newSessionList
        if (!currentSession.value && newSessionList.length > 0) {
          currentSession.value = newSessionList[0]
        }
      }
    },
    { deep: true }
  )

  // 监听窗口大小变化，动态调整 AIBlueking 宽度和位置
  const handleResize = () => {
    if (typeof window === "undefined") return
    // 强制更新 AIBluekingWidth 以触发重新计算
    AIBluekingWidth.value = enableChatSession.value ? window.innerWidth - 280 : window.innerWidth

    // 等待下一帧以确保组件已更新其内部状态
    // 然后触发组件刷新以确保它保持在边界内
    setTimeout(() => {
      if (aiBlueking.value && typeof aiBlueking.value.updatePositionAndSize === "function") {
        // 获取当前位置并触发更新以确保它保持在窗口边界内
        // 这会强制组件根据新的窗口尺寸调整其位置/大小
        const newWidth = enableChatSession.value ? window.innerWidth - 280 : window.innerWidth
        const defaultTop = 52 // 如组件的 default-top 属性所指定
        const defaultLeft = window.innerWidth - newWidth // 保持在右侧

        aiBlueking.value.updatePositionAndSize(defaultLeft, defaultTop, newWidth, window.innerHeight - defaultTop)
      }
    }, 100) // 延迟以确保 DOM 更新已完成
  }

  onMounted(async () => {
    if (typeof window !== "undefined") {
      window.addEventListener("resize", handleResize)
    }

    // 先获取agent信息
    await getAgentInfo()

    // 设置组件准备就绪标志
    isComponentReady.value = true

    // 获取agent信息后再初始化组件
    setTimeout(() => {
      aiBlueking.value?.handleShow()
      loading.value = false
      // 初始化会话列表
      fetchSessionList()
      // 触发一次 resize 事件确保组件宽度正确计算
      setTimeout(() => {
        if (typeof window !== "undefined") {
          window.dispatchEvent(new Event("resize"))
        }
      }, 100)
    }, 200)
  })
</script>

<style lang="postcss" scoped>
  .chat-wrapper {
    width: 100%;
    height: calc(100vh - 52px); /* 减去导航栏高度 */
  }

  .chat-container {
    display: flex;
    height: 100%;
  }

  .main-chat-area {
    flex: 1;
    height: 100%;
  }

  .main-chat-area.full-width {
    flex: 1;
    width: 100%;
  }

  .session-list-sidebar {
    display: flex;
    flex-direction: column;
    width: 280px;
    height: calc(100vh - 52px); /* 减去导航栏高度 */
    background-color: #ffffff;
    padding: 12px;
    padding-bottom: 20px; /* 底部额外留白 */
    box-sizing: border-box;
    border-right: 1px solid #efefef;
    overflow: hidden; /* 防止整个侧边栏滚动 */
  }

  .top-controls {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    .bk-input {
      align-items: center;
      .input-icon {
        color: #c4c6cc;
        padding-right: 8px;
      }
    }
  }

  .new-chat-button {
    margin-bottom: 12px;
    .f22 {
      font-size: 22px;
    }
  }

  .conversation-list {
    flex: 0 1 auto; /* 不强制拉伸，根据内容调整 */
    max-height: calc(100vh - 52px - 140px); /* 减去导航栏高度和顶部控件高度 */
    overflow-y: auto;
    padding-right: 8px;
    margin-right: -8px;
  }

  .conversation-list.is-empty {
    flex: 0 0 auto;
    height: auto;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow-y: visible; /* 空状态时不需要滚动 */
    max-height: calc(100vh - 52px - 140px);
  }

  .conversation-list:not(.is-empty) {
    flex: 0 1 auto;
    overflow-y: auto;
  }

  /* macOS 风格滚动条样式 */
  .conversation-list::-webkit-scrollbar {
    width: 8px;
  }

  .conversation-list::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.05);
    border-radius: 4px;
  }

  .conversation-list::-webkit-scrollbar-thumb {
    background-color: rgba(0, 0, 0, 0.3);
    border-radius: 4px;
    transition: background-color 0.2s ease;
  }

  .conversation-list::-webkit-scrollbar-thumb:hover {
    background-color: rgba(0, 0, 0, 0.5);
  }

  .conversation-list::-webkit-scrollbar-thumb:active {
    background-color: rgba(0, 0, 0, 0.6);
  }

  .conversation-item {
    padding: 10px 12px;
    border-radius: 8px;
    margin-bottom: 4px;
    cursor: pointer;
    font-weight: 500;
    font-size: 14px;
    background-color: #f7f8fa;
    color: #303133;
  }

  .conversation-item:hover {
    background-color: #eff0f1;
  }

  .conversation-item.active {
    background-color: #e6f0ff;
    color: #1677ff;
  }

  .conversation-title {
    font-weight: 500;
    font-size: 14px;
    margin-bottom: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .conversation-subtitle {
    font-weight: 400;
    font-size: 12px;
    color: #909399;
  }

  .conversation-item.active .conversation-subtitle {
    color: #1677ff;
  }

  /* 响应式设计 */
  @media (max-width: 768px) {
    .session-list-sidebar {
      width: 240px;
    }
  }
</style>

<style lang="postcss">
  .page-demo-ai-blueking {
    .handle {
      pointer-events: none;
    }
    .ai-blueking-container-wrapper {
      box-shadow: none;
    }
  }
</style>
