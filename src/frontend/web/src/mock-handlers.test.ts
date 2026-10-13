import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import type { ServerResponse } from 'node:http';
import { beforeEach, test } from 'node:test';

import { SEED_SESSION_CODE, SQL_COMMAND_ID } from './mock-fixtures';
import { MOCK_STREAM_TIMING, dispatchMockAguiRequest, type MockRequestContext } from './mock-handlers';
import { resetFlowRuns } from './mock-flow';
import { MOCK_STORE_LIMITS, resetMockStore, resolveMockClientId } from './mock-store';

class FakeResponse extends EventEmitter {
  statusCode = 200;
  headers: Record<string, string> = {};
  chunks: string[] = [];
  writableEnded = false;
  destroyed = false;
  headersSent = false;
  socket = null;
  onWrite?: (chunk: string) => void;

  setHeader(key: string, value: string) {
    this.headers[key.toLowerCase()] = value;
  }

  write(chunk: string) {
    this.headersSent = true;
    this.chunks.push(chunk);
    this.onWrite?.(chunk);
    return true;
  }

  end() {
    this.writableEnded = true;
  }

  events(): string[] {
    return this.chunks.map(c => (JSON.parse(c.replace(/^data: /, '').trim()) as { type: string }).type);
  }
}

const asRes = (r: FakeResponse) => r as unknown as ServerResponse;

interface Envelope<T> {
  code: number;
  data: T;
}

async function call<T>(method: string, path: string, body: Record<string, unknown> = {}, ctx: MockRequestContext = { clientId: 'c1' }): Promise<T> {
  const result = await dispatchMockAguiRequest(method, path, body, asRes(new FakeResponse()), ctx);
  assert.equal(result.handled, true, `${method} ${path} should be handled`);
  assert.ok(result.json, `${method} ${path} should return json`);
  assert.equal(result.json.status, 200, `${method} ${path} status`);
  return (result.json.json as Envelope<T>).data;
}

interface SessionLike {
  session_code: string;
  session_name: string;
  session_content_count?: number;
}

beforeEach(() => {
  resetMockStore();
  resetFlowRuns();
  Object.assign(MOCK_STREAM_TIMING, { afterRunStarted: 0, afterTextStart: 0, perChunk: 0, afterTextEnd: 0, beforeFinished: 0, flowStep: 0 });
});

test('agent/info 提供 SQL 报错诊断快捷指令', async () => {
  const info = await call<{ conversation_settings: { commands: { id: string; components: { key: string }[] }[] } }>(
    'GET',
    '/agent/info/',
  );
  const command = info.conversation_settings.commands[0];
  assert.equal(command.id, SQL_COMMAND_ID);
  assert.deepEqual(
    command.components.map(c => c.key),
    ['sql', 'error'],
  );
});

test('会话增删查与消息计数', async () => {
  await call('POST', '/session/', { session_code: 's1', session_name: '新会话' });
  await call('POST', '/session_content/', { session_code: 's1', role: 'user', content: '你好' });
  const list = await call<{ results: SessionLike[] }>('GET', '/session/');
  const s1 = list.results.find(s => s.session_code === 's1');
  assert.equal(s1?.session_content_count, 1);
  assert.equal(list.results[0].session_code, 's1', '最新会话排在最前');

  const messages = await call<unknown[]>('GET', '/session_content/content/', {}, { clientId: 'c1', query: { session_code: 's1' } });
  assert.equal(messages.length, 1);

  await call('DELETE', '/session/s1/');
  const after = await call<{ results: SessionLike[] }>('GET', '/session/');
  assert.equal(after.results.some(s => s.session_code === 's1'), false);
});

test('GET 请求的 query 通过 ctx 传入', async () => {
  const result = await dispatchMockAguiRequest('GET', '/session_content/content/', {}, asRes(new FakeResponse()), {
    clientId: 'c1',
    query: { session_code: SEED_SESSION_CODE },
  });
  assert.equal(((result.json?.json as Envelope<unknown[]>).data).length, 2);
});

test('临时会话不出现在列表中', async () => {
  await call('POST', '/session/', { session_code: 'tmp', is_temporary: true });
  const list = await call<{ results: SessionLike[] }>('GET', '/session/');
  assert.equal(list.results.some(s => s.session_code === 'tmp'), false);
});

