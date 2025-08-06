# 会话生命周期管理

v1.2.2版本引入了全新的会话生命周期管理功能，允许开发者通过组件实例方法动态创建、重命名和切换聊天会话，满足更复杂的业务场景需求。

## 功能概述

会话生命周期管理提供了以下核心能力：

- **创建会话**：通过 `addNewSession()` 方法动态创建新的聊天会话
- **重命名会话**：通过 `updateSessionName(sessionCode, newName)` 方法修改现有会话的名称
- **切换会话**：通过 `switchToSession(sessionCode)` 方法在不同会话间进行切换
- **初始会话**：通过 `initialSessionCode` 和 `autoSwitchToInitialSession` 属性指定组件加载时的默认会话

## 使用场景

会话生命周期管理特别适用于以下场景：

1. **业务驱动的会话创建**：根据用户操作或业务流程自动创建新的聊天会话
2. **会话个性化**：根据对话内容或用户偏好动态重命名会话
3. **上下文切换**：在不同业务模块或任务间快速切换会话
4. **深度集成**：将AI对话能力深度集成到现有业务系统中

## 完整示例

以下示例展示了如何使用会话生命周期管理功能实现一个完整的业务流程：点击按钮创建新会话 -> 根据业务需求重命名会话 -> 自动切换到新会话。

```vue
<template>
  <div>
    <!-- AI小鲸组件 -->
    <AIBlueking 
      ref="aiBlueking" 
      :url="apiUrl" 
      :initial-session-code="initialSessionCode"
      :auto-switch-to-initial-session="true"
    />
    
    <!-- 控制按钮 -->
    <div class="controls">
      <bk-button @click="handleCreateSession">创建新会话</bk-button>
      <bk-button @click="handleSwitchToSession">切换到指定会话</bk-button>
      <bk-input 
        v-model="sessionName" 
        placeholder="输入会话名称" 
        style="width: 200px; margin: 0 10px;"
      />
      <bk-input 
        v-model="targetSessionCode" 
        placeholder="输入目标会话代码" 
        style="width: 200px;"
      />
    </div>
    
    <!-- 会话列表 -->
    <div class="session-list">
      <h3>当前会话列表</h3>
      <ul>
        <li 
          v-for="session in sessionList" 
          :key="session.sessionCode"
          :class="{ active: session.sessionCode === currentSessionCode }"
        >
          <span>{{ session.sessionName }}</span>
          <span class="session-code">({{ session.sessionCode }})</span>
          <bk-button 
            text 
            size="small" 
            @click="switchToSession(session.sessionCode)"
          >
            切换
          </bk-button>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { AIBlueking } from '@blueking/ai-blueking'
import { bkButton, bkInput } from 'bkui-vue'

// 组件引用
const aiBlueking = ref(null)

// 状态管理
const apiUrl = ref('YOUR_API_URL')
const sessionName = ref('') // 新会话名称
const targetSessionCode = ref('') // 目标会话代码
const sessionList = ref([]) // 会话列表
const currentSessionCode = ref('') // 当前会话代码
const initialSessionCode = ref('') // 初始会话代码

// 创建新会话
const handleCreateSession = async () => {
  try {
    // 1. 调用组件方法创建新会话
    const newSession = await aiBlueking.value?.addNewSession()
    
    if (newSession?.sessionCode) {
      // 2. 根据输入的名称重命名会话（如果提供了名称）
      if (sessionName.value) {
        await aiBlueking.value?.updateSessionName(
          newSession.sessionCode, 
          sessionName.value
        )
      }
      
      // 3. 自动切换到新创建的会话
      await aiBlueking.value?.switchToSession(newSession.sessionCode)
      
      // 4. 更新本地状态
      currentSessionCode.value = newSession.sessionCode
      sessionName.value = '' // 清空输入框
      
      // 5. 重新获取会话列表以反映最新状态
      await fetchSessionList()
      
      console.log('会话创建并切换成功:', newSession)
    }
  } catch (error) {
    console.error('创建会话失败:', error)
  }
}

// 切换到指定会话
const handleSwitchToSession = async () => {
  if (!targetSessionCode.value) {
    console.warn('请输入目标会话代码')
    return
  }
  
  try {
    await aiBlueking.value?.switchToSession(targetSessionCode.value)
    currentSessionCode.value = targetSessionCode.value
    targetSessionCode.value = ''
    console.log('成功切换到会话:', targetSessionCode.value)
  } catch (error) {
    console.error('切换会话失败:', error)
  }
}

// 切换到指定会话（从列表中选择）
const switchToSession = async (sessionCode) => {
  try {
    await aiBlueking.value?.switchToSession(sessionCode)
    currentSessionCode.value = sessionCode
    console.log('成功切换到会话:', sessionCode)
  } catch (error) {
    console.error('切换会话失败:', error)
  }
}

// 获取会话列表
const fetchSessionList = async () => {
  try {
    // 调用组件暴露的 getSessionList 方法获取最新的会话列表
    const list = await aiBlueking.value?.getSessionList();
    if (list) {
      sessionList.value = list;
    }
  } catch (error) {
    console.error('获取会话列表失败:', error);
  }
};

// 组件挂载时初始化
onMounted(async () => {
  // 初始化会话列表
  await fetchSessionList()
  
  // 如果有初始会话代码，设置它
  if (sessionList.value.length > 0) {
    initialSessionCode.value = sessionList.value[0].sessionCode
  }
})
</script>

<style scoped>
.controls {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 4px;
}

.session-list {
  padding: 20px;
}

.session-list h3 {
  margin-top: 0;
  margin-bottom: 15px;
}

.session-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.session-list li {
  display: flex;
  align-items: center;
  padding: 10px;
  margin-bottom: 8px;
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  transition: all 0.3s;
}

.session-list li:hover {
  background: #f5f7fa;
}

.session-list li.active {
  border-color: #3a84ff;
  background: #e1efff;
}

.session-list li span:first-child {
  flex: 1;
  font-weight: 500;
}

.session-code {
  color: #909399;
  font-size: 12px;
  margin: 0 10px;
}
</style>
```

