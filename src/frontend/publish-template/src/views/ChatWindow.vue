<template>
  <div class="chat-window">
    <bk-resize-layout class="chat-window-layout" placement="left" :border="false" :initial-divide="300" :min="200" :max="480" collapsible :immediate="true">
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
                <BkInput
                  v-if="editingCode === session.sessionCode && editPlace === 'list'"
                  v-model="editingName"
                  class="session-edit-input"
                  @blur="confirmEdit(session)"
                  @enter="confirmEdit(session)"
                  @click.stop
                />
                <div
                  v-else
                  class="session-item"
                  :class="{
                    active: currentSession?.sessionCode === session.sessionCode,
                    'is-selected': isSessionSelected(session.sessionCode),
                  }"
                  @click="switchToSession(session.sessionCode)"
                >
                  <span class="session-prefix" aria-hidden="true">
                    <i v-if="currentSession?.sessionCode === session.sessionCode" class="session-active-bar" />
                    <i v-else class="session-chat-icon" />
                  </span>
                  <div class="session-item-content">
                    <div class="session-name">
                      {{ session.sessionName }}
                    </div>
                  </div>
                  <span v-if="getSessionTimeText(session)" class="session-time">{{ getSessionTimeText(session) }}</span>
                  <div class="session-actions" @click.stop>
                    <span
                      v-bk-tooltips="{
                        content: 'AI 生成标题',
                        delay: [300, 0],
                      }"
                      class="action-icon icon-auto-rename"
                      @click="renameByAI(session.sessionCode)"
                    />
                    <span v-bk-tooltips="{ content: '编辑标题', delay: [300, 0] }" class="action-icon icon-edit" @click="startEdit(session, 'list')" />
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
                  v-model="editingName"
                  class="chat-main-title-input"
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
                  @click="startEdit(currentSession, 'header')"
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
                :class="{ 'is-open': !asideCollapsed }"
                @click="asideCollapsed = !asideCollapsed"
              >
                <AsideToggleIcon />
              </span>
            </div>
          </header>
          <div class="chat-main-body">
            <section class="dynamic-bg" aria-hidden="true">
              <span class="color-orb orb-blue" />
              <span class="color-orb orb-purple" />
              <span class="color-orb orb-indigo" />
              <span class="grid-glow" />
            </section>
            <ChatBot
              ref="chatBotRef"
              v-model:aside-collapsed="asideCollapsed"
              :url="url"
              height="100%"
              size="normal"
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
  import { cloneVNode, computed, defineComponent, nextTick, onMounted, ref, shallowRef, watch } from "vue"
  import { Input as BkInput, Button as BkButton, Checkbox as BkCheckbox, Loading as BkLoading, InfoBox, bkTooltips as vBkTooltips } from "bkui-vue"
  import { Plus } from "bkui-vue/lib/icon"
  import { CollapsedAsideIcon } from "@blueking/chat-x"

  import { ChatBot } from "@blueking/ai-blueking"
  import "@blueking/ai-blueking/dist/vue3/style.css"
  import {
    clearChatAccessDenied,
    hasChatAccessDenied,
    invalidateAgentAccess,
    markChatAccessDenied,
  } from "../composables/use-agent-access"
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
    createdAt?: string
    updatedAt?: string
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

  const getSessionTimeText = (session: SessionItem) => {
    const raw = session.updatedAt || session.createdAt
    if (!raw) return ""
    const target = new Date(raw)
    if (Number.isNaN(target.getTime())) return ""
    const diffMinutes = Math.floor((Date.now() - target.getTime()) / 60000)
    if (diffMinutes < 60) return `${Math.max(diffMinutes, 1)} 分钟前`
    const diffHours = Math.floor(diffMinutes / 60)
    if (diffHours < 24) return `${diffHours} 小时前`
    const month = String(target.getMonth() + 1).padStart(2, "0")
    const day = String(target.getDate()).padStart(2, "0")
    return `${target.getFullYear()}-${month}-${day}`
  }

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
      title: `确认删除 ${count} 个会话？`,
      subTitle: `确定要删除选中的 ${count} 个会话吗？删除后不可恢复。`,
      confirmText: "删除",
      cancelText: "取消",
      confirmButtonTheme: "primary",
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
  const editPlace = ref<"list" | "header" | null>(null)
  const loadingSessionCode = ref<string | null>(null)

  const isSessionLoading = (code: string) => loadingSessionCode.value === code

  const isEditingCurrentSession = computed(
    () => editPlace.value === "header" && !!currentSession.value && editingCode.value === currentSession.value.sessionCode,
  )

  const focusEditInput = (place: "list" | "header") => {
    nextTick(() => {
      const input = document.querySelector<HTMLInputElement>(
        place === "header" ? ".chat-main-title-input input" : ".session-edit-input input",
      )
      input?.focus()
      input?.select()
    })
  }

  const startEdit = (session: SessionItem, place: "list" | "header") => {
    if (isSessionLoading(session.sessionCode)) return
    editingCode.value = session.sessionCode
    editingName.value = session.sessionName
    editPlace.value = place
    focusEditInput(place)
  }

  const confirmEdit = async (session: SessionItem) => {
    if (!chatHelperInstance.value || !editingCode.value) return
    const trimmed = editingName.value.trim()
    editingCode.value = null
    editPlace.value = null
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
      title: "确认删除 1 个会话？",
      subTitle: "确定要删除该会话吗？删除后不可恢复。",
      confirmText: "删除",
      cancelText: "取消",
      confirmButtonTheme: "primary",
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

  const splitWelcomeTitle = () => {
    const title = document.querySelector<HTMLElement>(".chat-main .ai-welcome-title")
    if (!title || title.dataset.inkSplit === "1") return
    const matched = (title.textContent ?? "").match(/^(你好)(，|,)?(.*)$/)
    if (!matched?.[3]) return
    title.dataset.inkSplit = "1"
    title.textContent = ""
    const ink = document.createElement("span")
    ink.className = "ai-welcome-title-ink"
    ink.textContent = `${matched[1]}${matched[2] ?? ""}`
    const brand = document.createElement("span")
    brand.className = "ai-welcome-title-brand"
    brand.textContent = matched[3]
    title.append(ink, brand)
  }

  onMounted(() => {
    const root = document.querySelector(".chat-main")
    if (!root) return
    const observer = new MutationObserver(() => {
      splitWelcomeTitle()
    })
    observer.observe(root, { childList: true, subtree: true, characterData: true })
    splitWelcomeTitle()
  })

  const handleAgentInfoLoaded = (helper: ChatHelper) => {
    clearChatAccessDenied()
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
      if (hasChatAccessDenied()) {
        return
      }
      markChatAccessDenied()
      invalidateAgentAccess()
      router.replace({
        name: "agent-access",
        query: router.currentRoute.value.query,
      })
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
    background-color: var(--aidev-workbench-aside-background);
    box-sizing: border-box;
  }

  .session-search {
    padding: 12px 12px 0;
  }

  .add-session-btn {
    margin: 12px 12px 0;

    .f22 {
      font-size: 16px;
    }
  }

  .session-edit-input {
    width: 100%;
    margin-top: 8px;
  }

  .session-list {
    flex: 1;
    overflow-y: auto;
    padding: 12px 12px 0;

    > :first-child .session-item {
      margin-top: 0;
    }

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
    line-height: 32px;
    padding: 0 8px;
    margin-top: 2px;
    border: 1px solid transparent;
    border-radius: 8px;
    box-sizing: content-box;
    cursor: pointer;
    background-color: transparent;
    color: var(--aidev-workbench-session-list-color);
    box-sizing: border-box;

    .session-prefix {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      margin-right: 8px;
      flex-shrink: 0;
    }

    .session-chat-icon {
      display: block;
      flex: none;
      width: 16px;
      height: 16px;
      background-color: var(--aidev-assist-color);
      mask-image: url("@/assets/svg/chat.svg");
      mask-repeat: no-repeat;
      mask-position: center;
      mask-size: 16px 16px;
      -webkit-mask-image: url("@/assets/svg/chat.svg");
      -webkit-mask-repeat: no-repeat;
      -webkit-mask-position: center;
      -webkit-mask-size: 16px 16px;
    }

    .session-active-bar {
      width: 4px;
      height: 12px;
      border-radius: 8px;
      background: var(--aidev-workbench-session-list-active-color);
    }

    .session-actions {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
      height: 24px;

      .action-icon {
        display: none;
        width: 20px;
        height: 20px;
        background-color: transparent;
        mask-image: none;
        -webkit-mask-image: none;
        border-radius: var(--aidev-radius);

        &::after {
          content: "";
          width: 14px;
          height: 14px;
          background-color: var(--aidev-assist-color);
          mask-repeat: no-repeat;
          mask-position: center;
          mask-size: contain;
          -webkit-mask-repeat: no-repeat;
          -webkit-mask-position: center;
          -webkit-mask-size: contain;
        }

        &:hover {
          background-color: var(--aidev-icon-hover-background);

          &::after {
            background-color: var(--aidev-clickable-color);
          }
        }
      }

      .session-checkbox {
        display: none;
      }
    }

    &:hover:not(.active) {
      background-color: var(--aidev-workbench-session-list-hover-background);

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
      background-color: var(--aidev-workbench-session-list-active-background);
      border-color: var(--aidev-workbench-session-list-active-border-color);
      color: var(--aidev-workbench-session-list-active-color);
      font-weight: 700;

      .session-name {
        color: var(--aidev-workbench-session-list-active-color);
        font-weight: 700;
      }

      &:hover .session-actions {
        .action-icon,
        .session-checkbox {
          display: inline-flex;
        }
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
    line-height: 32px;
    color: var(--aidev-workbench-session-list-color);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .session-time {
    flex-shrink: 0;
    font-size: 12px;
    font-weight: 400;
    line-height: 32px;
    color: var(--aidev-workbench-session-list-time-color);
    white-space: nowrap;
  }

  .session-item:hover .session-time,
  .session-item.is-selected .session-time {
    display: none;
  }

  .action-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    flex-shrink: 0;
    cursor: pointer;
    background-color: var(--aidev-assist-color);
    mask-size: contain;
    mask-repeat: no-repeat;
    mask-position: center;
    -webkit-mask-size: contain;
    -webkit-mask-repeat: no-repeat;
    -webkit-mask-position: center;
    transition: background-color 0.15s;

    &:hover {
      background-color: var(--aidev-clickable-color);
    }

    &.disabled {
      cursor: not-allowed;
      opacity: 0.45;
      pointer-events: none;
    }
  }

  .session-item .icon-auto-rename::after,
  .icon-auto-rename {
    mask-image: url("@/assets/svg/auto-rename.svg");
    -webkit-mask-image: url("@/assets/svg/auto-rename.svg");
  }

  .session-item .icon-edit::after,
  .icon-edit {
    mask-image: url("@/assets/svg/edit.svg");
    -webkit-mask-image: url("@/assets/svg/edit.svg");
  }

  .session-item .icon-delete::after,
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
    border-top: 1px solid var(--aidev-line-strong-color);
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
    background: var(--aidev-main-background);
    border-bottom: 1px solid var(--aidev-line-strong-color);
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
    color: var(--aidev-title-color);
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .chat-main-title-wrap:has(.chat-main-title-input) {
    flex: 1;
    min-width: 120px;
  }

  .chat-main-title-input {
    width: 100%;
    max-width: 420px;
  }

  .chat-main-title-actions {
    display: flex;
    flex-shrink: 0;
    gap: 12px;
    align-items: center;

    .action-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 20px;
      height: 20px;
      background-color: transparent;
      mask-image: none;
      -webkit-mask-image: none;
      border-radius: var(--aidev-radius);

      &::after {
        content: "";
        width: 14px;
        height: 14px;
        background-color: var(--aidev-assist-color);
        mask-repeat: no-repeat;
        mask-position: center;
        mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        -webkit-mask-position: center;
        -webkit-mask-size: contain;
      }

      &:hover {
        background-color: var(--aidev-icon-light-hover-background);
        box-shadow: none;

        &::after {
          background-color: var(--aidev-clickable-color);
        }
      }
    }

    .icon-auto-rename::after {
      mask-image: url("@/assets/svg/auto-rename.svg");
      -webkit-mask-image: url("@/assets/svg/auto-rename.svg");
    }

    .icon-edit::after {
      mask-image: url("@/assets/svg/edit.svg");
      -webkit-mask-image: url("@/assets/svg/edit.svg");
    }

    .icon-delete::after {
      mask-image: url("@/assets/svg/delete.svg");
      -webkit-mask-image: url("@/assets/svg/delete.svg");
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
    width: 24px;
    height: 24px;
    color: var(--aidev-main-color);
    cursor: pointer;
    border-radius: var(--aidev-radius);

    &:hover {
      color: var(--aidev-clickable-color);
      background: var(--aidev-icon-light-hover-background);
    }

    &.is-open {
      color: var(--aidev-clickable-color);
      background: var(--aidev-item-hover-background);
    }

    :deep(svg) {
      width: 14px;
      height: 14px;
    }
  }

  .chat-main-body {
    position: relative;
    flex: 1;
    min-height: 0;
  }

  .dynamic-bg {
    position: absolute;
    inset: 0;
    z-index: 0;
    overflow: hidden;
    pointer-events: none;
    background: #fff;
  }

  .chat-main:not(:has(.ai-is-welcome)) .dynamic-bg {
    display: none;
  }

  .chat-main-body :deep(.ai-chatbot) {
    position: relative;
    z-index: 1;
  }

  .color-orb {
    position: absolute;
    border-radius: 50%;
    pointer-events: none;
    filter: blur(26px);
    will-change: transform, opacity, filter;
  }

  .orb-blue {
    width: 34%;
    height: 27%;
    left: 58%;
    top: 8%;
    background: radial-gradient(
      circle at 50% 50%,
      color-mix(in srgb, var(--aidev-clickable-color) 26%, transparent) 0%,
      rgba(149, 184, 255, 0.13) 44%,
      rgba(255, 255, 255, 0) 72%
    );
    animation: orbBlueBreath 16s ease-in-out infinite;
  }

  .orb-purple {
    width: 58%;
    height: 46%;
    left: 3%;
    top: 22%;
    background: radial-gradient(
      circle at 50% 50%,
      rgba(170, 150, 235, 0.3) 0%,
      rgba(213, 203, 245, 0.17) 46%,
      rgba(255, 255, 255, 0) 76%
    );
    animation: orbPurpleBreath 19s ease-in-out infinite -3.2s;
  }

  .orb-indigo {
    width: 38%;
    height: 43%;
    left: 42%;
    top: 48%;
    background: radial-gradient(
      circle at 50% 50%,
      rgba(75, 108, 255, 0.22) 0%,
      rgba(180, 194, 255, 0.13) 43%,
      rgba(255, 255, 255, 0) 74%
    );
    animation: orbIndigoBreath 17.5s ease-in-out infinite -5.8s;
  }

  .grid-glow {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(color-mix(in srgb, var(--aidev-clickable-color) 8%, transparent) 1px, transparent 1px),
      linear-gradient(90deg, color-mix(in srgb, var(--aidev-clickable-color) 8%, transparent) 1px, transparent 1px);
    background-size: 24px 24px;
    mask-image: radial-gradient(ellipse at 50% 46%, rgba(0, 0, 0, 0.92) 0, rgba(0, 0, 0, 0.52) 50%, transparent 76%);
    animation: gridOpacityBreath 7.8s ease-in-out infinite;
  }

  @keyframes orbBlueBreath {
    0%,
    100% {
      opacity: 0.5;
      transform: translate3d(-18%, -4%, 0) scale(0.9);
      filter: blur(29px) saturate(0.88) brightness(0.9);
    }
    28% {
      opacity: 0.86;
      transform: translate3d(10%, 20%, 0) scale(1.13);
      filter: blur(23px) saturate(1.32) brightness(1.2);
    }
    62% {
      opacity: 0.64;
      transform: translate3d(24%, -10%, 0) scale(1.02);
      filter: blur(27px) saturate(1.08) brightness(1.02);
    }
    82% {
      opacity: 0.76;
      transform: translate3d(-2%, 28%, 0) scale(1.08);
      filter: blur(25px) saturate(1.22) brightness(1.12);
    }
  }

  @keyframes orbPurpleBreath {
    0%,
    100% {
      opacity: 0.4;
      transform: translate3d(10%, -12%, 0) scale(1.02);
      filter: blur(34px) saturate(0.9) brightness(0.88);
    }
    34% {
      opacity: 0.78;
      transform: translate3d(-24%, 22%, 0) scale(0.9);
      filter: blur(25px) saturate(1.35) brightness(1.18);
    }
    66% {
      opacity: 0.58;
      transform: translate3d(24%, 10%, 0) scale(1.14);
      filter: blur(30px) saturate(1.08) brightness(1.02);
    }
    84% {
      opacity: 0.68;
      transform: translate3d(-8%, -20%, 0) scale(0.96);
      filter: blur(27px) saturate(1.2) brightness(1.1);
    }
  }

  @keyframes orbIndigoBreath {
    0%,
    100% {
      opacity: 0.44;
      transform: translate3d(-14%, 18%, 0) scale(0.94);
      filter: blur(31px) saturate(0.86) brightness(0.88);
    }
    31% {
      opacity: 0.72;
      transform: translate3d(22%, -18%, 0) scale(1.12);
      filter: blur(24px) saturate(1.24) brightness(1.1);
    }
    58% {
      opacity: 0.82;
      transform: translate3d(6%, 24%, 0) scale(1.05);
      filter: blur(23px) saturate(1.32) brightness(1.18);
    }
    78% {
      opacity: 0.56;
      transform: translate3d(-26%, -8%, 0) scale(0.98);
      filter: blur(29px) saturate(1.02) brightness(0.98);
    }
  }

  @keyframes gridOpacityBreath {
    0%,
    100% {
      opacity: 0.42;
    }
    50% {
      opacity: 0.72;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .color-orb,
    .grid-glow {
      animation: none;
    }
  }
</style>

<style lang="postcss">
  .chat-main .ai-chatbot {
    height: 100% !important;
  }

  /* 覆盖左侧消息缩略条位置：避开折叠按钮，并与其垂直居中对齐 */
  .chat-main .ai-chatbot .ai-message-minimap {
    top: 0;
    height: 100%;
  }

  .chat-main .ai-chatbot .ai-message-minimap-list {
    left: 40px;
    top: calc(50% - 52px / 2);
  }

  /* 覆盖 chat-bot 组件内 message 和 input 的最大宽度 */
  .chat-main .ai-chatbot .chatbot-messages .message-group {
    max-width: 800px !important;
  }

  .chat-main .ai-chatbot .ai-blueking-banner-icon {
    width: 440px;
    height: auto;
  }

  .chat-main .ai-chatbot .ai-welcome-title {
    margin: 0;
    font-size: 48px;
    font-weight: 700;
    line-height: 60px;
    color: #1a1a1a;
  }

  .chat-main .ai-chatbot .ai-welcome-title-ink {
    color: #1a1a1a;
  }

  .chat-main .ai-chatbot .ai-welcome-title-brand {
    color: transparent;
    background-image: linear-gradient(155deg, #4abdfb 0%, #425bfb 38%, #4551fb 55%, #7548fb 78%, #c0458f 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .chat-main .ai-chatbot .ai-welcome-remark {
    margin-top: 24px;
    margin-bottom: 8px;
    font-size: 14px;
    font-weight: 400;
    line-height: 22px;
    color: #4d4f56;
    text-align: center;
  }

  .chat-main .ai-chatbot .ai-welcome-remark .ai-markdown-content,
  .chat-main .ai-chatbot .ai-welcome-remark p {
    margin: 0;
    font-size: 14px;
    font-weight: 400;
    line-height: 22px;
    color: #4d4f56;
    text-align: center;
  }

  .chat-main .ai-chatbot .chatbot-input {
    max-width: 1032px !important;
  }

  .chat-main .ai-chatbot .ai-chat-input-container .chat-input-wrapper {
    width: 100%;
    max-width: 1000px;
  }

  .chat-main .ai-chatbot .chatbot-input .chat-input-container .chat-input,
  .chat-main .ai-chatbot .ai-chat-input-container .chat-input {
    width: 100%;
    max-width: 1000px !important;
    border-radius: 12px 12px 8px 12px;
    box-shadow: 0 4px 10px 0 #0000001a;
    margin-right: auto;
    margin-left: auto;
  }

  .chat-main .ai-chatbot .chatbot-input .chat-input-container .chat-input:focus-within:not(.is-dragover),
  .chat-main .ai-chatbot .ai-chat-input-container .chat-input:focus-within:not(.is-dragover) {
    background: linear-gradient(#fff, #fff) padding-box, linear-gradient(#6cbaff, #3a84ff) border-box;
  }

  .chat-main .ai-chatbot .chatbot-input .chat-input-container .chat-input:focus-within:not(.is-dragover)::before,
  .chat-main .ai-chatbot .ai-chat-input-container .chat-input:focus-within:not(.is-dragover)::before {
    opacity: 0;
  }

  /* 覆盖 welcome 图片及相关元素尺寸 */
  .chat-main .ai-chatbot .chatbot-welcome .welcome-banner {
    width: 420px;
  }

  .chat-main .ai-chatbot .chatbot-welcome .welcome-content {
    padding-top: 110px;
  }

  .chat-window .session-search .bk-input.bk-input,
  .chat-window .session-edit-input.bk-input.bk-input,
  .chat-window .chat-main-title-input.bk-input.bk-input {
    overflow: hidden;
    background-color: var(--aidev-form-background);
    border-color: var(--aidev-form-border-color);
    border-radius: var(--aidev-radius);
  }

  .chat-window .session-search .bk-input.bk-input:hover,
  .chat-window .session-edit-input.bk-input.bk-input:hover,
  .chat-window .chat-main-title-input.bk-input.bk-input:hover {
    border-color: var(--aidev-form-hover-border-color);
  }

  .chat-window .session-search .bk-input.bk-input.is-focused,
  .chat-window .session-edit-input.bk-input.bk-input.is-focused,
  .chat-window .session-edit-input.bk-input.bk-input:focus-within,
  .chat-window .chat-main-title-input.bk-input.bk-input.is-focused,
  .chat-window .chat-main-title-input.bk-input.bk-input:focus-within {
    border-color: var(--aidev-form-active-border-color);
    box-shadow: none;
  }

  .chat-window .session-search .bk-input.bk-input input,
  .chat-window .session-edit-input.bk-input.bk-input input,
  .chat-window .chat-main-title-input.bk-input.bk-input input {
    color: var(--aidev-form-color);
    background-color: var(--aidev-form-background);
  }

  .chat-window .session-search .bk-input.bk-input input::placeholder {
    color: var(--aidev-form-placeholder-color);
  }

  .chat-window .add-session-btn.bk-button.bk-button {
    height: 32px;
    color: var(--aidev-main-color);
    background-color: var(--aidev-main-background);
    border-color: var(--aidev-form-border-color);
    border-radius: var(--aidev-radius);
  }

  .chat-window .add-session-btn.bk-button.bk-button:hover,
  .chat-window .add-session-btn.bk-button.bk-button:active {
    color: var(--aidev-basic-button-hover-color);
    background-color: var(--aidev-main-background);
    border-color: var(--aidev-form-hover-border-color);
  }

  .chat-window .bk-checkbox {
    color: var(--aidev-main-color);
  }

  .chat-window .bk-checkbox-input.bk-checkbox-input {
    background-color: var(--aidev-checkbox-background);
    border-color: var(--aidev-checkbox-border-color);
    border-radius: var(--aidev-radius-s);
  }

  .chat-window .bk-checkbox:not(.is-disabled):hover .bk-checkbox-input.bk-checkbox-input {
    border-color: var(--aidev-checkbox-hover-border-color);
  }

  .chat-window .bk-checkbox.is-checked:not(.is-disabled) .bk-checkbox-input.bk-checkbox-input,
  .chat-window .bk-checkbox.is-indeterminated:not(.is-disabled) .bk-checkbox-input.bk-checkbox-input {
    background-color: var(--aidev-checkbox-checked-color);
    border-color: var(--aidev-checkbox-checked-color);
  }

  .chat-window .bk-checkbox.is-checked:not(.is-disabled) .bk-checkbox-input::after {
    border-right-color: var(--aidev-checkbox-checked-mark-color);
    border-bottom-color: var(--aidev-checkbox-checked-mark-color);
  }

  .chat-window .bk-checkbox.is-indeterminated:not(.is-disabled) .bk-checkbox-input::after {
    background: var(--aidev-checkbox-checked-mark-color);
  }

  .chat-window .session-footer .bk-button.bk-button {
    border-radius: var(--aidev-radius);
  }

  .chat-window .session-footer .bk-button-primary.bk-button.bk-button:not(.is-disabled) {
    color: var(--aidev-main-button-color);
    background-color: var(--aidev-main-button-background);
    border-color: var(--aidev-main-button-border-color);
    box-shadow: var(--aidev-main-button-box-shadow);
  }

  .chat-window .session-footer .bk-button-primary.bk-button.bk-button:not(.is-disabled):hover {
    background-color: var(--aidev-main-button-hover-background);
    border-color: var(--aidev-main-button-hover-border-color);
  }

  .chat-window .session-footer .bk-button-primary.bk-button.bk-button:not(.is-disabled):active {
    background-color: var(--aidev-main-button-active-background);
    border-color: var(--aidev-main-button-active-border-color);
  }

  .chat-window .session-footer .bk-button.bk-button:not(.bk-button-primary, .is-disabled) {
    color: var(--aidev-main-color);
    background-color: var(--aidev-main-background);
    border-color: var(--aidev-form-border-color);
  }

  .chat-window .session-footer .bk-button.bk-button:not(.bk-button-primary, .is-disabled):hover,
  .chat-window .session-footer .bk-button.bk-button:not(.bk-button-primary, .is-disabled):active {
    color: var(--aidev-basic-button-hover-color);
    background-color: var(--aidev-main-background);
    border-color: var(--aidev-form-hover-border-color);
  }

  .chat-window .bk-resize-layout-aside.bk-resize-layout-aside {
    border-color: transparent;
    border-right-width: 0;
  }

  .chat-window .bk-resize-layout.bk-resize-layout > .bk-resize-layout-aside > .bk-resize-collapse.bk-resize-collapse {
    background: var(--aidev-resize-collapse-background);
    color: var(--aidev-resize-collapse-color);
  }

  .chat-window .bk-resize-layout.bk-resize-layout > .bk-resize-layout-aside > .bk-resize-collapse.bk-resize-collapse:hover {
    background: var(--aidev-clickable-color);
  }

  .chat-window .bk-resize-proxy.left,
  .chat-window .bk-resize-proxy.right {
    border-left-color: var(--aidev-clickable-color);
  }

  .bk-infobox .bk-modal-body {
    border-radius: var(--aidev-radius);
    box-shadow: var(--aidev-dialog-box-shadow);
  }

  .bk-infobox-title {
    color: var(--aidev-title-color);
  }

  .bk-infobox .bk-infobox-content {
    margin: 16px 24px 0;
    padding: 12px 16px;
    color: var(--aidev-main-color);
    background: var(--aidev-assist-content-background);
    border-radius: var(--aidev-radius);
    font-size: 14px;
    line-height: 22px;
  }

  .bk-infobox .bk-dialog-footer,
  .bk-infobox .bk-modal-footer,
  .bk-infobox .bk-infobox-footer {
    background-color: transparent;
    border: 0;
    box-shadow: none;
  }

  .bk-infobox .bk-modal-close {
    color: var(--aidev-assist-color);
    border-radius: var(--aidev-radius);
  }

  .bk-infobox .bk-modal-close:hover {
    color: var(--aidev-main-color);
    background: transparent;
  }

  .bk-infobox .bk-button-primary.bk-button.bk-button:not(.is-disabled) {
    color: var(--aidev-main-button-color);
    background-color: var(--aidev-main-button-background);
    border-color: var(--aidev-main-button-border-color);
    border-radius: var(--aidev-radius);
    box-shadow: var(--aidev-main-button-box-shadow);
  }

  .bk-infobox .bk-button-primary.bk-button.bk-button:not(.is-disabled):hover {
    background-color: var(--aidev-main-button-hover-background);
    border-color: var(--aidev-main-button-hover-border-color);
  }

  .bk-infobox .bk-button-primary.bk-button.bk-button:not(.is-disabled):active {
    background-color: var(--aidev-main-button-active-background);
    border-color: var(--aidev-main-button-active-border-color);
  }

  .bk-infobox .bk-button.bk-button:not(.bk-button-primary, .is-disabled) {
    color: var(--aidev-main-color);
    background-color: var(--aidev-main-background);
    border-color: var(--aidev-form-border-color);
    border-radius: var(--aidev-radius);
  }

  .bk-infobox .bk-button.bk-button:not(.bk-button-primary, .is-disabled):hover,
  .bk-infobox .bk-button.bk-button:not(.bk-button-primary, .is-disabled):active {
    color: var(--aidev-basic-button-hover-color);
    background-color: var(--aidev-main-background);
    border-color: var(--aidev-form-hover-border-color);
  }
</style>
