<template>
  <div class="app">
    <h1>BK AI Helper Playground</h1>

    <!-- 简单示例 -->
    <section class="demo-section">
      <div class="section-header">
        <h2>🚀 简单示例 - Simple Demo</h2>
        <p class="section-desc">AI 帮助填充输入框内容</p>
      </div>
      <div class="demo-container">
        <div class="demo-preview">
          <div class="form-demo">
            <label class="form-label">
              规则名称
              <BkAiHelper :base-url="baseUrl" prompt="帮我生成一个简短的规则名称" @response="handleSimpleResponse" />
            </label>
            <input v-model="simpleInput" class="demo-input" placeholder="请输入规则名称" type="text" />
          </div>
        </div>
        <div class="code-block">
          <div class="code-header">
            <span>代码示例</span>
          </div>
          <pre><code>&lt;template&gt;
  &lt;div class="form-demo"&gt;
    &lt;label&gt;
      规则名称
      &lt;BkAiHelper
        base-url="YOUR_API_BASE_URL"
        prompt="帮我生成一个简短的规则名称"
        @response="handleResponse"
      /&gt;
    &lt;/label&gt;
    &lt;input v-model="ruleName" placeholder="请输入规则名称" /&gt;
  &lt;/div&gt;
&lt;/template&gt;

&lt;script setup&gt;
import { ref } from 'vue';
import BkAiHelper from '@blueking/bk-ai-helper';

const ruleName = ref('');

const handleResponse = (content) => {
  ruleName.value = content;  // AI 响应自动填充到输入框
};
&lt;/script&gt;</code></pre>
        </div>
      </div>
    </section>

    <!-- 完整示例 -->
    <section class="demo-section">
      <div class="section-header">
        <h2>⚡ 完整示例 - Full Features Demo</h2>
        <p class="section-desc">复杂场景：使用 prompt 和自定义配置，填充多行文本</p>
      </div>
      <div class="demo-container">
        <div class="demo-preview">
          <div class="form-demo">
            <label class="form-label">
              规则描述
              <BkAiHelper
                form-title="AI 生成规则描述"
                placeholder="描述你想要生成什么样的规则描述"
                prompt="帮我生成一个详细的业务规则描述，不要多余的思考、解释，直接生成规则描述"
                title="AI 助手"
                @error="handleError"
                @response="handleFullResponse"
                @success="handleSuccess"
              />
            </label>
            <textarea v-model="fullInput" class="demo-textarea" placeholder="请输入规则描述（或让 AI 帮你生成）" rows="6" />
            <p class="tip">💡 提示：按 Enter 发送，Shift + Enter 换行</p>
          </div>
        </div>
        <div class="code-block">
          <div class="code-header">
            <span>代码示例</span>
          </div>
          <pre><code>&lt;template&gt;
  &lt;div class="form-demo"&gt;
    &lt;label&gt;
      规则描述
      &lt;BkAiHelper
        base-url="YOUR_API_BASE_URL"
        form-title="AI 生成规则描述"
        placeholder="描述你想要生成什么样的规则描述"
        prompt="帮我生成一个详细的业务规则描述，不要多余的思考、解释，直接生成规则描述"
        title="AI 助手"
        @response="handleResponse"
        @error="handleError"
        @success="handleSuccess"
      /&gt;
    &lt;/label&gt;
    &lt;textarea
      v-model="description"
      placeholder="请输入规则描述（或让 AI 帮你生成）"
      rows="6"
    /&gt;
  &lt;/div&gt;
&lt;/template&gt;

&lt;script setup&gt;
import { ref } from 'vue';
import BkAiHelper from '@blueking/bk-ai-helper';

const description = ref('');

const handleResponse = (content) => {
  description.value = content;  // AI 响应自动填充到文本框
};

const handleError = (error) => {
  console.error('请求失败:', error);
};

const handleSuccess = (response) => {
  console.log('请求成功:', response);
};
&lt;/script&gt;</code></pre>
        </div>
      </div>
    </section>

    <!-- API 说明 -->
    <section class="demo-section api-section">
      <div class="section-header">
        <h2>📚 API 说明</h2>
      </div>
      <div class="api-table">
        <table>
          <thead>
            <tr>
              <th>属性名</th>
              <th>类型</th>
              <th>默认值</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>base-url</code></td>
              <td>String</td>
              <td>-</td>
              <td>API 基础地址（必填）</td>
            </tr>
            <tr>
              <td><code>title</code></td>
              <td>String</td>
              <td>'帮我写'</td>
              <td>触发按钮文字</td>
            </tr>
            <tr>
              <td><code>form-title</code></td>
              <td>String</td>
              <td>'规则描述'</td>
              <td>弹窗标题</td>
            </tr>
            <tr>
              <td><code>placeholder</code></td>
              <td>String</td>
              <td>-</td>
              <td>输入框占位符</td>
            </tr>
            <tr>
              <td><code>prompt</code></td>
              <td>String</td>
              <td>''</td>
              <td>预设的 AI 提示词，用于引导 AI 生成特定内容</td>
            </tr>
            <tr>
              <td><code>form-options</code></td>
              <td>Object</td>
              <td>-</td>
              <td>传递给 BkInput 的额外配置</td>
            </tr>
          </tbody>
        </table>

        <h3>Events 事件</h3>
        <table>
          <thead>
            <tr>
              <th>事件名</th>
              <th>参数</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>@success</code></td>
              <td>(response: ChatCompletionResponse)</td>
              <td>请求成功时触发</td>
            </tr>
            <tr>
              <td><code>@response</code></td>
              <td>(content: string)</td>
              <td>返回 AI 响应内容</td>
            </tr>
            <tr>
              <td><code>@error</code></td>
              <td>(error: Error)</td>
              <td>请求失败时触发</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
  /// <reference path="../src/vite-env.d.ts" />
  import { ref } from "vue"

  import BkAiHelper from "../src/vue3.ts"

  const baseUrl = AI_HELPER_BASE_URL || ""

  // 简单示例的输入框
  const simpleInput = ref("")

  // 完整示例的文本框
  const fullInput = ref("")

  // 简单示例的响应处理
  const handleSimpleResponse = (response: string) => {
    console.log("💬 简单示例 - AI 响应:", response)
    simpleInput.value = response
  }

  // 完整示例的响应处理
  const handleFullResponse = (response: string) => {
    console.log("💬 完整示例 - AI 响应:", response)
    fullInput.value = response
  }

  const handleSuccess = (response: unknown) => {
    console.log("✅ 请求成功:", response)
  }

  const handleError = (error: Error) => {
    console.error("❌ 请求失败:", error)
  }
