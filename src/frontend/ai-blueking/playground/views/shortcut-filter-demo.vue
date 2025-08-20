<template>
  <div class="shortcut-filter-demo">
    <h2>快捷操作过滤器示例</h2>
    <p>选中下面的文本内容，查看快捷操作如何根据选中的内容进行过滤：</p>

    <div class="content-area">
      <div class="text-section">
        <h3>代码示例</h3>
        <pre><code class="language-javascript">function calculateSum(a, b) {
  return a + b;
}

const result = calculateSum(5, 3);
console.log(result);</code></pre>
      </div>

      <div class="text-section">
        <h3>普通文本</h3>
        <p>
          人工智能（Artificial
          Intelligence，AI）是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。
        </p>
      </div>

      <div class="text-section">
        <h3>长文本示例</h3>
        <p>
          这是一段很长的文本内容，用于测试快捷操作过滤器的行为。当用户选中过长的文本时，某些快捷操作（如翻译）可能不适用，因此可以被过滤掉。这是一段很长的文本内容，用于测试快捷操作过滤器的行为。当用户选中过长的文本时，某些快捷操作（如翻译）可能不适用，因此可以被过滤掉。这是一段很长的文本内容，用于测试快捷操作过滤器的行为。当用户选中过长的文本时，某些快捷操作（如翻译）可能不适用，因此可以被过滤掉。
        </p>
      </div>
    </div>

    <div class="ai-blueking-wrapper">
      <AIBlueking
        :shortcuts="shortcuts"
        :shortcut-filter="shortcutFilter"
        :enable-popup="true"
        :request-options="requestOptions"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import AIBlueking from '../../src/ai-blueking-new.vue';

  // 定义快捷操作
  const shortcuts = [
    {
      id: 'explain_code',
      name: '解释代码',
      icon: 'bkai-icon bkai-code',
      components: [
        {
          type: 'textarea',
          key: 'code',
          name: '代码内容',
          fillBack: true,
          placeholder: '请输入或选中需要解释的代码',
        },
      ],
    },
    {
      id: 'translate',
      name: '翻译',
      icon: 'bkai-icon bkai-translate',
      components: [
        {
          type: 'textarea',
          key: 'text',
          name: '待翻译文本',
          fillBack: true,
          placeholder: '请输入或选中需要翻译的文本',
        },
        {
          type: 'select',
          key: 'targetLang',
          name: '目标语言',
          options: [
            { label: '中文', value: 'zh' },
            { label: '英文', value: 'en' },
            { label: '日文', value: 'jp' },
          ],
          default: 'en',
          placeholder: '请选择目标语言',
        },
      ],
    },
    {
      id: 'summarize',
      name: '总结',
      icon: 'bkai-icon bkai-edit',
      components: [
        {
          type: 'textarea',
          key: 'content',
          name: '内容',
          fillBack: true,
          placeholder: '请输入或选中需要总结的内容',
        },
      ],
    },
  ];

  // 定义过滤器函数
  const shortcutFilter = shortcut => {
    // 检查是否有组件包含选中文本
    const hasSelectedText = shortcut.components?.some(c => c.selectedText);

    if (!hasSelectedText) {
      // 如果没有选中文本，显示所有快捷操作
      return true;
    }

    // 获取选中的文本内容
    const selectedText = shortcut.components?.find(c => c.selectedText)?.selectedText || '';

    console.log(selectedText);

    // 根据快捷操作类型和选中文本内容进行过滤
    switch (shortcut.id) {
      case 'explain_code':
        // 只有当选中的文本包含代码特征时才显示
        return (
          selectedText.includes('function') ||
          selectedText.includes('const') ||
          selectedText.includes('let') ||
          selectedText.includes('var') ||
          selectedText.includes('return') ||
          selectedText.includes('{') ||
          selectedText.includes('}') ||
          selectedText.includes('(') ||
          selectedText.includes(')')
        );

      case 'translate':
        // 翻译操作：文本长度在合理范围内才显示
        return selectedText.length > 0 && selectedText.length < 500;

      case 'summarize':
        // 总结操作：只有当选中文本较长时才显示
        return selectedText.length > 100;

      default:
        return true;
    }
  };

  // 请求选项
  const requestOptions = ref({
    headers: {
      'Content-Type': 'application/json',
    },
    context: () => ({
      userId: 'demo-user',
      timestamp: Date.now(),
    }),
  });
</script>

<style scoped>
  .shortcut-filter-demo {
    padding: 20px;
    max-width: 1200px;
    margin: 0 auto;
  }

  .content-area {
    margin: 20px 0;
    padding: 20px;
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: #f9f9f9;
  }

  .text-section {
    margin-bottom: 20px;
  }

  .text-section h3 {
    margin-top: 0;
    color: #333;
  }

  pre {
    background-color: #f5f5f5;
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
  }

  .ai-blueking-wrapper {
    margin-top: 30px;
  }
</style>
