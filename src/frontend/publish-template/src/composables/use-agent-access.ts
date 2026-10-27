import { reactive } from "vue"

import type { AgentAccessData, AgentAccessSnapshot, AgentAccessStatus, ApplyAccessResult } from "../types/agent-access"

const ACCESS_STATUSES: readonly AgentAccessStatus[] = [
  "authorized",
  "unauthorized",
  "authorization_pending",
  "authorization_rejected",
]

const accessState = reactive<AgentAccessSnapshot>({
  phase: "idle",
  status: null,
  applyUrl: null,
  rejectReason: "",
  errorMessage: "",
})

let requestSeq = 0
let inflight: Promise<void> | null = null

function joinUrl(base: string, path: string): string {
  const left = base.trim().replace(/\/+$/, "")
  const right = path.trim().replace(/^\/+/, "")
  if (!left) {
    return `/${right}`
  }
  return `${left}/${right}`
}

/** 与 agent/info 相同，挂在 BK_API_PREFIX 下：agent/access/、agent/access/apply/。 */
function accessStatusUrl(): string {
  return joinUrl(window.BK_API_PREFIX || "", "agent/access/")
}

function accessApplyUrl(): string {
  return joinUrl(accessStatusUrl(), "apply/")
}

function buildHeaders(jsonBody: boolean): Record<string, string> {
  const headers: Record<string, string> = {}
  if (jsonBody) {
    headers["Content-Type"] = "application/json"
  }
  const username = window.BK_USER_NAME?.trim()
  if (username) {
    headers["X-BKAIDEV-USER"] = username
  }
  return headers
}

function isAgentAccessStatus(value: unknown): value is AgentAccessStatus {
  return typeof value === "string" && (ACCESS_STATUSES as readonly string[]).includes(value)
}

function readMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") {
    return fallback
  }
  const body = payload as {
    message?: unknown
    error?: { message?: unknown }
  }
  if (typeof body.error?.message === "string" && body.error.message.trim()) {
    return body.error.message
  }
  if (typeof body.message === "string" && body.message.trim() && body.message !== "ok") {
    return body.message
  }
  return fallback
}

async function parseJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return null
  }
}

function parseAccessData(payload: unknown): AgentAccessData {
  if (!payload || typeof payload !== "object") {
    throw new Error("权限状态获取失败")
  }
  const body = payload as { result?: unknown; data?: unknown }
  if (body.result === false) {
    throw new Error(readMessage(payload, "权限状态获取失败"))
  }
  const data = body.data
  if (!data || typeof data !== "object") {
    throw new Error("权限状态获取失败")
  }
  const record = data as { status?: unknown; apply_url?: unknown; reject_reason?: unknown }
  if (!isAgentAccessStatus(record.status)) {
    throw new Error("权限状态获取失败")
  }
  const applyUrl = typeof record.apply_url === "string" && record.apply_url.trim() ? record.apply_url : null
  const rejectReason = typeof record.reject_reason === "string" ? record.reject_reason.trim() : ""
  return {
    status: record.status,
    applyUrl,
    rejectReason,
  }
}

function parseApplyUrl(payload: unknown): string {
  if (!payload || typeof payload !== "object") {
    throw new Error("申请提交失败")
  }
  const body = payload as { result?: unknown; data?: unknown }
  if (body.result === false) {
    throw new Error(readMessage(payload, "申请提交失败"))
  }
  const data = body.data
  if (!data || typeof data !== "object") {
    throw new Error("申请提交失败")
  }
  const applyUrl = (data as { apply_url?: unknown }).apply_url
  if (typeof applyUrl !== "string" || !applyUrl.trim()) {
    throw new Error("申请提交失败")
  }
  return applyUrl
}

async function requestAccess(): Promise<AgentAccessData> {
  const response = await fetch(accessStatusUrl(), {
    method: "GET",
    credentials: "include",
    headers: buildHeaders(false),
  })
  const payload = await parseJson(response)
  if (!response.ok) {
    throw new Error(readMessage(payload, "权限状态获取失败"))
  }
  return parseAccessData(payload)
}

async function requestApply(): Promise<string> {
  const response = await fetch(accessApplyUrl(), {
    method: "POST",
    credentials: "include",
    headers: buildHeaders(true),
    body: "{}",
  })
  const payload = await parseJson(response)
  if (!response.ok) {
    throw new Error(readMessage(payload, "申请提交失败"))
  }
  return parseApplyUrl(payload)
}

const CHAT_DENIED_MARK = "bk-agent-access-chat-denied"

/** 聊天接口刚因 403 离开过。用来挡住「GET 已授权但聊天权限缓存仍 403」时的来回跳转。 */
export function markChatAccessDenied(): void {
  try {
    sessionStorage.setItem(CHAT_DENIED_MARK, "1")
  } catch {
    // 隐私模式可能禁用 sessionStorage
  }
}

export function hasChatAccessDenied(): boolean {
  try {
    return sessionStorage.getItem(CHAT_DENIED_MARK) === "1"
  } catch {
    return false
  }
}

export function clearChatAccessDenied(): void {
  try {
    sessionStorage.removeItem(CHAT_DENIED_MARK)
  } catch {
    // 隐私模式可能禁用 sessionStorage
  }
}

/** 丢弃已缓存的授权状态。聊天接口 403 后调用，让拦截页重新查询。 */
export function invalidateAgentAccess(): void {
  requestSeq += 1
  inflight = null
  accessState.phase = "idle"
  accessState.status = null
  accessState.applyUrl = null
  accessState.rejectReason = ""
  accessState.errorMessage = ""
}

/**
 * 查询访问者授权状态。
 * 落地页与拦截页共用同一次结果；force 为 true 时忽略缓存重新请求。
 */
export async function loadAgentAccess(force = false): Promise<void> {
  if (!force && (accessState.phase === "ready" || accessState.phase === "error")) {
    return
  }
  if (!force && inflight) {
    return inflight
  }

  const seq = ++requestSeq
  accessState.phase = "loading"
  accessState.errorMessage = ""

  const task = (async () => {
    try {
      const data = await requestAccess()
      if (seq !== requestSeq) {
        return
      }
      accessState.status = data.status
      accessState.applyUrl = data.applyUrl
      accessState.rejectReason = data.rejectReason
      accessState.errorMessage = ""
      accessState.phase = "ready"
    } catch (error: unknown) {
      if (seq !== requestSeq) {
        return
      }
      accessState.status = null
      accessState.applyUrl = null
      accessState.rejectReason = ""
      accessState.errorMessage = error instanceof Error ? error.message : "权限状态获取失败"
      accessState.phase = "error"
    } finally {
      if (inflight === task) {
        inflight = null
      }
    }
  })()

  inflight = task
  return task
}

/** unauthorized 与 authorization_rejected 都走这个申请。成功后切到 authorization_pending。 */
export async function applyAgentAccess(): Promise<ApplyAccessResult> {
  try {
    const applyUrl = await requestApply()
    accessState.phase = "ready"
    accessState.status = "authorization_pending"
    accessState.applyUrl = applyUrl
    accessState.rejectReason = ""
    accessState.errorMessage = ""
    return {
      ok: true,
      applyUrl,
      message: "",
    }
  } catch (error: unknown) {
    return {
      ok: false,
      applyUrl: "",
      message: error instanceof Error ? error.message : "申请提交失败",
    }
  }
}

export function useAgentAccess(): { accessState: AgentAccessSnapshot } {
  return { accessState }
}
