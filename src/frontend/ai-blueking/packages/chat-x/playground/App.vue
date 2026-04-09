<template>
  <div class="app-nav">
    <button
      :class="{ active: page === 'chat' }"
      @click="page = 'chat'"
    >
      ChatBot
    </button>
    <button
      :class="{ active: page === 'image' }"
      @click="page = 'image'"
    >
      Image
    </button>
  </div>
  <!-- <ChatBot v-if="page === 'chat'" /> -->
  <chatBotNew v-if="page === 'chat'" />
  <ImageDemo v-else-if="page === 'image'" />
</template>

<script setup lang="ts">
  import { ref } from 'vue';

  import chatBotNew from './chat-bot-new.vue';
  // import ChatBot from './chat-bot.vue';
  import ImageDemo from './image-play/index.vue';

  const page = ref<'chat' | 'image'>('chat');
</script>

<style>
  .app-nav {
    position: fixed;
    top: 8px;
    right: 8px;
    z-index: 9999;
    display: flex;
    gap: 4px;
  }

  .app-nav button {
    padding: 4px 12px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    background: #f0f1f5;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    transition: all 0.2s;
  }

  .app-nav button:hover {
    color: #3a84ff;
    border-color: #3a84ff;
  }

  .app-nav button.active {
    color: #fff;
    background: #3a84ff;
    border-color: #3a84ff;
  }
</style>
