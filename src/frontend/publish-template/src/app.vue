<template>
  <router-view />
  <AuthorizationSuccessDialog
    :visible="showAuthSuccess"
    @return="handleReturnWeCom"
  />
</template>

<script setup lang="ts">
  import { computed } from "vue"
  import { useRoute, useRouter, type LocationQuery, type LocationQueryValue } from "vue-router"

  import AuthorizationSuccessDialog from "./components/authorization-success-dialog.vue"

  interface WeComWindow extends Window {
    WeixinJSBridge?: {
      call: (method: string) => void
    }
    wx?: {
      closeWindow?: () => void
    }
  }

  const route = useRoute()
  const router = useRouter()

  const showAuthSuccess = computed(() => isAuthorizationSuccess(route.query.authorization))

  function isAuthorizationSuccess(value: LocationQueryValue | LocationQueryValue[]): boolean {
    if (Array.isArray(value)) {
      return value.includes("success")
    }
    return value === "success"
  }

  function closeWeComWindow(): void {
    const host = window as WeComWindow
    if (host.WeixinJSBridge) {
      host.WeixinJSBridge.call("closeWindow")
      return
    }
    if (typeof host.wx?.closeWindow === "function") {
      host.wx.closeWindow()
      return
    }
    window.close()
  }

  async function handleReturnWeCom(): Promise<void> {
    const nextQuery: LocationQuery = { ...route.query }
    delete nextQuery.authorization
    await router.replace({ query: nextQuery })
    closeWeComWindow()
  }
</script>
