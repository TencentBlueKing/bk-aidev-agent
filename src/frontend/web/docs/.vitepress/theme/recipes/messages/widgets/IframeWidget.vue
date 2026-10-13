<template>
  <div class="iw">
    <div class="iw__title">{{ data.title ?? '嵌入页面' }}</div>
    <iframe
      class="iw__frame"
      :height="data.height ?? 240"
      loading="lazy"
      sandbox="allow-scripts"
      :src="src"
      :title="data.title ?? '嵌入页面'"
    />
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import { withBase } from 'vitepress';

  /** 自定义块 JSON：{ type: 'iframe', title, src, height } */
  interface IframeData {
    title?: string;
    src?: string;
    height?: number;
  }

  const props = defineProps<{ data: IframeData }>();

  /** 站内绝对路径需要拼上文档站的 base（子路径部署时） */
  const src = computed(() => {
    const raw = props.data.src ?? 'about:blank';
    return raw.startsWith('/') && !raw.startsWith('//') ? withBase(raw) : raw;
  });
</script>

<style scoped>
  .iw {
    overflow: hidden;
    border: 1px solid #eaebf0;
    border-radius: 6px;
  }

  .iw__title {
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 600;
    color: #313238;
    background: #fafbfd;
    border-bottom: 1px solid #eaebf0;
  }

  .iw__frame {
    display: block;
    width: 100%;
    border: 0;
  }
</style>
