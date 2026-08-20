/* eslint-disable @typescript-eslint/consistent-type-assertions */
/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import {
  // type AssistantMessage,
  type AIFileInfo,
  type BkFlowMessageContent,
  type IAiSlashMenuItem,
  type IModelOption,
  // type InfoMessage,
  type Message,
  type Shortcut,
  type UserMessage,
  AIBluekingIcon,
  APPROVAL_STATUS,
  // CopyIcon,
  DeleteIcon,
  InterruptReason,
  MessageContentType,
  MessageRole,
  MessageStatus,
  ShareIcon,
  t,
} from '../src';

// 模型图标示例：图标为图片地址（string），贴合后端返回的 icon 字段
const DEEPSEEK_ICON =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Ccircle cx='8' cy='8' r='7' fill='%234a6cf7'/%3E%3C/svg%3E";

// 生成贴合后端结构的模型 mock，补齐公共字段，聚焦 property（能力标签由其派生）与 description
const createMockModel = (id: number, llmName: string, extra: Partial<IModelOption> = {}): IModelOption => ({
  id,
  llm_code: llmName,
  llm_name: llmName,
  llm_type: 'chat.completion',
  max_token_size: 4096,
  space_auth_mode: 'PUBLIC',
  user_auth_mode: 'PUBLIC',
  base_model: 'hunyuan',
  icon: DEEPSEEK_ICON,
  tag_names: [],
  property: {},
  ...extra,
});

// 模型选择器 mock 数据：property 派生能力标签（图生文/深度思考/快速思考），description 作为选项 hover 提示
export const MOCK_MODELS: IModelOption[] = [
  createMockModel(1, 'hunyuan-turbos', {
    description: '混元 turbos 模型，支持视觉理解与深度思考',
    property: { max_model_len: 32000, support_thinking: true, support_vision: true },
  }),
  createMockModel(2, 'Hy3 hunyuan', {
    description: '混元 Hy3 模型，支持视觉理解与快速思考',
    property: { max_model_len: 32000, support_thinking_quick: true, support_vision: true },
  }),
  createMockModel(3, 'Deepseek - R1', {
    base_model: 'deepseek',
    description: 'DeepSeek R1 推理模型，支持深度思考',
    property: { max_model_len: 64000, support_thinking: true },
  }),
  createMockModel(4, 'Deepseek - V3', {
    base_model: 'deepseek',
    description: 'DeepSeek V3 通用模型，支持快速思考',
    property: { max_model_len: 64000, support_thinking_quick: true },
  }),
  createMockModel(5, 'GPT-4o', {
    base_model: 'openai',
    description: 'GPT-4o 通用对话模型',
  }),
  createMockModel(6, 'Legacy Model（已停用）', {
    disabled: true,
  }),
];

export const MOCK_SHORTCUTS = [
  {
    id: 'ai-chat',
    name: t('问问小鲸'),
    icon: () => AIBluekingIcon,
    components: [
      {
        id: 'ai-chat-input',
        type: 'input',
        formItemProps: { label: '提示词' },
        props: {
          placeholder: '请输入提示词',
          onChange: (value: string) => {
            console.log('Input changed:', value);
          },
        },
      },
      {
        id: 'ai-chat-select',
        type: 'select',
        formItemProps: { label: '模型' },
        props: {
          options: [
            { label: '模型1', value: 'model1' },
            { label: '模型2', value: 'model2' },
            { label: '模型3', value: 'model3' },
          ],
        },
      },
    ],
  },
  {
    id: 'ai-copy',
    name: t('复制'),
    icon: 'https://example.com/icons/agent_command/default.png',
  },
  {
    id: 'ai-share',
    name: t('分享'),
    icon: () => ShareIcon,
  },
  {
    id: 'ai-translate',
    name: '翻译',
  },
  {
    id: 'ai-delete',
    name: t('删除'),
    icon: () => DeleteIcon,
  },
  {
    id: 'ai-quote',
    name: t('引用'),
  },
  {
    id: 'ai-like',
    name: '点赞',
  },
  {
    id: 'ai-unlike',
    name: '不满意',
  },
] as Shortcut[];

// ---------------------------------------------------------------------------
// 文件产物 Mock（元信息 + 正文；download_url / preview_url 由 onArtifactClick 异步返回）
// txt / markdown / html：Blob URL，供前端 fetch 后原生渲染
// pdf / jpg：仍走 preview_url iframe（后台转 pdf 的模拟）
// ---------------------------------------------------------------------------

/** txt：纯文本预览正文 */
export const MOCK_ARTIFACT_TXT_CONTENT = `蓝鲸可观测平台 · 周例会纪要（草稿）
时间：2026-07-21 14:00–15:30
地点：线上会议（腾讯会议）
主持人：张明 | 记录人：李华

一、上周回顾
1. 告警收敛规则已上线，P1 告警量下降约 35%。
2. 日志查询慢查询优化：冷热分层已完成灰度，平均查询耗时从 8.2s 降至 2.6s。
3. Agent 侧文件产物预览联调阻塞项：markdown / txt 需前端直渲染，不再依赖 preview_url。

二、本周计划
1. 完成文件产物侧栏预览（html / txt / markdown）验收。
2. 推进「监控大盘 HTML 报告」导出模板评审。
3. 补齐 JSON 配置产物的 schema 校验与下载埋点。

三、风险与依赖
- PDF 转码服务高峰期偶发超时，需确认 SLA（负责人：王强，本周五前给结论）。
- 设计稿标注与主题变量对齐仍有 3 处待确认。

四、待办
[ ] 前端：txt / markdown 预览联调 — 李华 / 07-28
[ ] 后端：download_url 鉴权时效文档 — 赵磊 / 07-29
[ ] 产品：导出报告字段清单 — 陈静 / 07-30

备注：本稿仅供内部同步，正式纪要将在会后 24h 内发布到 iWiki。
`;

