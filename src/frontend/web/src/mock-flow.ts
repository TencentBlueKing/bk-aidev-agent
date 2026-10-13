/**
 * 文档站 Mock：流程智能体（路径前缀 ~flow/）。
 * 事件格式依据真实采集：flow_agent_* 的 value 均为任务数组，task_id 为数字，状态为 BKFlow 大写，result 携带 statistics。
 */
import type { MockMessageRecord } from './mock-fixtures';

export const FLOW_PROFILE = 'flow';

export const MOCK_FLOW_AGENT_INFO = {
  agent_name: '巡检流程助手 Demo',
  agent_type: 'single',
  conversation_settings: {
    opening_remark: '你好，我是巡检流程助手（Mock）。发送任意消息即可启动一次 4 节点巡检流程。',
    predefined_questions: ['开始巡检 10.0.0.12'],
    enable_chat_session: true,
    enable_word_selection_popup: false,
    commands: [],
  },
};

export type FlowNodeState = 'PENDING' | 'RUNNING' | 'FINISHED' | 'FAILED' | 'SKIPPED';
export type FlowOperation = 'flow_node_retry' | 'flow_node_skip';

interface FlowNodeDef {
  id: string;
  name: string;
  inputs: Record<string, unknown>;
  outputKey: string;
  outputName: string;
  okValue: string;
  failValue?: string;
}

/** 4 个节点；磁盘检查首次运行失败 */
export const FLOW_NODES: FlowNodeDef[] = [
  { id: 'n_collect_metrics', name: '采集指标', inputs: { host: '10.0.0.12', metrics: ['cpu', 'mem', 'disk'] }, outputKey: 'sample_count', outputName: '采集样本数', okValue: '1440' },
  {
    id: 'n_check_disk',
    name: '磁盘检查',
    inputs: { host: '10.0.0.12', mount: '/data', threshold: 90 },
    outputKey: 'disk_usage',
    outputName: '磁盘使用率',
    okValue: '78%（已清理日志）',
    failValue: '96%，超过阈值 90%',
  },
  { id: 'n_build_report', name: '生成报告', inputs: { template: 'daily-inspection' }, outputKey: 'report_url', outputName: '报告地址', okValue: 'https://example.com/reports/1024' },
  { id: 'n_notify', name: '发送通知', inputs: { channel: '企业微信', receivers: ['运维值班'] }, outputKey: 'notified', outputName: '通知人数', okValue: '3' },
];

const FAILING_NODE = 'n_check_disk';

interface NodeRuntime {
  state: FlowNodeState;
  start: string;
  finish: string;
  elapsed: number;
  retry: number;
}

interface FlowRun {
  taskId: number;
  taskName: string;
  nodes: Record<string, NodeRuntime>;
  pending?: { operation: FlowOperation; nodeId: string };
}

export interface FlowFrame {
  /** 推送前等待的毫秒数 */
  wait: number;
  event: Record<string, unknown>;
}

const MAX_RUNS = 1000;
const runs = new Map<string, FlowRun>();
let taskSeq = 87000;

