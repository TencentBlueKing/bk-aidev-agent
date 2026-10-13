/**
 * 文档站 Mock 的内存存储：按访客（x-mock-client）隔离会话与消息，并设上限防止公网访问撑大内存。
 */
import { createSeedSessions, type MockMessageRecord, type MockSessionRecord } from './mock-fixtures';

export const MOCK_CLIENT_HEADER = 'x-mock-client';
export const DEFAULT_MOCK_CLIENT_ID = 'anonymous';

export const MOCK_STORE_LIMITS = {
  maxClients: 500,
  maxSessionsPerClient: 20,
  maxMessagesPerSession: 60,
} as const;

interface ClientState {
  sessions: Map<string, MockSessionRecord>;
  messages: Map<string, MockMessageRecord[]>;
  /** 收到 stop 的会话；流式循环据此提前结束 */
  stoppedStreams: Set<string>;
}

const clients = new Map<string, ClientState>();
let seq = 1;

export function resolveMockClientId(raw: unknown): string {
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (typeof value !== 'string') return DEFAULT_MOCK_CLIENT_ID;
  const cleaned = value.replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 64);
  return cleaned || DEFAULT_MOCK_CLIENT_ID;
}

export function nextMockId(): string {
  const id = seq;
  seq += 1;
  return String(id);
}

function nowIso(): string {
  return new Date().toISOString();
}

function touchClient(clientId: string, state: ClientState): void {
  clients.delete(clientId);
  clients.set(clientId, state);
}

export function getClientState(clientId: string): ClientState {
  const existing = clients.get(clientId);
  if (existing) {
    touchClient(clientId, existing);
    return existing;
  }
  const state: ClientState = { sessions: new Map(), messages: new Map(), stoppedStreams: new Set() };
  for (const seed of createSeedSessions(nowIso)) {
    state.sessions.set(seed.session.session_code, seed.session);
    state.messages.set(seed.session.session_code, seed.messages);
  }
  clients.set(clientId, state);
  while (clients.size > MOCK_STORE_LIMITS.maxClients) {
    const oldest = clients.keys().next().value;
    if (oldest === undefined) break;
    clients.delete(oldest);
  }
  return state;
}

function withCount(state: ClientState, session: MockSessionRecord): MockSessionRecord {
  return { ...session, session_content_count: state.messages.get(session.session_code)?.length ?? 0 };
}

export function listSessions(clientId: string): MockSessionRecord[] {
  const state = getClientState(clientId);
  return [...state.sessions.values()]
    .filter(s => !s.is_temporary)
    .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
    .map(s => withCount(state, s));
}

export function getSession(clientId: string, sessionCode: string): MockSessionRecord | undefined {
  const state = getClientState(clientId);
  const session = state.sessions.get(sessionCode);
  return session ? withCount(state, session) : undefined;
}

export function upsertSession(clientId: string, input: Partial<MockSessionRecord>): MockSessionRecord {
  const state = getClientState(clientId);
  const sessionCode = input.session_code || `mock_session_${nextMockId()}`;
  const previous = state.sessions.get(sessionCode);
  const time = nowIso();
  const session: MockSessionRecord = {
    ...previous,
    ...input,
    session_code: sessionCode,
    session_name: input.session_name || previous?.session_name || '新会话',
    is_temporary: input.is_temporary ?? previous?.is_temporary ?? false,
    created_at: previous?.created_at || time,
    updated_at: time,
  };
  state.sessions.set(sessionCode, session);
  if (!state.messages.has(sessionCode)) state.messages.set(sessionCode, []);
  while (state.sessions.size > MOCK_STORE_LIMITS.maxSessionsPerClient) {
    const oldest = [...state.sessions.values()].sort((a, b) => (a.updated_at < b.updated_at ? -1 : 1))[0];
    if (!oldest || oldest.session_code === sessionCode) break;
    deleteSession(clientId, oldest.session_code);
  }
  return withCount(state, session);
}

export function deleteSession(clientId: string, sessionCode: string): boolean {
  const state = getClientState(clientId);
  state.messages.delete(sessionCode);
  state.stoppedStreams.delete(sessionCode);
  return state.sessions.delete(sessionCode);
}

export function listMessages(clientId: string, sessionCode: string): MockMessageRecord[] {
  return [...(getClientState(clientId).messages.get(sessionCode) ?? [])];
}

export function appendMessage(clientId: string, message: MockMessageRecord): MockMessageRecord {
  const state = getClientState(clientId);
  const code = message.session_code;
  if (!state.sessions.has(code)) {
    upsertSession(clientId, { session_code: code });
  }
  const list = state.messages.get(code) ?? [];
  list.push(message);
  while (list.length > MOCK_STORE_LIMITS.maxMessagesPerSession) list.shift();
  state.messages.set(code, list);
  const session = state.sessions.get(code);
  if (session) session.updated_at = nowIso();
  return message;
}

export function updateMessage(clientId: string, id: string, patch: Record<string, unknown>): MockMessageRecord | undefined {
  for (const list of getClientState(clientId).messages.values()) {
    const index = list.findIndex(m => m.id === id);
    if (index >= 0) {
      list[index] = { ...list[index], ...patch, id };
      return list[index];
    }
  }
  return undefined;
}

export function deleteMessages(clientId: string, ids: string[]): number {
  const wanted = new Set(ids.map(String));
  let removed = 0;
  for (const [code, list] of getClientState(clientId).messages) {
    const kept = list.filter(m => !wanted.has(m.id));
    removed += list.length - kept.length;
    getClientState(clientId).messages.set(code, kept);
  }
  return removed;
}

export function lastUserMessage(clientId: string, sessionCode: string): MockMessageRecord | undefined {
  const list = getClientState(clientId).messages.get(sessionCode) ?? [];
  for (let i = list.length - 1; i >= 0; i -= 1) {
    if (list[i].role === 'user') return list[i];
  }
  return undefined;
}

export function markStreamStopped(clientId: string, sessionCode: string): void {
  getClientState(clientId).stoppedStreams.add(sessionCode);
}

/** 读取并清除 stop 标记 */
export function consumeStreamStopped(clientId: string, sessionCode: string): boolean {
  const state = getClientState(clientId);
  const stopped = state.stoppedStreams.has(sessionCode);
  if (stopped) state.stoppedStreams.delete(sessionCode);
  return stopped;
}

export function clearStreamStopped(clientId: string, sessionCode: string): void {
  getClientState(clientId).stoppedStreams.delete(sessionCode);
}

/** 仅测试使用 */
export function resetMockStore(): void {
  clients.clear();
  seq = 1;
}