/** markdown：MarkdownContent 预览正文 */
export const MOCK_ARTIFACT_MARKDOWN_CONTENT = `# 蓝鲸可观测 · 系统配置说明

> 适用版本：chat-x ≥ 0.0.47｜更新：2026-07-28

## 1. 概述

本文档描述 Agent 产出**文件产物**时，前端侧栏预览与下载的配置约定。流式阶段消息仅携带文件元信息；真实链接通过 \`onArtifactClick\` 异步获取。

## 2. 预览策略

| 文件类型 | 加载方式 | 渲染 |
| --- | --- | --- |
| \`html\` | \`download_url\` → fetch | iframe \`srcdoc\` |
| \`txt\` | \`download_url\` → fetch | 浏览器纯文本（\`pre\`） |
| \`markdown\` / \`md\` | \`download_url\` → fetch | 项目 \`MarkdownContent\` |
| \`json\` | \`download_url\` → fetch | 纯文本（同 txt） |
| \`pdf\` / \`jpg\` | \`preview_url\` | iframe（后台转 PDF） |

## 3. 接入示例

\`\`\`ts
const onArtifactClick = async (file: AIFileInfo) => {
  const res = await api.getArtifactUrls(file.outputId);
  return {
    download_url: res.download_url,
    preview_url: res.preview_url,
  };
};
\`\`\`

## 4. 注意事项

1. **鉴权**：\`download_url\` / \`preview_url\` 建议带短时效签名，避免直链泄露。
2. **竞态**：侧栏切换文件时需中断上一次 fetch，防止旧内容覆盖。
3. **安全**：HTML 预览使用 \`srcdoc\`，勿将不可信脚本注入到宿主页面。

## 5. 检查清单

- [x] Pdf 预览可用
- [x] Html 直渲染
- [ ] Txt / Markdown 直渲染验收
- [ ] 下载埋点与失败重试

---

如有疑问请联系 **可观测前端小组**。
`;

