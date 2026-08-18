<template>
  <div class="chat-window">
    <bk-resize-layout class="chat-window-layout" placement="left" :initial-divide="300" :min="200" :max="480" disabled collapsible :immediate="true">
      <template #aside>
        <BkLoading :loading="isSessionListLoading" class="session-panel">
          <!-- 搜索 -->
          <div class="session-search">
            <BkInput v-model="searchQuery" type="search" placeholder="搜索会话名称" clearable />
          </div>

          <!-- 添加会话 -->
          <BkButton
            class="add-session-btn"
            :loading="isCreatingSession"
            :disabled="!chatHelperInstance || isCreatingSession"
            @click="createNewSession"
          >
            <Plus v-if="!isCreatingSession" class="f22" />
            <span>添加会话</span>
          </BkButton>

          <!-- 会话列表 -->
          <div class="session-list" :class="{ 'has-footer': hasSelected }">
            <template v-if="filteredSessionList.length > 0">
              <BkLoading
                v-for="session in filteredSessionList"
                :key="session.sessionCode"
                :loading="isSessionLoading(session.sessionCode)"
                size="mini"
                :opacity="0.7"
              >
                <div
                  class="session-item"
                  :class="{
                    active: currentSession?.sessionCode === session.sessionCode,
                    'is-selected': isSessionSelected(session.sessionCode),
                  }"
                  @click="switchToSession(session.sessionCode)"
                >
                  <div class="session-item-content">
                    <!-- 编辑态：当前会话在 header 编辑，避免双边同时出现输入框 -->
                    <BkInput
                      v-if="editingCode === session.sessionCode && currentSession?.sessionCode !== session.sessionCode"
                      ref="editInputRef"
                      v-model="editingName"
                      size="small"
                      @blur="confirmEdit(session)"
                      @enter="confirmEdit(session)"
                      @click.stop
                    />
                    <!-- 展示态：仅会话名，与设计稿一致 -->
                    <div v-else class="session-name">
                      {{ session.sessionName }}
                    </div>
                  </div>
                  <div class="session-actions" @click.stop>
                    <span
                      v-bk-tooltips="{
                        content: 'AI 生成标题',
                        delay: [300, 0],
                      }"
                      class="action-icon icon-auto-rename"
                      @click="renameByAI(session.sessionCode)"
                    />
                    <span v-bk-tooltips="{ content: '编辑标题', delay: [300, 0] }" class="action-icon icon-edit" @click="startEdit(session)" />
                    <span
                      v-bk-tooltips="{ content: '删除会话', delay: [300, 0] }"
                      class="action-icon icon-delete"
                      @click="deleteSingle(session.sessionCode)"
                    />
                    <BkCheckbox
                      class="session-checkbox"
                      :model-value="isSessionSelected(session.sessionCode)"
                      @change="(val: boolean) => toggleSessionSelect(session.sessionCode, val)"
                    />
                  </div>
                </div>
              </BkLoading>
            </template>
            <bk-exception
              v-else
              style="margin-top: 100px"
              :description="searchQuery ? '搜索为空' : '暂无对话'"
              scene="part"
              :type="searchQuery ? 'search-empty' : 'empty'"
            />
          </div>

          <!-- 批量操作底栏 -->
          <div v-if="hasSelected" class="session-footer">
            <BkCheckbox :model-value="isAllSelected" :indeterminate="isIndeterminate" @change="toggleSelectAll"> 全选 </BkCheckbox>
            <div class="footer-actions">
              <BkButton theme="primary" size="small" @click="batchDelete"> 批量删除 </BkButton>
              <BkButton size="small" @click="cancelSelect"> 取消 </BkButton>
            </div>
          </div>
        </BkLoading>
      </template>

      <template #main>
        <div class="chat-main">
          <header class="chat-main-header">
            <div class="chat-main-left">
              <div class="chat-main-title-wrap">
                <BkInput
                  v-if="isEditingCurrentSession"
                  ref="headerEditInputRef"
                  v-model="editingName"
                  class="chat-main-title-input"
                  size="small"
                  @blur="confirmCurrentEdit"
                  @enter="confirmCurrentEdit"
                />
                <h1 v-else class="chat-main-title">{{ currentSessionName }}</h1>
              </div>
              <div v-if="currentSession" class="chat-main-title-actions">
                <span
                  v-bk-tooltips="{
                    content: 'AI 生成标题',
                    delay: [300, 0],
                  }"
                  class="action-icon icon-auto-rename"
                  :class="{
                    disabled: isSessionLoading(currentSession.sessionCode),
                  }"
                  @click="renameByAI(currentSession.sessionCode)"
                />
                <span
                  v-bk-tooltips="{ content: '编辑标题', delay: [300, 0] }"
                  class="action-icon icon-edit"
                  :class="{
                    disabled: isSessionLoading(currentSession.sessionCode),
                  }"
                  @click="startEdit(currentSession)"
                />
                <span
                  v-bk-tooltips="{ content: '删除会话', delay: [300, 0] }"
                  class="action-icon icon-delete"
                  @click="deleteSingle(currentSession.sessionCode)"
                />
              </div>
            </div>
            <div class="chat-main-actions">
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
          </header>
          <div class="chat-main-body">
            <ChatBot
              ref="chatBotRef"
              v-model:aside-collapsed="asideCollapsed"
              :url="url"
              height="100%"
              @agent-info-loaded="handleAgentInfoLoaded"
              @error="handleChatBotError"
            />
          </div>
        </div>
      </template>
    </bk-resize-layout>
  </div>
