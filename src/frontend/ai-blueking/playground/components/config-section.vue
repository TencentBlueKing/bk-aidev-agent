<template>
  <div class="config-section">
    <h3>测试配置</h3>
    <div class="config-items">
      <label class="config-item">
        <span>加载状态：</span>
        <input
          :value="loading"
          type="checkbox"
          @input="(e: Event) => $emit('update:loading', (e.target as HTMLInputElement).checked)"
        />
      </label>
      <label class="config-item">
        <span>显示对话框：</span>
        <input
          :value="isShow"
          type="checkbox"
          @input="(e: Event) => $emit('update:isShow', (e.target as HTMLInputElement).checked)"
        />
      </label>
      <label class="config-item">
        <span>选择模型：</span>
        <select
          :value="model"
          @change="(e: Event) => $emit('update:model', (e.target as HTMLSelectElement).value)"
        >
          <option
            v-for="item in models"
            :key="item.id"
            :value="item.id"
          >
            {{ item.name }}
          </option>
        </select>
      </label>
      <label class="config-item">
        <span>聊天背景色：</span>
        <input
          :value="background"
          type="color"
          @input="(e: Event) => $emit('update:background', (e.target as HTMLInputElement).value)"
        />
      </label>
      <div class="config-item gradient-config">
        <span>头部背景色：</span>
        <div class="gradient-inputs">
          <input
            :value="headBackgroundConfig.startColor"
            type="color"
            @input="updateGradient('startColor', $event)"
          />
          <input
            :value="headBackgroundConfig.endColor"
            type="color"
            @input="updateGradient('endColor', $event)"
          />
          <input
            :value="headBackgroundConfig.angle"
            max="360"
            min="0"
            step="1"
            type="number"
            @input="updateGradient('angle', $event)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  interface Model {
    id: string;
    name: string;
  }

  interface HeadBackgroundConfig {
    angle: number;
    startColor: string;
    endColor: string;
  }

  const props = defineProps<{
    loading: boolean;
    isShow: boolean;
    model: string;
    models: Model[];
    background: string;
    headBackgroundConfig: HeadBackgroundConfig;
  }>();

  const emit = defineEmits<{
    'update:loading': [value: boolean];
    'update:isShow': [value: boolean];
    'update:model': [value: string];
    'update:background': [value: string];
    'update:headBackground': [value: string];
  }>();

  const updateGradient = (type: keyof HeadBackgroundConfig, event: Event) => {
    const value =
      type === 'angle' ? Number((event.target as HTMLInputElement).value) : (event.target as HTMLInputElement).value;

    const newConfig = {
      ...props.headBackgroundConfig,
      [type]: value,
    };

    emit(
      'update:headBackground',
      `linear-gradient(${newConfig.angle}deg, ${newConfig.startColor} 0%, ${newConfig.endColor} 95%)`,
    );
  };
</script>

<style lang="scss" scoped>
  .config-section {
    padding: 24px;
    margin-bottom: 32px;
    background: #f5f7fa;
    border-radius: 8px;

    h3 {
      margin-bottom: 16px;
      font-size: 18px;
      color: #333;
    }
  }

  .config-items {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;

    .config-item {
      display: flex;
      gap: 8px;
      align-items: center;

      span {
        min-width: 80px;
        color: #666;
      }

      input[type='checkbox'] {
        width: 16px;
        height: 16px;
      }

      input[type='color'] {
        width: 40px;
        height: 24px;
        padding: 0;
        border: 1px solid #ddd;
        border-radius: 4px;
      }

      select {
        padding: 4px 8px;
        border: 1px solid #ddd;
        border-radius: 4px;
      }

      &.gradient-config {
        .gradient-inputs {
          display: flex;
          gap: 8px;
          align-items: center;

          input[type='number'] {
            width: 60px;
            padding: 4px;
            border: 1px solid #ddd;
            border-radius: 4px;
          }
        }
      }
    }
  }
</style>
