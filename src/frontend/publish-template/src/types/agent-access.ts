/** 插件 GET {BK_API_PREFIX}/agent/access/ 的授权状态 */
export type AgentAccessStatus = "authorized" | "unauthorized" | "authorization_pending" | "authorization_rejected"

export interface AgentAccessData {
  status: AgentAccessStatus
  applyUrl: string | null
  rejectReason: string
}

/** 落地页与拦截页共享的查询结果 */
export interface AgentAccessSnapshot {
  phase: "idle" | "loading" | "ready" | "error"
  status: AgentAccessStatus | null
  applyUrl: string | null
  rejectReason: string
  errorMessage: string
}

export interface ApplyAccessResult {
  ok: boolean
  applyUrl: string
  message: string
}
