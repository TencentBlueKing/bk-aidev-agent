<template>
  <div class="custom-content">
    <div class="custom-content-content">
      {{ content }}
      <Button
        theme="primary"
        @click="handleClick"
      >
        查看详情
      </Button>
    </div>
    <template v-if="detailVisible && messageSlotId">
      <Teleport :to="messageSlotId">
        <div class="custom-content-slot">
          {{ content }}

          <Button
            theme="primary"
            @click="handleClick"
          >
            关闭
          </Button>
        </div>
      </Teleport>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { shallowRef } from 'vue';

  import { Button } from 'bkui-vue';

  import { useMessageSlotId } from '../src';

  defineProps<{
    content: string;
  }>();
  const { messageSlotId } = useMessageSlotId();
  const detailVisible = shallowRef(false);
  const handleClick = () => {
    detailVisible.value = !detailVisible.value;
  };
</script>
<style lang="scss">
  .custom-content {
    display: flex;

    &-content {
      display: flex;
      align-items: center;
      width: 100%;
      height: 100px;
      padding: 16px;
      font-size: 16px;
      background-color: #f0f0f0;
    }
  }
</style>