test('不同访客互不可见', async () => {
  await call('POST', '/session/', { session_code: 'mine' }, { clientId: 'alice' });
  const bob = await call<{ results: SessionLike[] }>('GET', '/session/', {}, { clientId: 'bob' });
  assert.equal(bob.results.some(s => s.session_code === 'mine'), false);
});

test('预置会话带 2 条历史消息', async () => {
  const session = await call<SessionLike>('GET', `/session/${SEED_SESSION_CODE}/`);
  assert.equal(session.session_name, '上周容量评估');
  assert.equal(session.session_content_count, 2);
});

test('会话数超过上限时淘汰最早的会话', async () => {
  for (let i = 0; i < MOCK_STORE_LIMITS.maxSessionsPerClient + 3; i += 1) {
    await call('POST', '/session/', { session_code: `s${i}` });
    await new Promise(r => setTimeout(r, 2));
  }
  const list = await call<{ results: SessionLike[] }>('GET', '/session/');
  assert.ok(list.results.length <= MOCK_STORE_LIMITS.maxSessionsPerClient);
  assert.equal(list.results.some(s => s.session_code === 's0'), false);
});

test('chat_completion 按 AG-UI 顺序推流，并写入助手消息', async () => {
  await call('POST', '/session_content/', { session_code: 's2', role: 'user', content: '请诊断告警「CPU」' });
  const res = new FakeResponse();
  const result = await dispatchMockAguiRequest('POST', '/chat_completion/', { session_code: 's2' }, asRes(res), { clientId: 'c1' });
  assert.equal(result.handled, true);
  const types = res.events();
  assert.equal(types[0], 'RUN_STARTED');
  assert.equal(types[1], 'TEXT_MESSAGE_START');
  assert.ok(types.filter(t => t === 'TEXT_MESSAGE_CHUNK').length > 3);
  assert.deepEqual(types.slice(-2), ['TEXT_MESSAGE_END', 'RUN_FINISHED']);
  assert.equal(res.headers['content-type'], 'text/event-stream; charset=utf-8');

  const messages = await call<{ role: string; status: string }[]>('GET', '/session_content/content/', {}, {
    clientId: 'c1',
    query: { session_code: 's2' },
  });
  assert.equal(messages.at(-1)?.role, 'assistant');
  assert.equal(messages.at(-1)?.status, 'complete');
});

test('stop 后流提前结束，助手消息标记为 stop', async () => {
  await call('POST', '/session_content/', { session_code: 's3', role: 'user', content: '请诊断告警「CPU」' });
  const res = new FakeResponse();
  let stopped = false;
  res.onWrite = chunk => {
    if (!stopped && chunk.includes('TEXT_MESSAGE_CHUNK')) {
      stopped = true;
      void dispatchMockAguiRequest('POST', '/session_content/stop/', { session_code: 's3' }, asRes(new FakeResponse()), {
        clientId: 'c1',
      });
    }
  };
  await dispatchMockAguiRequest('POST', '/chat_completion/', { session_code: 's3' }, asRes(res), { clientId: 'c1' });
  assert.equal(res.events().includes('RUN_FINISHED'), false);

  const messages = await call<{ role: string; status: string }[]>('GET', '/session_content/content/', {}, {
    clientId: 'c1',
    query: { session_code: 's3' },
  });
  assert.equal(messages.at(-1)?.status, 'stop');
});

test('快捷指令消息得到包含字段长度的回复', async () => {
  await call('POST', '/session_content/', {
    session_code: 's4',
    role: 'user',
    content: 'SQL 报错诊断',
    property: {
      extra: {
        command: SQL_COMMAND_ID,
        context: [
          { __key: 'sql', __value: 'SELECT 1' },
          { __key: 'error', __value: 'boom' },
        ],
      },
    },
  });
  const res = new FakeResponse();
  await dispatchMockAguiRequest('POST', '/chat_completion/', { session_code: 's4' }, asRes(res), { clientId: 'c1' });
  const text = res.chunks
    .map(c => JSON.parse(c.replace(/^data: /, '').trim()) as { type: string; delta?: string })
    .filter(e => e.type === 'TEXT_MESSAGE_CHUNK')
    .map(e => e.delta)
    .join('');
  assert.match(text, /SQL 8 字，报错 4 字/);
});

const textOf = (res: FakeResponse) =>
  res.chunks
    .map(c => JSON.parse(c.replace(/^data: /, '').trim()) as { type: string; delta?: string })
    .filter(e => e.type === 'TEXT_MESSAGE_CHUNK')
    .map(e => e.delta)
    .join('');

