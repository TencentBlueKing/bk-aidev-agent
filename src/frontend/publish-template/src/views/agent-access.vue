<template>
  <div
    v-if="viewMode === 'loading'"
    class="access-page"
    v-bkloading="{
      loading: true,
      theme: 'primary',
      mode: 'spin',
    }"
  />
  <main
    v-else
    class="access-page"
  >
    <AgentAccessCard v-if="viewMode === 'confirm'">
      <h1 class="access-title access-title-confirm">智能体申请确认</h1>
      <p class="access-summary">
        以 <strong>{{ userName || "—" }}</strong> 身份申请使用智能体 <strong>{{ agentName || "—" }}</strong> 及其关联的所有资源
      </p>
      <AgentAccessIdentity />
      <template #actions>
        <AgentAccessButton
          theme="primary"
          :loading="submitting"
          @click="handleApply"
        >
          提交申请
        </AgentAccessButton>
      </template>
    </AgentAccessCard>

    <AgentAccessCard v-else-if="viewMode === 'submitted'">
      <AgentAccessStatusIcon type="success" />
      <h1 class="access-title">申请已经提交</h1>
      <p class="access-hint">
        可点击“<a
          v-if="accessState.applyUrl"
          class="ticket-link"
          :href="accessState.applyUrl"
          target="_blank"
          rel="noopener noreferrer"
        >单据详情</a><span
          v-else
          class="ticket-link"
        >单据详情</span>”查看进度
      </p>
      <template #actions>
        <AgentAccessButton @click="handleClosePage">关闭</AgentAccessButton>
      </template>
    </AgentAccessCard>

    <AgentAccessCard v-else-if="viewMode === 'rejected'">
      <AgentAccessStatusIcon type="error" />
      <h1 class="access-title">申请已被拒绝</h1>
      <p class="access-hint">
        <span v-if="accessState.rejectReason">{{ accessState.rejectReason }}</span>
        <template v-if="accessState.rejectReason"><br /></template>
        可点击“<a
          v-if="accessState.applyUrl"
          class="ticket-link"
          :href="accessState.applyUrl"
          target="_blank"
          rel="noopener noreferrer"
        >单据详情</a><span
          v-else
          class="ticket-link"
        >单据详情</span>”查看
      </p>
      <template #actions>
        <AgentAccessButton
          theme="primary"
          :loading="submitting"
          @click="handleApply"
        >
          重新申请
        </AgentAccessButton>
      </template>
    </AgentAccessCard>

    <AgentAccessCard v-else-if="viewMode === 'submit-failed'">
      <AgentAccessStatusIcon type="error" />
      <h1 class="access-title">申请提交失败</h1>
      <p class="access-hint">{{ submitErrorMessage }}</p>
      <template #actions>
        <AgentAccessButton @click="handleCloseSubmitFailed">关闭</AgentAccessButton>
      </template>
    </AgentAccessCard>

    <AgentAccessCard v-else>
      <AgentAccessStatusIcon type="error" />
      <h1 class="access-title">权限状态获取失败</h1>
      <p class="access-hint">{{ accessState.errorMessage || "权限状态获取失败" }}</p>
      <template #actions>
        <AgentAccessButton
          theme="primary"
          :loading="retrying"
          @click="handleRetry"
        >
          重试
        </AgentAccessButton>
      </template>
    </AgentAccessCard>
  </main>
</template>

<script setup lang="ts">
  import { computed, onMounted, ref } from "vue"
  import { useRoute, useRouter } from "vue-router"

  import AgentAccessButton from "../components/agent-access-button.vue"
  import AgentAccessCard from "../components/agent-access-card.vue"
  import AgentAccessIdentity from "../components/agent-access-identity.vue"
  import AgentAccessStatusIcon from "../components/agent-access-status-icon.vue"
  import { applyAgentAccess, clearChatAccessDenied, loadAgentAccess, useAgentAccess } from "../composables/use-agent-access"

  const route = useRoute()
  const router = useRouter()
  const { accessState } = useAgentAccess()

  const userName = window.BK_USER_NAME || ""
  const agentName = window.BK_AGENT_NAME || ""
  const submitting = ref(false)
  const retrying = ref(false)
  const submitFailed = ref(false)
  const submitErrorMessage = ref("")

  const viewMode = computed(() => {
    if (submitFailed.value) {
      return "submit-failed"
    }
    if (accessState.phase === "idle" || accessState.phase === "loading") {
      return "loading"
    }
    if (accessState.phase === "error") {
      return "query-failed"
    }
    if (accessState.status === "authorized") {
      return "loading"
    }
    if (accessState.status === "authorization_pending") {
      return "submitted"
    }
    if (accessState.status === "authorization_rejected") {
      return "rejected"
    }
    return "confirm"
  })

  async function redirectIfAuthorized(): Promise<boolean> {
    if (accessState.status !== "authorized") {
      clearChatAccessDenied()
      return false
    }
    await router.replace({
      name: "chat-window",
      query: route.query,
    })
    return true
  }

  onMounted(async () => {
    await loadAgentAccess()
    await redirectIfAuthorized()
  })

  function canSubmitApply(): boolean {
    return accessState.status === "unauthorized" || accessState.status === "authorization_rejected"
  }

  async function handleApply(): Promise<void> {
    if (submitting.value || !canSubmitApply()) {
      return
    }
    submitting.value = true
    try {
      const result = await applyAgentAccess()
      if (!result.ok) {
        submitErrorMessage.value = result.message || "申请提交失败"
        submitFailed.value = true
      }
    } finally {
      submitting.value = false
    }
  }

  function handleCloseSubmitFailed(): void {
    submitFailed.value = false
    submitErrorMessage.value = ""
  }

  function handleClosePage(): void {
    window.close()
  }

  async function handleRetry(): Promise<void> {
    if (retrying.value) {
      return
    }
    retrying.value = true
    try {
      await loadAgentAccess(true)
      await redirectIfAuthorized()
    } finally {
      retrying.value = false
    }
  }
</script>

<style lang="postcss" scoped>
  .access-page {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100vh;
    background: #f5f7fa;
  }

  .access-title {
    width: 100%;
    margin: 0;
    font-size: 20px;
    font-weight: 400;
    line-height: 28px;
    color: #111214;
    text-align: center;
  }

  .access-title-confirm {
    padding: 16px 0 20px;
  }

  .access-summary {
    width: 100%;
    margin: 0;
    font-size: 14px;
    line-height: 22px;
    color: #4a5973;
    text-align: center;
    word-break: break-word;
  }

  .access-summary strong {
    font-weight: 700;
    color: #3b6ef5;
  }

  .access-hint {
    align-self: stretch;
    width: 100%;
    box-sizing: border-box;
    margin: 0;
    padding: 16px;
    background: #f7f9fd;
    font-size: 14px;
    line-height: 22px;
    color: #4a5973;
    text-align: center;
    word-break: break-word;
  }

  .ticket-link {
    color: #3b6ef5;
    text-decoration: none;
  }
</style>