</script>

<style lang="scss">
  * {
    box-sizing: border-box;
    padding: 0;
    margin: 0;
  }

  .app {
    min-height: 100vh;
    padding: 40px 20px;
    background: linear-gradient(135deg, #f5f7fa 0%, #e9ecef 100%);

    > h1 {
      padding-bottom: 20px;
      margin-bottom: 40px;
      font-size: 36px;
      font-weight: bold;
      color: #313238;
      text-align: center;
      border-bottom: 3px solid #3a84ff;
    }

    .demo-section {
      max-width: 1200px;
      padding: 30px;
      margin: 0 auto 40px;
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 4px 16px rgb(0 0 0 / 8%);

      .section-header {
        margin-bottom: 24px;

        h2 {
          margin-bottom: 8px;
          font-size: 24px;
          color: #313238;
        }

        .section-desc {
          font-size: 14px;
          color: #979ba5;
        }
      }

      .demo-container {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 24px;
        margin-bottom: 20px;

        @media (width <= 1024px) {
          grid-template-columns: 1fr;
        }

        .demo-preview {
          display: flex;
          flex-direction: column;
          gap: 16px;
          align-items: center;
          justify-content: center;
          padding: 30px;
          background: #f5f7fa;
          border: 2px dashed #dcdee5;
          border-radius: 8px;

          .form-demo {
            width: 100%;

            .form-label {
              display: flex;
              gap: 8px;
              align-items: center;
              margin-bottom: 8px;
              font-size: 14px;
              font-weight: 500;
              color: #313238;
            }

            .demo-input,
            .demo-textarea {
              width: 100%;
              padding: 8px 12px;
              font-size: 14px;
              line-height: 1.5;
              color: #313238;
              outline: none;
              background: #fff;
              border: 1px solid #dcdee5;
              border-radius: 2px;
              transition: all 0.3s;

              &::placeholder {
                color: #c4c6cc;
              }
            }

            .demo-input {
              &:hover {
                border-color: #a3c5fd;
              }

              &:focus {
                border-color: #3a84ff;
                box-shadow: 0 0 0 2px rgb(58 132 255 / 10%);
              }
            }

            .demo-textarea {
              resize: vertical;

              &:hover {
                border-color: #a3c5fd;
              }

              &:focus {
                border-color: #3a84ff;
                box-shadow: 0 0 0 2px rgb(58 132 255 / 10%);
              }
            }
          }

          .tip {
            font-size: 13px;
            color: #979ba5;
            text-align: center;
          }
        }

        .code-block {
          overflow: hidden;
          background: #282c34;
          border-radius: 8px;

          .code-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 16px;
            background: #21252b;
            border-bottom: 1px solid #181a1f;

            span {
              font-size: 12px;
              font-weight: 500;
              color: #abb2bf;
            }
          }

          pre {
            padding: 16px;
            margin: 0;
            overflow-x: auto;
            font-family: Consolas, Monaco, monospace;
            font-size: 13px;
            line-height: 1.6;
            color: #abb2bf;
            background: #282c34;

            code {
              font-family: inherit;
            }
          }
        }
      }

      &.api-section {
        .api-table {
          h3 {
            padding-top: 24px;
            margin-bottom: 16px;
            font-size: 18px;
            color: #313238;
          }

          table {
            width: 100%;
            border-collapse: collapse;

            thead {
              background: #f5f7fa;

              th {
                padding: 12px 16px;
                font-size: 14px;
                font-weight: 600;
                color: #313238;
                text-align: left;
                border-bottom: 2px solid #dcdee5;
              }
            }

            tbody {
              tr {
                border-bottom: 1px solid #f0f1f5;

                &:hover {
                  background: #fafbfd;
                }

                td {
                  padding: 12px 16px;
                  font-size: 13px;
                  color: #63656e;

                  code {
                    padding: 2px 6px;
                    font-family: Consolas, Monaco, monospace;
                    font-size: 12px;
                    color: #3a84ff;
                    background: #f0f5ff;
                    border-radius: 3px;
                  }
                }
              }
            }
          }
        }
      }
    }
  }
</style>