test('故障注入：agent_info / session_content 500 与 all:401', async () => {
  const info = await dispatchMockAguiRequest('GET', '/agent/info/', {}, asRes(new FakeResponse()), {
    clientId: 'c1',
    fault: 'agent_info:500',
  });
  assert.equal(info.json?.status, 500);

  const sessions = await dispatchMockAguiRequest('GET', '/session/', {}, asRes(new FakeResponse()), {
    clientId: 'c1',
    fault: 'agent_info:500',
  });
  assert.equal(sessions.json?.status, 200, '只影响目标接口');

  const write = await dispatchMockAguiRequest('POST', '/session_content/', { session_code: 's', role: 'user', content: 'x' }, asRes(new FakeResponse()), {
    clientId: 'c1',
    fault: 'session_content:500',
  });
  assert.equal(write.json?.status, 500);

  const any = await dispatchMockAguiRequest('GET', '/llms/', {}, asRes(new FakeResponse()), { clientId: 'c1', fault: 'all:401' });
  assert.equal(any.json?.status, 401);

  const unknown = await dispatchMockAguiRequest('GET', '/agent/info/', {}, asRes(new FakeResponse()), { clientId: 'c1', fault: 'nope' });
  assert.equal(unknown.json?.status, 200, '未知故障忽略');
});

test('故障注入：stream:run_error 推送若干 chunk 后发送 RUN_ERROR', async () => {
  await call('POST', '/session_content/', { session_code: 's5', role: 'user', content: '请诊断告警「CPU」' });
  const res = new FakeResponse();
  await dispatchMockAguiRequest('POST', '/chat_completion/', { session_code: 's5' }, asRes(res), {
    clientId: 'c1',
    fault: 'stream:run_error',
  });
  const types = res.events();
  assert.equal(types.at(-1), 'RUN_ERROR');
  assert.equal(types.includes('RUN_FINISHED'), false);
  assert.ok(types.filter(t => t === 'TEXT_MESSAGE_CHUNK').length > 0);
});

test('智能体档案：~data 前缀返回数据助手，会话与默认档案隔离', async () => {
  const info = await call<{ agent_name: string }>('GET', '/~data/agent/info/');
  assert.equal(info.agent_name, '数据助手 Demo');
  await call('POST', '/~data/session/', { session_code: 'only-data' });
  const data = await call<{ results: SessionLike[] }>('GET', '/~data/session/');
  const def = await call<{ results: SessionLike[] }>('GET', '/session/');
  assert.equal(data.results.some(s => s.session_code === 'only-data'), true);
  assert.equal(def.results.some(s => s.session_code === 'only-data'), false);
});

test('回复回显消息上下文 context', async () => {
  await call('POST', '/session_content/', {
    session_code: 's6',
    role: 'user',
    content: '这台主机怎么了？',
    property: { extra: { context: [{ __key: 'biz_id', __value: 2 }, { host: '10.0.0.12' }] } },
  });
  const res = new FakeResponse();
  await dispatchMockAguiRequest('POST', '/chat_completion/', { session_code: 's6' }, asRes(res), { clientId: 'c1' });
  assert.match(textOf(res), /收到上下文：biz_id=2，host=10\.0\.0\.12/);
});

test('关键词回复：图表 / 代码', async () => {
  for (const [question, expected] of [
    ['要一张图表', /```custom-component\n\{"type":"chart"/],
    ['给我一段代码', /```ts\nexport async function fetchWithTimeout/],
  ] as const) {
    const code = `kw-${question}`;
    await call('POST', '/session_content/', { session_code: code, role: 'user', content: question });
    const res = new FakeResponse();
    await dispatchMockAguiRequest('POST', '/chat_completion/', { session_code: code }, asRes(res), { clientId: 'c1' });
    assert.match(textOf(res), expected);
  }
});

interface FlowEvent {
  type: string;
  name?: string;
  value?: { task_id: number; task_state?: string; nodes?: Record<string, { state: string; retry: number }>; statistics?: { total: number }; task_outputs?: string[] }[];
}

const flowEvents = (res: FakeResponse): FlowEvent[] => res.chunks.map(c => JSON.parse(c.replace(/^data: /, '').trim()) as FlowEvent);
const runFlow = async (session: string) => {
  const res = new FakeResponse();
  await dispatchMockAguiRequest('POST', '/~flow/chat_completion/', { session_code: session }, asRes(res), { clientId: 'c1' });
  return flowEvents(res);
};

