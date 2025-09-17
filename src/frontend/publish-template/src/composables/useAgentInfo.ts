import router from "../router"

interface AgentInfo {
  conversation_settings?: {
    enable_chat_session?: boolean
  }
  [key: string]: any
}

/**
 * 获取Agent信息的公共函数
 * @param url - 请求的URL前缀
 * @returns 返回Agent信息或null（当失败时）
 */
export const fetchAgentInfo = async (url: string): Promise<AgentInfo | null> => {
  try {
    const response = await fetch(`${url}/agent/info/`, {
      credentials: "include", // 包含Cookie等凭证信息
    })

    // 检查 HTTP 状态码，fetch 不会为 4xx/5xx 状态码抛出异常
    if (!response.ok && response.status === 403) {
      router.push("/403")
      throw new Error(`HTTP Error: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    return data.data
  } catch (error) {
    console.error("获取Agent信息失败:", error)
    return null
  }
}
