<template>
  <div class="chat-wrapper" v-bkloading="loadingConf">
    <AIBlueking
      ref="aiBlueking"
      hide-header
      :draggable="false"
      :hide-nimbus="false"
      :url="url"
      :default-top="52"
      :default-width="AIBluekingWidth"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref, onMounted, reactive } from 'vue';

  import AIBlueking, { AIBluekingExpose } from '@blueking/ai-blueking';
  import '@blueking/ai-blueking/dist/vue3/style.css';


  const aiBlueking = ref<AIBluekingExpose | null>(null);

  const url = ref(window.BK_API_PREFIX);

  const AIBluekingWidth = ref(window.innerWidth);

  const title = ref('加载中...');

  const loading = ref(true);

  const loadingConf = reactive({
    loading,
    title
  })

  onMounted(() => {
    setTimeout(() => {
      aiBlueking.value?.handleShow();
      loading.value = false;
    }, 200);
  });

</script>

<style lang="postcss">
  .chat-wrapper {
    width: 100%;
    height: 100vh;
  }
</style>