## API 说明

### 新增属性

| 属性名 | 类型 | 默认值 | 描述 |
| --- | --- | --- | --- |
| `initialSessionCode` | `String` | `''` | 指定组件初始化时要加载的会话代码 |
| `autoSwitchToInitialSession` | `Boolean` | `true` | 控制是否在组件初始化时自动切换到初始会话 |

### 新增方法

| 方法名 | 参数 | 返回值 | 描述 |
| --- | --- | --- | --- |
| `addNewSession()` | - | `Promise<ISessionEditItem>` | 创建一个新的聊天会话并返回会话信息 |
| `updateSessionName(sessionCode, newName)` | `sessionCode: string, newName: string` | `Promise<ISessionEditItem>` | 更新指定会话的名称 |
| `switchToSession(sessionCode)` | `sessionCode: string` | `Promise<void>` | 切换到指定代码的会话 |
| `getSessionList()` | - | `Promise<ISessionEditItem[]>` | 获取最新的会话列表 |

## 注意事项

1. **异步操作**：所有会话管理方法都是异步的，需要使用 `await` 或 `.then()` 处理返回结果
2. **错误处理**：建议对所有异步操作进行适当的错误处理，以提升用户体验
3. **权限控制**：在实际应用中，应根据业务需求对会话操作进行适当的权限控制
4. **状态同步**：会话列表的更新可能需要手动触发，确保UI与实际状态保持一致
5. **性能优化**：频繁的会话切换操作可能影响性能，建议合理使用并做好优化

通过会话生命周期管理功能，开发者可以更灵活地控制AI对话组件的行为，实现更复杂和个性化的用户体验。