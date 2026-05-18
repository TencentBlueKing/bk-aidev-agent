<template>
  <div class="flow-side-render-demo">
    <div
      v-if="!flowAgentUrl"
      class="flow-side-render-demo__empty"
    >
      请在 <code>packages/ai-blueking/.env.local</code> 中配置
      <code>VITE_FLOW_AGENT_URL</code>（流程智能体插件 API 地址）
    </div>
    <ChatBot
      v-else
      height="640px"
      :url="flowAgentUrl"
      :get-side-render-component="getSideRenderComponent"
      :get-side-tab-render-component="getSideTabRenderComponent"
      :hello-text="helloText"
      :placeholder="'输入消息，触发流程智能体（FlowAgent）…'"
      placement="left"
      :resize-props="{
        initialDivide: '55%',
        min: 320,
        max: 720,
      }"
      @error="handleError"
    />
  </div>
</template>

<script setup lang="ts">
  import { ChatBot } from '@blueking/ai-blueking';

  import { useSideRenderHandlers } from './use-side-render-handlers';

  const flowAgentUrl = import.meta.env.VITE_FLOW_AGENT_URL || '';

  const { getSideRenderComponent, getSideTabRenderComponent } = useSideRenderHandlers();

  const helloText =
    '本示例连接流程智能体后台（VITE_FLOW_AGENT_URL）。发送消息后等待 FlowAgent 活动消息出现，展开「执行情况」，点击节点「详情」可在右侧看到自定义侧栏；节点详情由小鲸默认接口拉取。';

  const handleError = (error: Error) => {
    console.error('[SideRender Demo]', error);
  };
</script>

<style scoped>
  .flow-side-render-demo {
    overflow: hidden;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .flow-side-render-demo__empty {
    padding: 24px;
    font-size: 13px;
    line-height: 22px;
    color: #63656e;
    background: #fffbf0;
  }

  .flow-side-render-demo__empty code {
    padding: 1px 6px;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 3px;
  }
</style>
