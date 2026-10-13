import type { AIBluekingExpose } from '@blueking/ai-blueking';

export interface Alert {
  title: string;
  host: string;
}

// ① 带着日志打开面板，由用户自己补充问题
export async function citeLogAndOpen(ai: AIBluekingExpose, log: string): Promise<void> {
  ai.setCiteText(log);
  await ai.show();
}

// ② 替用户直接提问（show 会等待会话就绪）
export async function askAboutAlert(ai: AIBluekingExpose, alert: Alert): Promise<void> {
  await ai.show();
  await ai.sendMessage(`请诊断告警「${alert.title}」，主机 ${alert.host}`);
}

// ③ 中止正在生成的回复（同步方法）
export function stopAnswer(ai: AIBluekingExpose): void {
  ai.stopGeneration();
}