</template>

<script setup lang="ts">
  import { cloneVNode, computed, defineComponent, nextTick, ref, shallowRef, watch } from "vue"
  import { Input as BkInput, Button as BkButton, Checkbox as BkCheckbox, Loading as BkLoading, InfoBox, bkTooltips as vBkTooltips } from "bkui-vue"
  import { Plus } from "bkui-vue/lib/icon"
  import { CollapsedAsideIcon } from "@blueking/chat-x"

  import { ChatBot } from "@blueking/ai-blueking"
  import "@blueking/ai-blueking/dist/vue3/style.css"
  import router from "../router"

  import type { ChatBotExpose } from "@blueking/ai-blueking"

  const AsideToggleIcon = defineComponent({
    name: "AsideToggleIcon",
    setup() {
      return () => cloneVNode(CollapsedAsideIcon)
    },
  })

  type ChatHelper = NonNullable<ReturnType<ChatBotExpose["getChatHelper"]>>

  interface SessionItem {
    sessionCode: string
    sessionName: string
    createdAt: string
  }

  interface RequestError extends Error {
    response?: { status: number }
  }

  const chatBotRef = ref<ChatBotExpose | null>(null)
  // shallowRef 避免 reactive 自动解包内部 ref，保留 session.list / session.current 原始 Ref 语义
  const chatHelperInstance = shallowRef<ChatHelper | null>(null)
  /** 嵌入式 ChatBot 不自带侧栏开关，由业务 Header 受控 */
  const asideCollapsed = ref(true)
  const searchQuery = ref("")
  const selectedCodes = ref<Set<string>>(new Set())
  const sessionList = ref<SessionItem[]>([])
  const currentSession = ref<SessionItem | null>(null)
  const url = ref(window.BK_API_PREFIX)
  const sessionCodeFromQuery = new URLSearchParams(window.location.search).get("session")?.trim() ?? ""
  const hasHandledSessionQuery = ref(false)

  const isSessionListLoading = computed(() => !chatHelperInstance.value)

  const currentSessionName = computed(() => currentSession.value?.sessionName?.trim() ?? "")

  /** 创建会话中：复用 chat-helper session.isCreateLoading，避免重复点击 */
  const isCreatingSession = computed(() => chatHelperInstance.value?.session.isCreateLoading.value ?? false)

  const filteredSessionList = computed(() => {
    if (!searchQuery.value) return sessionList.value
    const query = searchQuery.value.toLowerCase()
    return sessionList.value.filter((s) => s.sessionName.toLowerCase().includes(query))
  })

  const hasSelected = computed(() => selectedCodes.value.size > 0)

  const isAllSelected = computed(
    () => filteredSessionList.value.length > 0 && filteredSessionList.value.every((s) => selectedCodes.value.has(s.sessionCode)),
  )

  const isIndeterminate = computed(() => hasSelected.value && !isAllSelected.value)

  const isSessionSelected = (code: string) => selectedCodes.value.has(code)

  const toggleSessionSelect = (code: string, val: boolean) => {
    const next = new Set(selectedCodes.value)
    if (val) {
      next.add(code)
    } else {
      next.delete(code)
    }
    selectedCodes.value = next
  }

  const toggleSelectAll = (val: boolean) => {
    if (val) {
      selectedCodes.value = new Set(filteredSessionList.value.map((s) => s.sessionCode))
    } else {
      selectedCodes.value = new Set()
    }
  }

  const cancelSelect = () => {
    selectedCodes.value = new Set()
  }

  const doBatchDelete = async () => {
    if (!chatHelperInstance.value) return
    const codes = [...selectedCodes.value]
    for (const code of codes) {
      try {
        await chatHelperInstance.value.session.deleteSession(code)
      } catch (e) {
        console.error("删除会话失败:", e)
      }
    }
    selectedCodes.value = new Set()
  }

  const batchDelete = () => {
    const count = selectedCodes.value.size
    InfoBox({
      title: "确认删除",
      subTitle: `确定要删除选中的 ${count} 个会话吗？删除后不可恢复。`,
      confirmText: "删除",
      cancelText: "取消",
      headerAlign: "center" as const,
      contentAlign: "center" as const,
      onConfirm: () => doBatchDelete(),
    })
  }

  const switchToSession = async (sessionCode: string) => {
    if (!chatHelperInstance.value) return
    try {
      await chatHelperInstance.value.session.chooseSession(sessionCode)
      await router.replace({
        query: {
          ...router.currentRoute.value.query,
          session: sessionCode,
        },
      })
    } catch (e) {
      console.error("切换会话失败:", e)
    }
  }

  const trySwitchToQuerySession = async (helper: ChatHelper) => {
    if (!sessionCodeFromQuery || hasHandledSessionQuery.value) return

    const targetSession = helper.session.list.value.find((session) => session.sessionCode === sessionCodeFromQuery)
    if (!targetSession) {
      hasHandledSessionQuery.value = true
      return
    }

    hasHandledSessionQuery.value = true
    if (helper.session.current.value?.sessionCode === sessionCodeFromQuery) return

    try {
      await helper.session.chooseSession(sessionCodeFromQuery)
    } catch (e) {
      console.error("根据 URL 切换会话失败:", e)
    }
  }

  const createNewSession = async () => {
    if (!chatHelperInstance.value || isCreatingSession.value) return
    try {
      const sessionCode = `new_session_${Date.now()}`
      await chatHelperInstance.value.session.createSession({
        sessionCode,
        sessionName: "新会话",
      })
      const activeCode = chatHelperInstance.value.session.current.value?.sessionCode ?? sessionCode
      await router.replace({
        query: {
          ...router.currentRoute.value.query,
          session: activeCode,
        },
      })
    } catch (e) {
      console.error("创建会话失败:", e)
    }
  }

  // ==================== 编辑标题 ====================
  const editingCode = ref<string | null>(null)
  const editingName = ref("")
  const editInputRef = ref<Array<{ $el?: HTMLElement }>>([])
  const headerEditInputRef = ref<{ $el?: HTMLElement } | null>(null)
  const loadingSessionCode = ref<string | null>(null)

  const isSessionLoading = (code: string) => loadingSessionCode.value === code

  const isEditingCurrentSession = computed(() => !!currentSession.value && editingCode.value === currentSession.value.sessionCode)

  const focusEditInput = (preferHeader = false) => {
    nextTick(() => {
      const wrapper = preferHeader ? headerEditInputRef.value : editInputRef.value?.[0]
      const el = wrapper?.$el ?? (wrapper as unknown as HTMLElement)
      const input = el?.querySelector?.("input")
      input?.focus()
      input?.select?.()
    })
  }

  const startEdit = (session: SessionItem) => {
    if (isSessionLoading(session.sessionCode)) return
    editingCode.value = session.sessionCode
    editingName.value = session.sessionName
    const isCurrent = currentSession.value?.sessionCode === session.sessionCode
    focusEditInput(isCurrent)
  }

  const confirmEdit = async (session: SessionItem) => {
    if (!chatHelperInstance.value || !editingCode.value) return
    const trimmed = editingName.value.trim()
    editingCode.value = null
    if (trimmed && trimmed !== session.sessionName) {
      loadingSessionCode.value = session.sessionCode
      try {
        await chatHelperInstance.value.session.updateSession({
          ...session,
          sessionName: trimmed,
        } as any)
      } catch (e) {
        console.error("更新会话标题失败:", e)
      } finally {
        loadingSessionCode.value = null
      }
    }
  }

  const confirmCurrentEdit = async () => {
    if (!currentSession.value) return
    await confirmEdit(currentSession.value)
  }

  // ==================== AI 自动生成标题 ====================
  const renameByAI = async (sessionCode: string) => {
    if (!chatHelperInstance.value || isSessionLoading(sessionCode)) return
    loadingSessionCode.value = sessionCode
    try {
      await chatHelperInstance.value.session.renameSession(sessionCode)
    } catch (e) {
      console.error("AI 重命名失败:", e)
    } finally {
      loadingSessionCode.value = null
    }
  }

  // ==================== 单个删除 ====================
  const deleteSingle = (sessionCode: string) => {
    InfoBox({
      title: "确认删除",
      subTitle: "确定要删除该会话吗？删除后不可恢复。",
      confirmText: "删除",
      cancelText: "取消",
      headerAlign: "center" as const,
      contentAlign: "center" as const,
      onConfirm: async () => {
        if (!chatHelperInstance.value) return
        try {
          await chatHelperInstance.value.session.deleteSession(sessionCode)
          selectedCodes.value.delete(sessionCode)
        } catch (e) {
          console.error("删除会话失败:", e)
        }
      },
    })
  }

  const handleAgentInfoLoaded = (helper: ChatHelper) => {
    chatHelperInstance.value = helper

    watch(
      () => helper.session.list.value,
      (list) => {
        sessionList.value = Array.isArray(list) ? ([...list] as SessionItem[]) : []
        void trySwitchToQuerySession(helper)
      },
      { immediate: true, deep: true },
    )

    watch(
      () => helper.session.current?.value,
      (current) => {
        currentSession.value = (current as SessionItem) ?? null
      },
      { immediate: true },
    )
  }

  const handleChatBotError = (error: Error) => {
    const status = (error as RequestError).response?.status
    if (status === 403) {
      router.push("/403")
    }
  }