/** html：iframe srcdoc 预览正文 */
export const MOCK_ARTIFACT_HTML_CONTENT = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>监控大盘周报</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; color: #1d2126; }
    h1 { font-size: 20px; margin: 0 0 8px; }
    .meta { color: #979ba5; font-size: 12px; margin-bottom: 20px; }
    .cards { display: flex; gap: 12px; flex-wrap: wrap; }
    .card { flex: 1; min-width: 140px; padding: 16px; background: #f5f7fa; border-radius: 8px; }
    .card strong { display: block; font-size: 24px; color: #3a84ff; margin-top: 8px; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px; }
    th, td { border: 1px solid #dcdee5; padding: 8px 10px; text-align: left; }
    th { background: #f0f1f5; }
  </style>
</head>
<body>
  <h1>业务监控大盘 · 周报预览</h1>
  <p class="meta">统计周期：2026-07-14 ~ 2026-07-20｜生成时间：2026-07-21 09:12</p>
  <div class="cards">
    <div class="card">P1 告警<strong>42</strong></div>
    <div class="card">平均恢复时长<strong>18 min</strong></div>
    <div class="card">可用性<strong>99.95%</strong></div>
  </div>
  <table>
    <thead><tr><th>服务</th><th>错误率</th><th>P99 延迟</th><th>状态</th></tr></thead>
    <tbody>
      <tr><td>aidev-agent</td><td>0.12%</td><td>320ms</td><td>正常</td></tr>
      <tr><td>chat-gateway</td><td>0.08%</td><td>180ms</td><td>正常</td></tr>
      <tr><td>artifact-preview</td><td>1.40%</td><td>1.2s</td><td>关注</td></tr>
    </tbody>
  </table>
</body>
</html>`;

/** json：配置样例正文（与 txt 相同，fetch 后纯文本预览） */
export const MOCK_ARTIFACT_JSON_CONTENT = `{
  "service": "bk-observe-agent",
  "env": "prod",
  "alert": {
    "p1_threshold": 5,
    "mute_window_min": 30,
    "channels": ["wecom", "email"]
  },
  "dashboard": {
    "refresh_sec": 60,
    "panels": ["error_rate", "latency_p99", "saturation"]
  }
}
`;

/** py：代码高亮预览正文（hljs 直接识别 py 别名） */
export const MOCK_ARTIFACT_PY_CONTENT = `"""告警收敛分析脚本：拉取近 7 天 P1 告警并按服务聚合输出 TOP 噪声源。"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from bkmonitor.client import MonitorClient

logger = logging.getLogger(__name__)

P1_LEVEL = 1
NOISE_THRESHOLD = 20


@dataclass(frozen=True)
class AlertDigest:
    service: str
    total: int
    recovered: int

    @property
    def recover_rate(self) -> float:
        return self.recovered / self.total if self.total else 0.0


def fetch_alerts(biz_id: int, days: int = 7) -> list[dict]:
    """按业务拉取指定天数内的 P1 告警。"""
    client = MonitorClient(biz_id=biz_id)
    end = datetime.now()
    start = end - timedelta(days=days)
    return client.search_alert(
        start_time=int(start.timestamp()),
        end_time=int(end.timestamp()),
        conditions=[{"key": "severity", "value": [P1_LEVEL]}],
    )


def summarize(alerts: list[dict]) -> list[AlertDigest]:
    total = Counter(a["service"] for a in alerts)
    recovered = Counter(a["service"] for a in alerts if a.get("status") == "RECOVERED")
    digests = [AlertDigest(svc, cnt, recovered[svc]) for svc, cnt in total.items()]
    return sorted(digests, key=lambda d: d.total, reverse=True)


def main(biz_id: int = 2) -> None:
    digests = summarize(fetch_alerts(biz_id))
    for item in digests:
        if item.total < NOISE_THRESHOLD:
            continue
        logger.warning(
            "噪声服务 %s：共 %d 条，恢复率 %.1f%%",
            item.service,
            item.total,
            item.recover_rate * 100,
        )


if __name__ == "__main__":
    main()
`;

/** vue：SFC 源码，验证 vue → xml 的 hljs 语言映射 */
export const MOCK_ARTIFACT_VUE_CONTENT = `<template>
  <div class="alert-summary">
    <h3 class="alert-summary-title">{{ title }}</h3>
    <ul class="alert-summary-list">
      <li
        v-for="item in topServices"
        :key="item.service"
        class="alert-summary-item"
        :class="{ 'is-noisy': item.total >= threshold }"
      >
        <span>{{ item.service }}</span>
        <em>{{ item.total }}</em>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  const props = withDefaults(
    defineProps<{
      digests: { service: string; total: number }[];
      threshold?: number;
      title?: string;
    }>(),
    { threshold: 20, title: 'P1 告警 TOP 服务' },
  );

  const topServices = computed(() => [...props.digests].sort((a, b) => b.total - a.total).slice(0, 5));
</script>

<style lang="scss">
  .alert-summary {
    padding: 12px 16px;
    background: #fafbfd;
    border-radius: 4px;

    &-item.is-noisy em {
      color: #ea3636;
    }
  }
</style>
`;

/** yaml：部署与告警配置 */
export const MOCK_ARTIFACT_YAML_CONTENT = `# 可观测 Agent 采集配置
apiVersion: monitor.bk.tencent.com/v1
kind: CollectConfig
metadata:
  name: aidev-agent-metrics
  namespace: bk-monitor
  labels:
    app: aidev-agent
    tier: backend
spec:
  interval: 60s
  timeout: 10s
  targets:
    - job: aidev-agent
      scheme: http
      path: /metrics
      ports: [8080, 8081]
  relabel:
    - source: __meta_kubernetes_pod_label_app
      target: service
  alerts:
    - name: HighErrorRate
      expr: rate(http_requests_total{code=~"5.."}[5m]) > 0.05
      for: 3m
      severity: 1
      annotations:
        summary: "错误率超过 5%，持续 3 分钟"
        runbook: https://iwiki.xxxx.com/runbook/high-error-rate
    - name: SlowP99
      expr: histogram_quantile(0.99, rate(http_duration_bucket[5m])) > 1
      for: 5m
      severity: 2
`;

/** sql：慢查询分析 */
export const MOCK_ARTIFACT_SQL_CONTENT = `-- 近 7 天各服务慢请求分布（P99 > 1s）
-- 生成时间：2026-07-21，数据源：bk_observe.request_log

WITH recent AS (
  SELECT
    service_name,
    request_path,
    duration_ms,
    status_code,
    created_at
  FROM bk_observe.request_log
  WHERE created_at >= NOW() - INTERVAL '7 days'
    AND duration_ms IS NOT NULL
)
SELECT
  service_name,
  request_path,
  COUNT(*)                                                   AS total,
  ROUND(AVG(duration_ms), 2)                                 AS avg_ms,
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms)  AS p99_ms,
  SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END)        AS error_count
FROM recent
GROUP BY service_name, request_path
HAVING PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) > 1000
ORDER BY p99_ms DESC
LIMIT 50;
`;

/** Dockerfile：无扩展名文件，验证按文件名解析类型 */
export const MOCK_ARTIFACT_DOCKERFILE_CONTENT = `# 可观测 Agent 运行镜像
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim

LABEL maintainer="bk-observe@example.com"

ENV PYTHONUNBUFFERED=1 \\
    TZ=Asia/Shanghai \\
    APP_ENV=prod

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

RUN groupadd -r bkuser && useradd -r -g bkuser bkuser
USER bkuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \\
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz')"

CMD ["python", "-m", "agent.server", "--port", "8080"]
`;

/** .gitignore：hljs 无对应语言，验证 plaintext 兜底 */
export const MOCK_ARTIFACT_GITIGNORE_CONTENT = `# 依赖
node_modules/
__pycache__/
*.egg-info/

# 构建产物
dist/
build/
.vitepress/cache/
.vitepress/dist/

# 环境与密钥
.env
.env.local
*.pem
*.key

# 日志与临时文件
*.log
.DS_Store
.idea/
.vscode/*
!.vscode/extensions.json
`;

/** rst：纯文本渲染，hljs 不支持该格式 */
export const MOCK_ARTIFACT_RST_CONTENT = `文件产物预览接入说明
====================

:作者: 可观测前端小组
:更新: 2026-07-28

概述
----

Agent 产出文件时，流式消息仅携带元信息（\`\`name\`\` / \`\`outputId\`\` / \`\`size\`\` / \`\`type\`\`），
真实的下载与预览链接由前端在用户点击时通过 \`\`onArtifactClick\`\` 异步获取。

接入步骤
--------

1. 给 \`\`ChatContainer\`\` 传入 \`\`onArtifactClick\`\`；
2. 回调内按 \`\`outputId\`\` 换取 \`\`download_url\`\` / \`\`preview_url\`\`；
3. 链接建议带短时效签名，避免直链泄露。

注意事项
--------

* 切换文件时前端会中断上一次请求，回调需支持被丢弃的结果；
* 未识别的扩展名统一走 \`\`preview_url\`\`，后台需保证可转换为 PDF。
`;

/** 覆盖各文件分类与图标的扩展样例：code / text / image / binary / 未登记类型 */
const MOCK_EXTENDED_ARTIFACTS: AIFileInfo[] = [
  {
    name: '告警收敛分析.py',
    outputId: 'artifact-py',
    size: MOCK_ARTIFACT_PY_CONTENT.length,
    type: 'py',
  },
  {
    name: 'alert-summary.vue',
    outputId: 'artifact-vue',
    size: MOCK_ARTIFACT_VUE_CONTENT.length,
    type: 'vue',
  },
  {
    name: 'collect-config.yaml',
    outputId: 'artifact-yaml',
    size: MOCK_ARTIFACT_YAML_CONTENT.length,
    type: 'yaml',
  },
  {
    name: '慢请求分布查询.sql',
    outputId: 'artifact-sql',
    size: MOCK_ARTIFACT_SQL_CONTENT.length,
    type: 'sql',
  },
  // 无扩展名文件：type 直接给文件名，解析时大小写不敏感
  {
    name: 'Dockerfile',
    outputId: 'artifact-dockerfile',
    size: MOCK_ARTIFACT_DOCKERFILE_CONTENT.length,
    type: 'Dockerfile',
  },
  // 点号开头的隐藏文件：hljs 无对应语言，预期按 plaintext 转义输出
  {
    name: '.gitignore',
    outputId: 'artifact-gitignore',
    size: MOCK_ARTIFACT_GITIGNORE_CONTENT.length,
    type: 'gitignore',
  },
  {
    name: '文件产物接入说明.rst',
    outputId: 'artifact-rst',
    size: MOCK_ARTIFACT_RST_CONTENT.length,
    type: 'rst',
  },
  {
    name: '告警趋势截图.png',
    outputId: 'artifact-png',
    size: 524_288,
    type: 'png',
  },
  {
    name: '监控方案评审材料.docx',
    outputId: 'artifact-docx',
    size: 163_840,
    type: 'docx',
  },
  {
    name: '容量规划测算表.xlsx',
    outputId: 'artifact-xlsx',
    size: 98_304,
    type: 'xlsx',
  },
  {
    name: '季度汇报.pptx',
    outputId: 'artifact-pptx',
    size: 2_097_152,
    type: 'pptx',
  },
  // 未登记扩展名：预期落 unknown 图标 + preview_url iframe 兜底
  {
    name: '巡检原始数据包.zip',
    outputId: 'artifact-zip',
    size: 5_242_880,
    type: 'zip',
  },
];

export const MOCK_FILE_ARTIFACTS: AIFileInfo[] = [
  {
    name: '可观测平台立项说明书.pdf',
    outputId: 'artifact-pdf',
    size: 245_760,
    type: 'pdf',
  },
  {
    name: '文件产物预览-系统配置说明.md',
    outputId: 'artifact-markdown',
    size: MOCK_ARTIFACT_MARKDOWN_CONTENT.length,
    type: 'markdown',
  },
  {
    name: '告警策略配置.json',
    outputId: 'artifact-json',
    size: MOCK_ARTIFACT_JSON_CONTENT.length,
    type: 'json',
  },
  {
    name: '机房巡检现场照片.jpg',
    outputId: 'artifact-jpg',
    size: 1_048_576,
    type: 'jpg',
  },
  {
    name: '监控大盘周报.html',
    outputId: 'artifact-html',
    size: MOCK_ARTIFACT_HTML_CONTENT.length,
    type: 'html',
  },
  {
    name: '周例会纪要-0721.txt',
    outputId: 'artifact-txt',
    size: MOCK_ARTIFACT_TXT_CONTENT.length,
    type: 'txt',
  },
  ...MOCK_EXTENDED_ARTIFACTS,
];

type MockArtifactUrl = {
  download_url?: string;
  preview_url?: string;
};

/** 后台转码后的统一 PDF 预览地址，binary 类文件共用 */
const MOCK_PDF_PREVIEW_URL = 'https://mozilla.github.io/pdf.js/web/compressed.tracemonkey-pldi-09.pdf';

/** 图片与 binary 类型需要的静态 URL；文本类 download_url 运行时用 Blob 生成 */
const MOCK_ARTIFACT_STATIC_URL: Record<string, MockArtifactUrl> = {
  'artifact-pdf': {
    download_url: 'https://example.com/download/observe-project.pdf',
    preview_url: MOCK_PDF_PREVIEW_URL,
  },
  'artifact-json': {},
  // 图片类走 <img src=preview_url>，preview_url 必须是真实图片而非转码 PDF
  'artifact-jpg': {
    download_url: 'https://picsum.photos/seed/bk-observe/1200/800.jpg',
    preview_url: 'https://picsum.photos/seed/bk-observe/1200/800.jpg',
  },
  'artifact-png': {
    download_url: 'https://picsum.photos/seed/bk-alert-trend/1440/900',
    preview_url: 'https://picsum.photos/seed/bk-alert-trend/1440/900',
  },
  'artifact-markdown': {},
  'artifact-html': {},
  'artifact-txt': {},
  'artifact-docx': {
    download_url: 'https://example.com/download/monitor-review.docx',
    preview_url: MOCK_PDF_PREVIEW_URL,
  },
  'artifact-xlsx': {
    download_url: 'https://example.com/download/capacity-plan.xlsx',
    preview_url: MOCK_PDF_PREVIEW_URL,
  },
  'artifact-pptx': {
    download_url: 'https://example.com/download/quarterly-report.pptx',
    preview_url: MOCK_PDF_PREVIEW_URL,
  },
  'artifact-zip': {
    download_url: 'https://example.com/download/inspection-raw.zip',
    preview_url: MOCK_PDF_PREVIEW_URL,
  },
};

const MOCK_TEXT_ARTIFACT_BODY: Record<string, { body: string; mime: string }> = {
  'artifact-html': { body: MOCK_ARTIFACT_HTML_CONTENT, mime: 'text/html' },
  'artifact-json': { body: MOCK_ARTIFACT_JSON_CONTENT, mime: 'application/json' },
  'artifact-markdown': { body: MOCK_ARTIFACT_MARKDOWN_CONTENT, mime: 'text/markdown' },
  'artifact-txt': { body: MOCK_ARTIFACT_TXT_CONTENT, mime: 'text/plain' },
  'artifact-py': { body: MOCK_ARTIFACT_PY_CONTENT, mime: 'text/x-python' },
  'artifact-vue': { body: MOCK_ARTIFACT_VUE_CONTENT, mime: 'text/plain' },
  'artifact-yaml': { body: MOCK_ARTIFACT_YAML_CONTENT, mime: 'text/yaml' },
  'artifact-sql': { body: MOCK_ARTIFACT_SQL_CONTENT, mime: 'application/sql' },
  'artifact-dockerfile': { body: MOCK_ARTIFACT_DOCKERFILE_CONTENT, mime: 'text/plain' },
  'artifact-gitignore': { body: MOCK_ARTIFACT_GITIGNORE_CONTENT, mime: 'text/plain' },
  'artifact-rst': { body: MOCK_ARTIFACT_RST_CONTENT, mime: 'text/plain' },
};

/** 缓存 Blob URL，避免重复 createObjectURL */
const mockArtifactBlobUrlCache = new Map<string, string>();

const getMockTextDownloadUrl = (outputId: string) => {
  const cached = mockArtifactBlobUrlCache.get(outputId);
  if (cached) {
    return cached;
  }
  const item = MOCK_TEXT_ARTIFACT_BODY[outputId];
  if (!item) {
    return undefined;
  }
  const url = URL.createObjectURL(new Blob([item.body], { type: `${item.mime};charset=utf-8` }));
  mockArtifactBlobUrlCache.set(outputId, url);
  return url;
};

/** 兼容旧导出名：静态映射 + 文本类占位（真实 download_url 见 mockArtifactClick） */
export const MOCK_ARTIFACT_URL_MAP: Record<string, MockArtifactUrl> = MOCK_ARTIFACT_STATIC_URL;

export const mockArtifactClick = async (file: AIFileInfo): Promise<MockArtifactUrl> => {
  console.info('mockArtifactClick', file);
  await new Promise(resolve => setTimeout(resolve, 600));
  const staticUrls = MOCK_ARTIFACT_STATIC_URL[file.outputId] ?? {};
  const textDownloadUrl = getMockTextDownloadUrl(file.outputId);
  return {
    ...staticUrls,
    ...(textDownloadUrl ? { download_url: textDownloadUrl } : {}),
  };
};

/** 第一轮产物：含 pdf / markdown / txt，后续轮次会复用部分 outputId 验证去重 */
const MOCK_ARTIFACTS_ROUND1: AIFileInfo[] = [
  MOCK_FILE_ARTIFACTS[0], // artifact-pdf
  MOCK_FILE_ARTIFACTS[1], // artifact-markdown
  MOCK_FILE_ARTIFACTS[5], // artifact-txt
];

/**
 * 第二轮产物：复用 artifact-pdf / artifact-txt（同 outputId 应去重并保留本轮），
 * 并新增 artifact-html；侧栏预期顺序按「最后一次出现」：markdown → pdf(新) → html → txt
 */
const MOCK_ARTIFACTS_ROUND2: AIFileInfo[] = [
  {
    name: '可观测平台立项说明书-v2.pdf',
    outputId: 'artifact-pdf',
    size: 312_320,
    type: 'pdf',
  },
  MOCK_FILE_ARTIFACTS[4], // artifact-html
  {
    name: '周例会纪要-0721-修订.txt',
    outputId: 'artifact-txt',
    size: MOCK_ARTIFACT_TXT_CONTENT.length + 32,
    type: 'txt',
  },
];

/** 第三轮产物：全类型样例，用于验证图标映射与各分类的预览渲染 */
const MOCK_ARTIFACTS_ROUND3: AIFileInfo[] = MOCK_EXTENDED_ARTIFACTS;

/**
 * 生成相对当前时间的 createdAt，用于调试消息时间的四档展示
 * 各轮会话按「从早到晚」分配，覆盖 非今年 / 今年内更早 / 昨天 / 今天 四种格式
 * @param dayOffset 距今天数，0 为今天、1 为昨天
 * @param yearOffset 距今年数，传 1 可稳定落在非今年，不受年初边界影响
 */
const mockCreatedAt = (dayOffset: number, hours: number, minutes: number, yearOffset = 0) => {
  const date = new Date();
  date.setFullYear(date.getFullYear() - yearOffset);
  date.setDate(date.getDate() - dayOffset);
  date.setHours(hours, minutes, 0, 0);
  return date.toISOString();
};

// 带文件产物的会话消息，用于 playground 调试 artifacts 展示与 outputId 去重
export const MOCK_ARTIFACTS_MESSAGES = [
  {
    id: 'mock-artifacts-user',
    role: MessageRole.User,
    content: '帮我把本周监控方案相关的产出文件都整理出来，方便评审。',
    name: 'user',
    status: MessageStatus.Complete,
    messageId: 'mock-artifacts-user',
    uid: 'mock-artifacts-user',
    createdAt: mockCreatedAt(5, 11, 20),
  },
  {
    id: 'mock-artifacts-assistant',
    role: MessageRole.Assistant,
    content: '已整理第一版材料：立项 PDF、配置说明 Markdown、周例会纪要 TXT。可点击卡片在侧栏预览或下载。',
    name: 'react_agent',
    status: MessageStatus.Complete,
    messageId: 'mock-artifacts-assistant',
    uid: 'mock-artifacts-assistant',
    createdAt: mockCreatedAt(5, 11, 22),
    property: {
      artifacts: MOCK_ARTIFACTS_ROUND1,
    },
  },
  {
    id: 'mock-artifacts-user-2',
    role: MessageRole.User,
    content: '再补一版 PDF，并加上大盘周报 HTML；纪要也更新一下。',
    name: 'user',
    status: MessageStatus.Complete,
    messageId: 'mock-artifacts-user-2',
    uid: 'mock-artifacts-user-2',
    createdAt: mockCreatedAt(4, 14, 8),
  },
  {
    id: 'mock-artifacts-assistant-2',
    role: MessageRole.Assistant,
    content:
      '已更新：PDF / TXT 与上一轮同 outputId（侧栏应去重并保留本轮最新文件名），同时新增 HTML 周报。打开「文件产物」侧栏可验证去重与顺序。',
    name: 'react_agent',
    status: MessageStatus.Complete,
    messageId: 'mock-artifacts-assistant-2',
    uid: 'mock-artifacts-assistant-2',
    createdAt: mockCreatedAt(4, 14, 10),
    property: {
      artifacts: MOCK_ARTIFACTS_ROUND2,
    },
  },
  {
    id: 'mock-artifacts-user-3',
    role: MessageRole.User,
    content: '把配套的脚本、配置和汇报材料也一起产出来，各种格式都要。',
    name: 'user',
    status: MessageStatus.Complete,
    messageId: 'mock-artifacts-user-3',
    uid: 'mock-artifacts-user-3',
    createdAt: mockCreatedAt(1, 9, 5),
  },
  {
    id: 'mock-artifacts-assistant-3',
    role: MessageRole.Assistant,
    content:
      '已产出全套材料：代码类（py / vue / yaml / sql / Dockerfile / .gitignore）走高亮预览，rst 走纯文本，png 直出图片，docx / xlsx / pptx 与未知格式 zip 走后台转码预览。',
    name: 'react_agent',
    status: MessageStatus.Complete,
    messageId: 'mock-artifacts-assistant-3',
    uid: 'mock-artifacts-assistant-3',
    createdAt: mockCreatedAt(1, 9, 8),
    property: {
      artifacts: MOCK_ARTIFACTS_ROUND3,
    },
  },
] as Message[];

export const MOCK_USER_MESSAGE = {
  id: '1',
  role: MessageRole.User,
  content:
    'Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?Hello, how are you?',
  messageId: '1',
  status: MessageStatus.Complete,
} as UserMessage;

/** InfoMessage：会话分隔 / 上下文提示；多行 content 运行时兼容 string[] */
export const MOCK_INFO_MESSAGES = [
  {
    id: 'mock-info-session-divider',
    messageId: 'mock-info-session-divider',
    role: MessageRole.Info,
    content: '以下是新的对话',
    status: MessageStatus.Completed,
  },
  {
    id: 'mock-info-context-cleared',
    messageId: 'mock-info-context-cleared',
    role: MessageRole.Info,
    // InfoMessage 类型声明为 string，组件运行时支持 string[]
    content: ['上下文已清除', '新对话从这里开始'],
    status: MessageStatus.Completed,
  },
] as Message[];

/**
 * ToolCallRender 状态 mock：一条 assistant 内多个 toolCall，覆盖
 * Pending / Streaming（Loading）与 Success / Complete / Completed（成功）以及 Error（失败）
 */
export const MOCK_TOOLCALL_STATUS_MESSAGES = [
  {
    id: 'mock-toolcall-status-user',
    role: MessageRole.User,
    content: '帮我演示一下工具调用的各种状态',
    name: 'user',
    status: MessageStatus.Complete,
    messageId: 'mock-toolcall-status-user',
    createdAt: mockCreatedAt(0, 10, 0, 1),
  },
  {
    id: 'mock-toolcall-status-assistant',
    role: MessageRole.Assistant,
    content: '以下为 ToolCallRender 各状态示例：',
    name: 'react_agent',
    status: MessageStatus.Complete,
    messageId: 'mock-toolcall-status-assistant',
    createdAt: mockCreatedAt(0, 10, 3, 1),
    toolCalls: [
      // Pending：无 toolMessage → Loading「调用中」
      {
        id: 'mock-tc-pending',
        type: 'function',
        function: {
          name: 'query_service_status',
          description: '查询服务运行状态（Pending）',
          arguments: '{"service": "chat-x"}',
        },
      },
      // Streaming：Loading「调用中」
      {
        id: 'mock-tc-streaming',
        type: 'function',
        function: {
          name: 'stream_logs',
          description: '流式拉取日志（Streaming）',
          arguments: '{"lines": 100}',
        },
        toolMessage: {
          toolCallId: 'mock-tc-streaming',
          status: MessageStatus.Streaming,
          content: '',
          duration: 0,
        },
      },
      // Success
      {
        id: 'mock-tc-success',
        type: 'function',
        function: {
          name: 'get_cluster_info',
          description: '获取集群信息（Success）',
          arguments: '{"cluster_id": "bk-prod"}',
        },
        toolMessage: {
          toolCallId: 'mock-tc-success',
          status: MessageStatus.Success,
          content: '{"cluster": "bk-prod", "nodes": 12}',
          duration: 1234,
        },
      },
      // Complete
      {
        id: 'mock-tc-complete',
        type: 'function',
        function: {
          name: 'list_pods',
          description: '列出 Pod（Complete）',
          arguments: '{"namespace": "default"}',
        },
        toolMessage: {
          toolCallId: 'mock-tc-complete',
          status: MessageStatus.Complete,
          content: '{"pods": ["api-0", "api-1"]}',
          duration: 856,
        },
      },
      // Completed
      {
        id: 'mock-tc-completed',
        type: 'function',
        function: {
          name: 'check_itsm_ticket',
          description: '检查 ITSM 工单（Completed）',
          arguments: '{"ticket_num": "1234"}',
        },
        toolMessage: {
          toolCallId: 'mock-tc-completed',
          status: MessageStatus.Completed,
          content: '{"id": "1234", "status": "open"}',
          duration: 2100,
        },
      },
      // Error：失败图标
      {
        id: 'mock-tc-error',
        type: 'function',
        function: {
          name: 'deploy_service',
          description: '部署服务（Error）',
          arguments: '{"service": "chat-x", "env": "prod"}',
        },
        toolMessage: {
          toolCallId: 'mock-tc-error',
          status: MessageStatus.Error,
          error: '部署失败：权限不足',
          content: '',
          duration: 430,
        },
      },
    ],
  },
] as Message[];

/**
 * flow_agent 执行情况 mock：单任务 + 5 个节点，覆盖成功 / 失败 / 待执行三态。
 * 失败节点带 retryable + skippable，用于验证「重试 / 跳过」只在对话流内出现，
 * 侧栏「执行情况」面板内只保留「详情」。
 */
const MOCK_FLOW_AGENT_CONTENT: BkFlowMessageContent = [
  {
    is_active: true,
    nodes: {
      'node-message-start': {
        elapsed_time: 0.4,
        finish_time: '2026-08-20 16:20:01',
        id: 'node-message-start',
        loop: 0,
        name: '消息展示',
        retry: 0,
        skip: false,
        start_time: '2026-08-20 16:20:00',
        state: 'FINISHED',
        type: 'task',
      },
      'node-knowledge': {
        elapsed_time: 5,
        finish_time: '2026-08-20 16:20:06',
        id: 'node-knowledge',
        loop: 0,
        name: '知识库',
        retry: 0,
        skip: false,
        start_time: '2026-08-20 16:20:01',
        state: 'FINISHED',
        type: 'task',
      },
      // 失败节点：重试 / 跳过入口的唯一来源
      'node-hy3-preview': {
        elapsed_time: 0.6,
        finish_time: '2026-08-20 16:20:07',
        id: 'node-hy3-preview',
        loop: 0,
        name: 'hy3-preview',
        retry: 0,
        retryable: true,
        skip: false,
        skippable: true,
        start_time: '2026-08-20 16:20:06',
        state: 'FAILED',
        type: 'task',
      },
      'node-deploy-test': {
        elapsed_time: 0,
        finish_time: '',
        id: 'node-deploy-test',
        loop: 0,
        name: '部署测试0114',
        retry: 0,
        skip: false,
        start_time: '',
        state: 'PENDING',
        type: 'task',
      },
      'node-message-end': {
        elapsed_time: 0,
        finish_time: '',
        id: 'node-message-end',
        loop: 0,
        name: '消息展示',
        retry: 0,
        skip: false,
        start_time: '',
        state: 'PENDING',
        type: 'task',
      },
    },
    statistics: {
      state_counts: { FAILED: 1, FINISHED: 2, PENDING: 2 },
      total: 5,
    },
    task_id: 1787195768571,
    task_name: 'flow_agent_test_new_session_1787195768571',
    task_outputs: {},
    task_state: 'FAILED',
  },
];

/** flow_agent 会话 mock：user 提问作为执行情况面板的分组标题，activity 承载流程内容 */
export const MOCK_FLOW_AGENT_MESSAGES = [
  {
    id: 'mock-flow-agent-user',
    role: MessageRole.User,
    content: '测试',
    name: 'user',
    status: MessageStatus.Complete,
    messageId: 'mock-flow-agent-user',
    createdAt: mockCreatedAt(0, 16, 20),
  },
  {
    id: 'mock-flow-agent-activity',
    role: MessageRole.Activity,
    activityType: MessageContentType.FlowAgent,
    content: MOCK_FLOW_AGENT_CONTENT,
    status: MessageStatus.Completed,
    messageId: 'mock-flow-agent-activity',
    createdAt: mockCreatedAt(0, 16, 20),
  },
] as Message[];

// @ 资源列表
export const MOCK_RESOURCES = [
  {
    type: 'tool',
    name: '工具1撒旦法收到了客服',
    id: 'tool1',
    icon: 'icon-tool1',
  },
  {
    type: 'shortcut',
    name: '快捷1撒旦法收到',
    id: 'shortcut1',
    icon: 'icon-shortcut1',
  },
  {
    type: 'doc',
    name: '文档1',
    id: 'doc1',
    icon: 'icon-doc1',
  },
  {
    type: 'mcp',
    name: 'MCP1',
    id: 'mcp1',
    icon: 'icon-mcp1',
  },
  {
    type: 'tool',
    name: '工具2',
    id: 'tool2',
    icon: 'icon-tool2',
  },

  {
    type: 'shortcut',
    name: '快捷2',
    id: 'shortcut2',
    icon: 'icon-shortcut2',
  },

  {
    type: 'doc',
    name: '文档2',
    id: 'doc2',
    icon: 'icon-doc2',
  },
] as IAiSlashMenuItem[];
// @ 提示词列表
export const MOCK_PROMPTS = ['你好', '你好啊', '你好啊', '你好啊', '你好啊', '你好啊', '你好啊', '你好啊', '你好啊'];

export const MOCK_MARKDOWN_CONTENT = `
---
__Advertisement :)__

- __[pica](https://nodeca.github.io/pica/demo/)__ - high quality and fast image
  resize in browser.
- __[babelfish](https://github.com/nodeca/babelfish/)__ - developer friendly
  i18n with plurals support and easy syntax.

You will like those projects!

---

# h1 Heading 8-)
## h2 Heading
### h3 Heading
#### h4 Heading
##### h5 Heading
###### h6 Heading


## Horizontal Rules

___

---

***


## Typographic replacements

Enable typographer option to see result.

(c) (C) (r) (R) (tm) (TM) (p) (P) +-

test.. test... test..... test?..... test!....

!!!!!! ???? ,,  -- ---

"Smartypants, double quotes" and 'single quotes'


## Emphasis

**This is bold text**

__This is bold text__

*This is italic text*

_This is italic text_

~~Strikethrough~~


## Blockquotes


> Blockquotes can also be nested...
>> ...by using additional greater-than signs right next to each other...
> > > ...or with spaces between arrows.


## Lists

Unordered

+ Create a list by starting a line with \`+\`, \`-\`, or \`*\`
+ Sub-lists are made by indenting 2 spaces:
  - Marker character change forces new list start:
    * Ac tristique libero volutpat at
    + Facilisis in pretium nisl aliquet
    - Nulla volutpat aliquam velit
+ Very easy!

Ordered

1. Lorem ipsum dolor sit amet
2. Consectetur adipiscing elit
3. Integer molestie lorem at massa


1. You can use sequential numbers...
1. ...or keep all the numbers as \`1.\`

Start numbering with offset:

57. foo
1. bar


## Code

Inline \`code\`

Indented code

    // Some comments
    line 1 of code
    line 2 of code
    line 3 of code


Block code "fences"

\`\`\`
Sample text here...
\`\`\`

Syntax highlighting

\`\`\` js
var foo = function (bar) {
  return bar++;
};

console.log(foo(5));
\`\`\`

## Tables

| Option | Description |
| ------ | ----------- |
| data   | path to data files to supply the data that will be passed into templates. |
| engine | engine to be used for processing templates. Handlebars is the default. |
| ext    | extension to be used for dest files. |

Right aligned columns

| Option | Description |
| ------:| -----------:|
| data   | path to data files to supply the data that will be passed into templates. |
| engine | engine to be used for processing templates. Handlebars is the default. |
| ext    | extension to be used for dest files. |


## Links

[link text](http://dev.nodeca.com)

[link with title](http://nodeca.github.io/pica/demo/ "title text!")

Autoconverted link https://github.com/nodeca/pica (enable linkify to see)


## Images

![Minion](https://octodex.github.com/images/minion.png)
![Stormtroopocat](https://octodex.github.com/images/stormtroopocat.jpg "The Stormtroopocat")

Like links, Images also have a footnote style syntax

![Alt text][id]

With a reference later in the document defining the URL location:

[id]: https://octodex.github.com/images/dojocat.jpg  "The Dojocat"


## Plugins

The killer feature of \`markdown-it\` is very effective support of
[syntax plugins](https://www.npmjs.org/browse/keyword/markdown-it-plugin).


### [Emojies](https://github.com/markdown-it/markdown-it-emoji)

> Classic markup: :wink: :cry: :laughing: :yum:
>
> Shortcuts (emoticons): :-) :-( 8-) ;)

see [how to change output](https://github.com/markdown-it/markdown-it-emoji#change-output) with twemoji.


### [Subscript](https://github.com/markdown-it/markdown-it-sub) / [Superscript](https://github.com/markdown-it/markdown-it-sup)

- 19^th^
- H~2~O


### [<ins>](https://github.com/markdown-it/markdown-it-ins)

++Inserted text++


### [<mark>](https://github.com/markdown-it/markdown-it-mark)

==Marked text==


### [Footnotes](https://github.com/markdown-it/markdown-it-footnote)

Footnote 1 link[^first].

Footnote 2 link[^second].

Inline footnote^[Text of inline footnote] definition.

Duplicated footnote reference[^second].

[^first]: Footnote **can have markup**

    and multiple paragraphs.

[^second]: Footnote text.


### [Definition lists](https://github.com/markdown-it/markdown-it-deflist)

Term 1

:   Definition 1
with lazy continuation.

Term 2 with *inline markup*

:   Definition 2

        { some code, part of Definition 2 }

    Third paragraph of definition 2.

_Compact style:_

Term 1
  ~ Definition 1

Term 2
  ~ Definition 2a
  ~ Definition 2b


### [Abbreviations](https://github.com/markdown-it/markdown-it-abbr)

This is HTML abbreviation example.

It converts "HTML", but keep intact partial entries like "xxxHTMLyyy" and so on.

*[HTML]: Hyper Text Markup Language

### [Custom containers](https://github.com/markdown-it/markdown-it-container)

::: warning
*here be dragons*
:::
              `;

export const MOCK_MESSAGES = [
  // 文件产物 + outputId 去重调试会话（侧栏「文件产物」）
  ...MOCK_ARTIFACTS_MESSAGES,
  {
    id: 'cbba21f14f7847d98ff3240e69ef5c07',
    role: 'user',
    content: '检查一下 itsm 工单1234的状态',
    name: 'user',
    status: 'completed',
    messageId: 'cbba21f14f7847d98ff3240e69ef5c07',
    createdAt: mockCreatedAt(0, 15, 30),
  },
  // {
  //   id: 'cbba21f14f7847d98ff3240e69ef5c07',
  //   role: 'custom',
  //   content: {
  //     content: '这是自定义内容',
  //     id: 'cbba21f14f7847d98ff3240e69ef5c07',
  //     name: 'custom',
  //     slot: 'custom-slot',
  //   },
  //   name: 'custom',
  //   status: 'completed',
  //   messageId: 'cbba21f14f7847d98ff3240e69ef5c07',
  // },
  {
    status: 'completed',
    id: 'lc_run--019b7205-65ad-7c70-b504-ca80d8cd0efa',
    role: 'reasoning',
    content: [
      '用户想要检查ITSM工单1234的状态。我需要调用check_itsm_ticket_v2工具，并将ticket_num参数设为"1234"。现在就开始执行。',
    ],
    messageId: 'lc_run--019b7205-65ad-7c70-b504-ca80d8cd0efa',
  },
  {
    id: 'lc_run--019b7205-65ad-7c70-b504-ca80d8cd0efa',
    role: 'assistant',
    content: '\n\n',
    name: 'react_agent',
    toolCalls: [
      {
        id: 'call_8e651617efb44152af988a5c',
        type: 'function',
        function: {
          name: 'check_itsm_ticket_v2',
          arguments: '{"ticket_num": "1234"}',
        },
      },
    ],
    status: 'completed',
    messageId: 'lc_run--019b7205-65ad-7c70-b504-ca80d8cd0efa',
  },
  {
    id: '6287d811-590f-4c96-bc8f-36a5cf6cd558',
    role: 'activity',
    activityType: 'chat',
    content: [{ name: '', url: '' }],
    status: 'completed',
    messageId: '6287d811-590f-4c96-bc8f-36a5cf6cd558',
  },
  {
    id: 'e737ddd2-d13a-4a6d-8650-2490163c607b',
    role: 'tool',
    content:
      '{"id": "1234", "title": "\\u5de5\\u53551234", "description": "\\u6d4b\\u8bd5\\u5de5\\u5355\\u4e00\\u4e8c\\u4e09", "status": "open"}',
    toolCallId: 'call_8e651617efb44152af988a5c',
    status: 'completed',
    messageId: 'e737ddd2-d13a-4a6d-8650-2490163c607b',
  },
  {
    status: 'completed',
    id: 'lc_run--019b7205-6bb3-79a0-81ec-48e5fcb8fea0',
    role: 'reasoning',
    content: [
      '根据查询结果，ITSM工单1234的状态是：**open（开启）**。\n\n工单详情：\n- 工单号：1234\n- 标题：工单1234\n- 描述：测试工单一二三\n- 状态：open',
    ],
    messageId: 'lc_run--019b7205-6bb3-79a0-81ec-48e5fcb8fea0',
  },
  {
    id: 'lc_run--019b7205-6bb3-79a0-81ec-48e5fcb8fea0',
    role: 'assistant',
    content: '',
    name: 'react_agent',
    status: 'completed',
    messageId: 'lc_run--019b7205-6bb3-79a0-81ec-48e5fcb8fea0',
    createdAt: mockCreatedAt(0, 15, 31),
  },
  {
    id: 'mock-revoked-approval-user',
    role: MessageRole.User,
    content: '查看一下已经撤销的算法方案评审单',
    name: 'user',
    status: MessageStatus.Complete,
    messageId: 'mock-revoked-approval-user',
    createdAt: mockCreatedAt(0, 15, 45),
  },
  {
    id: 'mock-revoked-approval-assistant',
    role: MessageRole.Assistant,
    content: '该第三方审批单据已撤销，当前无需继续审批：',
    name: 'react_agent',
    status: MessageStatus.Complete,
    messageId: 'mock-revoked-approval-assistant',
  },
  {
    id: 'mock-revoked-approval-interrupt',
    role: MessageRole.Interrupt,
    content: {
      message: '',
      outcome: {
        type: 'interrupt',
        interrupts: [
          {
            id: 'mock-revoked-approval-interrupt-item',
            reason: InterruptReason.AIDevToolApproval,
            toolCallId: 'mock-revoked-approval-tool-call',
            metadata: {
              ticket: {
                approvers: [],
                sn: 'REV-2026-04-24-002',
                status: APPROVAL_STATUS.REVOKED,
                submit_time: '2026-04-24 14:30:15',
                title: '算法方案评审单',
                url: 'https://example.com/ticket/REV-2026-04-24-002',
              },
            },
          },
        ],
      },
    },
    status: MessageStatus.Complete,
    messageId: 'mock-revoked-approval-interrupt',
  },
];
