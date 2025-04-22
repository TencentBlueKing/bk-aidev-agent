<template>
  <div class="test-component">
    <h2>测试组件</h2>
    <button @click="callAiBlueking" class="test-btn">在子组件中调用 AI 小鲸</button>
  </div>
</template>

<script>
export default {
  name: 'TestComponent',
  methods: {
    callAiBlueking() {
      // 通过 $root 访问根组件，然后访问 AI 小鲸引用
      this.$root.$refs.aiBlueking?.handleShow();
      
      // 也可以通过 EventBus 或 Vuex 等方式来实现组件间通信
      console.log('在子组件中调用 AI 小鲸');
    }
  }
}
</script>

<style lang="scss" scoped>
.test-component {
  margin-top: 20px;
  padding: 15px;
  border: 1px dashed #ccc;
  border-radius: 4px;
}

.test-btn {
  padding: 8px 16px;
  background-color: #27ae60;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
  
  &:hover {
    background-color: #219653;
  }
}
</style> 