/** BKFlow 的时间格式：2026-10-09 17:07:28 +0800 */
export function formatFlowTime(date: Date): string {
  const shifted = new Date(date.getTime() + 8 * 3600 * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())} ` +
    `${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}:${pad(shifted.getUTCSeconds())} +0800`
  );
}

const runKey = (clientId: string, sessionCode: string) => `${clientId}::${sessionCode}`;

function remember(key: string, run: FlowRun) {
  runs.delete(key);
  runs.set(key, run);
  while (runs.size > MAX_RUNS) {
    const oldest = runs.keys().next().value;
    if (oldest === undefined) break;
    runs.delete(oldest);
  }
}

/** 当前运行状态 → flow_agent_result 的任务数组 */
export function toTaskValue(run: FlowRun, taskState: string, outputs: string[] = ['']) {
  const nodes = Object.fromEntries(
    FLOW_NODES.map(def => {
      const rt = run.nodes[def.id];
      return [
        def.id,
        {
          id: def.id,
          name: def.name,
          type: 'ServiceActivity',
          state: rt.state,
          start_time: rt.start,
          finish_time: rt.finish,
          elapsed_time: rt.elapsed,
          loop: 1,
          retry: rt.retry,
          skip: rt.state === 'SKIPPED',
          retryable: true,
          skippable: true,
        },
      ];
    }),
  );
  const stateCounts: Record<string, number> = {};
  for (const def of FLOW_NODES) {
    const s = run.nodes[def.id].state;
    stateCounts[s] = (stateCounts[s] ?? 0) + 1;
  }
  return [
    {
      task_id: run.taskId,
      task_name: run.taskName,
      task_state: taskState,
      nodes,
      statistics: { total: FLOW_NODES.length, state_counts: stateCounts },
      task_outputs: outputs,
    },
  ];
}

const custom = (name: string, value: unknown) => ({ type: 'CUSTOM', name, value });

function setNode(run: FlowRun, id: string, state: FlowNodeState, now: Date) {
  const rt = run.nodes[id];
  if (state === 'RUNNING') {
    rt.start = formatFlowTime(now);
    rt.finish = '';
    rt.elapsed = 0;
  }
  if (state === 'FINISHED' || state === 'FAILED' || state === 'SKIPPED') {
    if (!rt.start) rt.start = formatFlowTime(now);
    rt.finish = formatFlowTime(now);
    rt.elapsed = 1;
  }
  rt.state = state;
}

/**
 * 生成本次 chat_completion 的事件帧：首次运行在「磁盘检查」失败；记录了重试 / 跳过操作时续跑到完成。
 * step 为节点推进间隔（毫秒），测试中可置零。
 */
export function planFlowFrames(clientId: string, sessionCode: string, step: number, now: () => Date = () => new Date()): {
  frames: FlowFrame[];
  run: FlowRun;
  restarted: boolean;
} {
  const key = runKey(clientId, sessionCode);
  const existing = runs.get(key);
  const threadId = `thread-${sessionCode}`;
  const runId = `run-${Date.now()}`;
  const frames: FlowFrame[] = [{ wait: 0, event: { type: 'RUN_STARTED', threadId, runId } }];
  const push = (wait: number, event: Record<string, unknown>) => frames.push({ wait, event });

  if (existing?.pending) {
    const run = existing;
    const { operation, nodeId } = run.pending as { operation: FlowOperation; nodeId: string };
    run.pending = undefined;
    push(0, custom('flow_agent_restart', [{ task_id: run.taskId }]));
    if (operation === 'flow_node_skip') {
      setNode(run, nodeId, 'SKIPPED', now());
    } else {
      run.nodes[nodeId].retry += 1;
      setNode(run, nodeId, 'RUNNING', now());
    }
    push(step / 2, custom('flow_agent_result', toTaskValue(run, 'RUNNING')));
    if (operation === 'flow_node_retry') {
      setNode(run, nodeId, 'FINISHED', now());
      push(step, custom('flow_agent_result', toTaskValue(run, 'RUNNING')));
    }
    const rest = FLOW_NODES.map(n => n.id).filter(id => run.nodes[id].state === 'PENDING');
    for (const id of rest) {
      setNode(run, id, 'RUNNING', now());
      push(step, custom('flow_agent_result', toTaskValue(run, 'RUNNING')));
      setNode(run, id, 'FINISHED', now());
      push(step, custom('flow_agent_result', toTaskValue(run, 'RUNNING')));
    }
    const summary =
      operation === 'flow_node_skip'
        ? '巡检完成：已跳过「磁盘检查」，其余 3 个节点执行成功。'
        : '巡检完成：「磁盘检查」重试成功，4 个节点全部执行成功。';
    push(0, custom('flow_agent_result', toTaskValue(run, 'FINISHED', [summary])));
    push(0, custom('flow_agent_end', [{ task_id: run.taskId, task_outputs: [summary] }]));
    push(0, { type: 'RUN_FINISHED', threadId, runId, outcome: { type: 'success' } });
    remember(key, run);
    return { frames, run, restarted: true };
  }

  taskSeq += 1;
  const run: FlowRun = {
    taskId: taskSeq,
    taskName: `inspection_${sessionCode}`,
    nodes: Object.fromEntries(FLOW_NODES.map(n => [n.id, { state: 'PENDING', start: '', finish: '', elapsed: 0, retry: 0 }])),
  };
  push(0, custom('flow_agent_start', [{ task_id: run.taskId }]));
  for (const def of FLOW_NODES) {
    setNode(run, def.id, 'RUNNING', now());
    push(step / 2, custom('flow_agent_result', toTaskValue(run, 'RUNNING')));
    if (def.id === FAILING_NODE) {
      setNode(run, def.id, 'FAILED', now());
      push(step, custom('flow_agent_result', toTaskValue(run, 'FAILED')));
      break;
    }
    setNode(run, def.id, 'FINISHED', now());
    push(step, custom('flow_agent_result', toTaskValue(run, 'RUNNING')));
  }
  const failure = '节点「磁盘检查」执行失败：/data 使用率 96%，超过阈值 90%。可在流程卡片中重试或跳过该节点。';
  push(0, custom('flow_agent_end', [{ task_id: run.taskId, task_outputs: [failure] }]));
  push(0, { type: 'RUN_FINISHED', threadId, runId, outcome: { type: 'success' } });
  remember(key, run);
  return { frames, run, restarted: false };
}

/** 记录用户对失败节点的重试 / 跳过；下一次 chat_completion 按此续跑 */
export function recordFlowOperation(clientId: string, sessionCode: string, operation: string, nodeId: string): boolean {
  if (operation !== 'flow_node_retry' && operation !== 'flow_node_skip') return false;
  const run = runs.get(runKey(clientId, sessionCode));
  if (!run || !run.nodes[nodeId]) return false;
  run.pending = { operation, nodeId };
  return true;
}

/** GET flow_agent/{task_id}/task_node_info/{node_id}/ 的响应（IFlowAgentTaskNodeInfo） */
export function buildNodeInfo(taskId: number, nodeId: string) {
  const def = FLOW_NODES.find(n => n.id === nodeId);
  if (!def) return undefined;
  const run = [...runs.values()].find(r => r.taskId === taskId);
  const state = run?.nodes[nodeId]?.state ?? 'PENDING';
  const value = state === 'FAILED' ? def.failValue ?? '执行失败' : state === 'FINISHED' ? def.okValue : '';
  return {
    task_id: taskId,
    node_id: nodeId,
    inputs: def.inputs,
    outputs: [
      { key: '_result', preset: true, value: state === 'FINISHED' },
      { key: def.outputKey, preset: false, value },
      ...(state === 'FAILED' ? [{ key: 'ex_data', preset: true, value: `Mock：${def.name}失败，${value}` }] : []),
    ],
    basic_info: {
      node_name: def.name,
      stage_name: '日常巡检',
      template_name: '主机日常巡检',
      optional: false,
      retryable: true,
      skippable: true,
      error_ignorable: false,
      always_use_latest: null,
      auto_retry: { enable: false, interval: 0, times: 0 },
      timeout_config: { action: 'forced_fail', enable: true, seconds: 300 },
    },
    plugin_output: [
      {
        key: def.outputKey,
        name: def.outputName,
        type: 'string',
        schema: { type: 'string', description: def.outputName, enum: [] },
      },
    ],
  };
}

/** 由节点状态推出任务状态 */
export function taskStateOf(run: FlowRun): 'RUNNING' | 'FAILED' | 'FINISHED' {
  const states = FLOW_NODES.map(n => run.nodes[n.id].state);
  if (states.includes('FAILED')) return 'FAILED';
  if (states.every(s => s === 'FINISHED' || s === 'SKIPPED')) return 'FINISHED';
  return 'RUNNING';
}

/** 运行结束后写入会话的活动消息（刷新历史可复现执行情况） */
export function toActivityMessage(run: FlowRun, sessionCode: string, id: string, taskState: string): MockMessageRecord {
  return {
    id,
    message_id: id,
    session_code: sessionCode,
    role: 'activity',
    activity_type: 'flow_agent',
    content: toTaskValue(run, taskState),
    status: 'complete',
    created_at: new Date().toISOString(),
  };
}

/** 仅测试使用 */
export function resetFlowRuns(): void {
  runs.clear();
  taskSeq = 87000;
}