test('流程智能体：首次运行在「磁盘检查」失败，value 均为数组', async () => {
  const events = await runFlow('f1');
  assert.equal(events[0].type, 'RUN_STARTED');
  assert.equal(events[1].name, 'flow_agent_start');
  assert.ok(events.every(e => e.type !== 'CUSTOM' || Array.isArray(e.value)));
  const results = events.filter(e => e.name === 'flow_agent_result');
  assert.ok(results.length >= 3, '逐步推送多次 result');
  const last = results.at(-1)?.value?.[0];
  assert.equal(last?.task_state, 'FAILED');
  assert.equal(last?.nodes?.n_check_disk.state, 'FAILED');
  assert.equal(last?.nodes?.n_notify.state, 'PENDING');
  assert.equal(last?.statistics?.total, 4);
  assert.match(events.find(e => e.name === 'flow_agent_end')?.value?.[0].task_outputs?.[0] ?? '', /磁盘检查/);
  assert.equal(events.at(-1)?.type, 'RUN_FINISHED');
});

test('流程智能体：重试后以 flow_agent_restart 续跑到完成，并更新会话中的活动消息', async () => {
  const first = await runFlow('f2');
  const taskId = first[1].value?.[0].task_id ?? 0;
  await call('POST', '/~flow/user_operation/', { session_code: 'f2', operation: 'flow_node_retry', payload: { node_id: 'n_check_disk', task_id: String(taskId) } });
  const second = await runFlow('f2');
  assert.equal(second[1].name, 'flow_agent_restart');
  assert.equal(second[1].value?.[0].task_id, taskId);
  const last = second.filter(e => e.name === 'flow_agent_result').at(-1)?.value?.[0];
  assert.equal(last?.task_state, 'FINISHED');
  assert.equal(last?.nodes?.n_check_disk.state, 'FINISHED');
  assert.equal(last?.nodes?.n_check_disk.retry, 1);

  const messages = await call<{ role: string; content: { task_state: string }[] }[]>('GET', '/~flow/session_content/content/', {}, {
    clientId: 'c1',
    query: { session_code: 'f2' },
  });
  const activities = messages.filter(m => m.role === 'activity');
  assert.equal(activities.length, 1, '同一任务只保留一条活动消息');
  assert.equal(activities[0].content[0].task_state, 'FINISHED');
});

test('流程智能体：跳过后失败节点为 SKIPPED，任务完成', async () => {
  await runFlow('f3');
  await call('POST', '/~flow/user_operation/', { session_code: 'f3', operation: 'flow_node_skip', payload: { node_id: 'n_check_disk' } });
  const events = await runFlow('f3');
  const last = events.filter(e => e.name === 'flow_agent_result').at(-1)?.value?.[0];
  assert.equal(last?.nodes?.n_check_disk.state, 'SKIPPED');
  assert.equal(last?.task_state, 'FINISHED');
});

test('流程智能体：task_node_info 返回节点详情，失败节点带错误输出', async () => {
  const first = await runFlow('f4');
  const taskId = first[1].value?.[0].task_id ?? 0;
  const info = await call<{ node_id: string; basic_info: { node_name: string }; outputs: { key: string; value: unknown }[] }>(
    'GET',
    `/~flow/flow_agent/${taskId}/task_node_info/n_check_disk/`,
  );
  assert.equal(info.basic_info.node_name, '磁盘检查');
  assert.ok(info.outputs.some(o => o.key === 'ex_data'));
  const agent = await call<{ agent_name: string }>('GET', '/~flow/agent/info/');
  assert.equal(agent.agent_name, '巡检流程助手 Demo');
});

test('未知路由不处理', async () => {
  const result = await dispatchMockAguiRequest('GET', '/nope/', {}, asRes(new FakeResponse()), { clientId: 'c1' });
  assert.equal(result.handled, false);
});

test('resolveMockClientId 清洗输入', () => {
  assert.equal(resolveMockClientId(undefined), 'anonymous');
  assert.equal(resolveMockClientId('ab c/../d'), 'abcd');
  assert.equal(resolveMockClientId(['x1', 'x2']), 'x1');
  assert.equal(resolveMockClientId('a'.repeat(100)).length, 64);
});