</script>

<style lang="postcss" scoped>
  .chat-window {
    width: 100%;
    height: calc(100vh - 52px);
  }

  .chat-window-layout {
    height: 100%;
  }

  .session-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    background-color: #f5f7fa;
    box-sizing: border-box;
  }

  .session-search {
    padding: 12px 12px 0;
  }

  .add-session-btn {
    margin: 12px;

    .f22 {
      font-size: 22px;
    }
  }

  .session-list {
    flex: 1;
    overflow-y: auto;
    padding: 0 12px;

    &.has-footer {
      padding-bottom: 0;
    }

    &::-webkit-scrollbar {
      width: 6px;
    }

    &::-webkit-scrollbar-thumb {
      background-color: rgba(0, 0, 0, 0.15);
      border-radius: 3px;
    }

    &::-webkit-scrollbar-thumb:hover {
      background-color: rgba(0, 0, 0, 0.3);
    }
  }

  .session-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 32px;
    padding: 4px 16px;
    border-radius: 4px;
    margin-bottom: 12px;
    cursor: pointer;
    background-color: #fff;
    color: #4d4f56;
    box-sizing: border-box;
    transition:
      background-color 0.15s,
      color 0.15s,
      box-shadow 0.15s;

    .session-actions {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
      height: 24px;

      .action-icon {
        display: none;
      }

      .session-checkbox {
        display: none;
      }
    }

    &:hover {
      background-color: #e1ecff;
      color: #3a84ff;
      box-shadow: 0 2px 4px rgba(25, 25, 41, 0.05);

      .session-name {
        color: #3a84ff;
        font-weight: 700;
      }

      .session-actions {
        .action-icon,
        .session-checkbox {
          display: inline-flex;
        }
      }
    }

    /* 批量勾选时仅常驻 checkbox，操作图标仍仅 hover 显示 */
    &.is-selected .session-actions .session-checkbox {
      display: inline-flex;
    }

    &.active {
      background-color: #e1ecff;
      color: #3a84ff;
      box-shadow: 0 2px 4px rgba(25, 25, 41, 0.05);

      .session-name {
        color: #3a84ff;
        font-weight: 700;
      }
    }
  }

  .session-item-content {
    flex: 1;
    min-width: 0;
    margin-right: 8px;
  }

  .session-name {
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 12px;
    font-weight: 400;
    line-height: 20px;
    color: #4d4f56;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .action-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    flex-shrink: 0;
    cursor: pointer;
    background-color: #979ba5;
    mask-size: contain;
    mask-repeat: no-repeat;
    mask-position: center;
    -webkit-mask-size: contain;
    -webkit-mask-repeat: no-repeat;
    -webkit-mask-position: center;
    transition: background-color 0.15s;

    &:hover {
      background-color: #3a84ff;
    }

    &.disabled {
      cursor: not-allowed;
      opacity: 0.45;
      pointer-events: none;
    }
  }

  .icon-auto-rename {
    mask-image: url("@/assets/svg/auto-rename.svg");
    -webkit-mask-image: url("@/assets/svg/auto-rename.svg");
  }

  .icon-edit {
    mask-image: url("@/assets/svg/edit.svg");
    -webkit-mask-image: url("@/assets/svg/edit.svg");
  }

  .icon-delete {
    mask-image: url("@/assets/svg/delete.svg");
    -webkit-mask-image: url("@/assets/svg/delete.svg");
  }

  .session-checkbox {
    margin-left: 0;
  }

  /* 底部批量操作栏 */
  .session-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-top: 1px solid #dcdee5;
    background: #fff;
  }

  .footer-actions {
    display: flex;
    gap: 8px;
  }

  /* 右侧聊天区域 */
  .chat-main {
    display: flex;
    flex-direction: column;
    flex: 1;
    height: 100%;
    min-width: 0;
    position: relative;
    background: #fff;
    .ai-chatbot :deep(.collapse-button.is-right) {
      right: auto;
    }
    .ai-chatbot :deep(.ai-is-collapse .collapse-button.is-right) {
      right: 0;
      border-radius: 4px 0 0 4px;
    }
  }

  .chat-main-header {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    height: 52px;
    padding: 0 16px 0 24px;
    background: #fff;
    border-bottom: 1px solid #dcdee5;
    box-sizing: border-box;
    gap: 16px;
  }

  /* 标题 + 操作图标紧挨排列（设计稿：icon 跟在 title 后） */
  .chat-main-left {
    display: flex;
    flex: 1;
    align-items: center;
    min-width: 0;
    gap: 12px;
  }

  .chat-main-title-wrap {
    flex: 0 1 auto;
    min-width: 0;
    max-width: 100%;
  }

  .chat-main-title {
    min-width: 0;
    margin: 0;
    overflow: hidden;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 16px;
    font-weight: 400;
    line-height: 24px;
    color: #313238;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .chat-main-title-input {
    max-width: 420px;
  }

  .chat-main-title-actions {
    display: flex;
    flex-shrink: 0;
    gap: 12px;
    align-items: center;

    .action-icon {
      display: inline-flex;
    }
  }

  .chat-main-actions {
    display: flex;
    flex-shrink: 0;
    gap: 12px;
    align-items: center;
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

  .chat-main-body {
    flex: 1;
    min-height: 0;
  }
</style>

<style lang="postcss">
  .chat-main .ai-chatbot {
    height: 100% !important;
  }

  /* 覆盖 chat-bot 组件内 message 和 input 的最大宽度 */
  .chat-main .ai-chatbot .chatbot-messages .message-group {
    max-width: 800px !important;
  }

  .chat-main .ai-chatbot .chatbot-input {
    max-width: 832px !important;
  }

  .chat-main .ai-chatbot .chatbot-input .chat-input-container .chat-input {
    max-width: 800px !important;
  }

  /* 覆盖 welcome 图片及相关元素尺寸 */
  .chat-main .ai-chatbot .chatbot-welcome .welcome-banner {
    width: 420px;
  }

  .chat-main .ai-chatbot .chatbot-welcome .welcome-content {
    padding-top: 110px;
  }
</style>
