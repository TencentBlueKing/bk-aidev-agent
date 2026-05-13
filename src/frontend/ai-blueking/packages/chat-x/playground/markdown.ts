/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

export const streamContentX = `
<thinking>
- markstream-vue playground
- A Vue 3 component that renders Markdown string content as HTML, supporting custom components and advanced markdown features.
</thinking>

>>>I'll create a simple Electron + Vue chat application demo. Here's the structure:

[Star on GitHub](https://github.com/Simon-He95/markstream-vue)

<a href="https://simonhe.me/">我是 a 元素标签</a>

https://github.com/Simon-He95/markstream-vue

[【Author: Simon】](https://simonhe.me/)

- **[Link (Test 1)](https://simonhe.me/)**

**[Link (Test 2)](https://simonhe.me/)**

**Markdown链接**：  
1. [GitHub官网](https://github.com)  
2. [知乎 - 有问题就会有答案](https://www.zhihu.com)  
3. **加粗链接**：[Google](https://www.google.com)  
4. 嵌套格式的链接：[*斜体链接*](https://example.com)  

**普通链接**：  
1. https://www.wikipedia.org  
2. http://example.com/path?query=test  
3. 纯文本URL：https://markdown-guide.readthedocs.io

![Vue Markdown Icon](/vue-markdown-icon.svg "Vue Markdown Icon")
*Figure: Vue Markdown Icon (served from /vue-markdown-icon.svg)*

这是 ~~已删除的文本~~，这是一个表情 :smile:。

- [ ] Star this repo
- [x] Fork this repo
- [ ] Create issues
- [x] Submit PRs

##  表格

| 姓名 | 年龄 | 职业 |
|------|------|------|
| 张三 | 25   | 工程师 |
| 李四 | 30   | 设计师 |
| 王五 | 28   | 产品经理 |

### 对齐表格
| 左对齐 | 居中对齐 | 右对齐 |
|:-------|:--------:|-------:|
| 内容1  |  内容2   |  内容3 |
| 内容4  |  内容5   |  内容6 |

我将为您输出泰勒公式的一般形式及其常见展开式。

---

## 0. 薛定谔方程（量子力学）
$$i\\hbar \\frac{\\partial}{\\partial t} \\Psi(\\mathbf{r},t) = \\left[ -\\frac{\\hbar^2}{2m} \\nabla^2 + V(\\mathbf{r},t) \\right] \\Psi(\\mathbf{r},t)$$


## 1. 泰勒公式（Taylor's Formula）

### 一般形式（在点 \\(x = a\\) 处展开）：
\\[
f(x) = f(a) + f'(a)(x-a) + \\frac{f''(a)}{2!}(x-a)^2 + \\frac{f'''(a)}{3!}(x-a)^3 + \\cdots + \\frac{f^{(n)}(a)}{n!}(x-a)^n + R_n(x)
\\]

其中：
- \\(f^{(k)}(a)\\) 是 \\(f(x)\\) 在 \\(x=a\\) 处的 \\(k\\) 阶导数
- \\(R_n(x)\\) 是余项，常见形式有拉格朗日余项：
\\[
R_n(x) = \\frac{f^{(n+1)}(\\xi)}{(n+1)!}(x-a)^{n+1}, \\quad \\xi \\text{ 在 } a \\text{ 和 } x \\text{ 之间}
\\]

---

## 2. 麦克劳林公式（Maclaurin's Formula，即 \\(a=0\\) 时的泰勒公式）：
\\[
f(x) = f(0) + f'(0)x + \\frac{f''(0)}{2!}x^2 + \\frac{f'''(0)}{3!}x^3 + \\cdots + \\frac{f^{(n)}(0)}{n!}x^n + R_n(x)
\\]

---

## 3. 常见函数的麦克劳林展开（前几项）

- **指数函数**：
\\[
e^x = 1 + x + \\frac{x^2}{2!} + \\frac{x^3}{3!} + \\cdots + \\frac{x^n}{n!} + \\cdots, \\quad x \\in \\mathbb{R}
\\]

- **正弦函数**：
\\[
\\sin x = x - \\frac{x^3}{3!} + \\frac{x^5}{5!} - \\frac{x^7}{7!} + \\cdots + (-1)^n \\frac{x^{2n+1}}{(2n+1)!} + \\cdots
\\]

- **余弦函数**：
\\[
\\cos x = 1 - \\frac{x^2}{2!} + \\frac{x^4}{4!} - \\frac{x^6}{6!} + \\cdots + (-1)^n \\frac{x^{2n}}{(2n)!} + \\cdots
\\]

- **自然对数**（在 \\(x=0\\) 附近）：
\\[
\\ln(1+x) = x - \\frac{x^2}{2} + \\frac{x^3}{3} - \\frac{x^4}{4} + \\cdots + (-1)^{n-1} \\frac{x^n}{n} + \\cdots, \\quad -1 < x \\le 1
\\]

- **二项式展开**（\\( (1+x)^m \\)，\\(m\\) 为实数）：
\\[
(1+x)^m = 1 + mx + \\frac{m(m-1)}{2!}x^2 + \\frac{m(m-1)(m-2)}{3!}x^3 + \\cdots, \\quad |x| < 1
\\]

- **矩阵**：
\\[
\\begin{bmatrix}
2x_2 - 8x_3 = 8 \\\\
5x_1 - 5x_3 = 10
\\end{bmatrix}
\\]

- **公式**


- **代入数据**
   \\[
   \\frac{363}{15,\\!135} \\times 100\\% = 2.398\\%
   \\]

- **计算工具验证**
   通过数学计算工具确认结果：
   \`363 ÷ 15,135 × 100 = 2.39841427...\`

- **差异说明**
   $$E=mc^2$$

---

如果您需要某个特定函数在特定点的泰勒展开，请告诉我，我可以为您详细写出。

::: warning
这是一个警告块。
:::

::: tip 提示标题
这是带标题的提示。
:::

::: error 错误块
这是一个错误块。
:::

مرحبا بكم في عالم اللغة العربية!
1. First, let's set up the project:

\`\`\`shellscript
# Create Vue project
npm create vue@latest electron-vue-chat

# Navigate to project
cd electron-vue-chat

# Install dependencies
npm install
npm install electron electron-builder vue-router

# Install dev dependencies
npm install -D electron-dev-server concurrently wait-on
\`\`\`

2. Create the main Electron file:

\`\`\`javascript:electron/main.js
const { app, BrowserWindow } = require('electron');
const path = require('path');
const isDev = process.env.NODE_ENV === 'development';

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 680,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  const url = isDev
    ? 'http://localhost:5173'
    : \`file://\${path.join(__dirname, '../dist/index.html')}\`;

  mainWindow.loadURL(url);

  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.on('ready', createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});
\`\`\`

3. Update package.json:

\`\`\`diff json:package.json
{
  "name": "markstream-vue",
  "type": "module",
- "version": "0.0.49",
+ "version": "0.0.54-beta.1",
  "packageManager": "pnpm@10.16.1",
  "description": "A Vue 3 component that renders Markdown string content as HTML, supporting custom components and advanced markdown features.",
  "author": "Simon He",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "git + git@github.com:Simon-He95/markstream-vue.git"
  },
  "bugs": {
    "url": "https://github.com/Simon-He95/markstream-vue/issues"
  },
  "keywords": [
    "vue",
    "vue3",
    "markdown",
    "markdown-to-html",
    "markdown-renderer",
    "vue-markdown",
    "vue-component",
    "html",
    "renderer",
    "custom-component"
  ],
  "exports": {
    ".": {
      "types": "./dist/types/exports.d.ts",
      "import": "./dist/index.js",
      "require": "./dist/index.cjs"
    },
    "./index.css": "./dist/index.css",
    "./index.tailwind.css": "./dist/index.tailwind.css",
    "./tailwind": "./dist/tailwind.ts"
  },
  "main": "./dist/index.js",
  "module": "./dist/index.js",
  "types": "./dist/types/exports.d.ts",
  "files": [
    "dist"
  ],
}
\`\`\`

4. Create chat components \\(diversified languages\\):

\`\`\`python:src/server/app.py
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Message(BaseModel):
    sender: str
    text: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/echo")
def echo(msg: Message):
    return {"reply": f"Echo: {msg.text}"}
\`\`\`

5. Create a native module example (C++):

\`\`\`cpp:src/native/compute.cpp
#include <bits/stdc++.h>
using namespace std;

int fibonacci(int n){
  if(n<=1) return n;
  int a=0,b=1;
  for(int i=2;i<=n;++i){ int c=a+b; a=b; b=c; }
  return b;
}

int main(){
  ios::sync_with_stdio(false);
  cin.tie(nullptr);
  cout << "fib(10)=" << fibonacci(10) << "\n";
  return 0;
}
\`\`\`

6. Update the main App.vue:

\`\`\`vue:src/App.vue
<template>
  <router-view />
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: Arial, sans-serif;
}
</style>
\`\`\`

7. Set up the router:

\`\`\`javascript:src/router/index.js
import { createRouter, createWebHistory } from 'vue-router';
import ChatView from '../views/ChatView.vue';

const routes = [
  {
    path: '/',
    name: 'chat',
    component: ChatView
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;
\`\`\`

8. Update main.js:

\`\`\`javascript:src/main.js
import { createApp } from 'vue';
import App from './App.vue';
import router from './router';

createApp(App).use(router).mount('#app');
\`\`\`

9. Mermaid graphic:

\`\`\`mermaid
graph TD
    Kira_Yamato[基拉·大和]
    Lacus_Clyne[拉克丝·克莱因]
    Athrun_Zala[阿斯兰·萨拉]
    Cagalli_Yula_Athha[卡嘉莉·尤拉·阿斯哈]
    Shinn_Asuka[真·飞鸟]
    Lunamaria_Hawke[露娜玛丽亚·霍克]
    COMPASS[世界和平监视组织COMPASS]
    Foundation[芬德申王国]
    Orphee_Lam_Tao[奥尔菲·拉姆·陶]
    %% 节点定义结束，开始定义边
    Kira_Yamato ---|恋人| Lacus_Clyne
    Kira_Yamato ---|挚友| Athrun_Zala
    Kira_Yamato -->|隶属| COMPASS
    Kira_Yamato -->|前辈| Shinn_Asuka
    Lacus_Clyne -->|初代总裁| COMPASS
    Athrun_Zala ---|恋人| Cagalli_Yula_Athha
    Athrun_Zala -.->|协力| COMPASS
    Shinn_Asuka ---|恋人| Lunamaria_Hawke
    Shinn_Asuka -->|隶属| COMPASS
    Lunamaria_Hawke -->|隶属| COMPASS
    COMPASS -->|对立| Foundation
    Orphee_Lam_Tao -->|隶属| Foundation
    Orphee_Lam_Tao -.->|追求| Lacus_Clyne
\`\`\`

\`\`\`mermaid
  xychart
    title "销售收入"
    x-axis ["一月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "十二月"]
    y-axis "收入" 4000 --> 11000
    line [5000, 6000, 7500, 8200, 9500, 10500, 11000, 10200, 9200, 8500, 7000, 6000]
\`\`\`


\`\`\`infographic
infographic list-row-simple-horizontal-arrow
data
  items
    - label 步骤 1
      desc 开始
    - label 步骤 2
      desc 进行中
    - label 步骤 3
      desc 完成
\`\`\`

---
# 复杂数学公式

### 1. **理解 \\(\\boldsymbol{\\alpha}^T \\boldsymbol{\\beta} = 0\\) 的含义**
   - \\(\\boldsymbol{\\alpha}\\) 和 \\(\\boldsymbol{\\beta}\\) 是三维列向量，因此 \\(\\boldsymbol{\\alpha}^T \\boldsymbol{\\beta}\\) 表示它们的点积（内积）。
   - \\(\\boldsymbol{\\alpha}^T \\boldsymbol{\\beta} = 0\\) 意味着向量 \\(\\boldsymbol{\\alpha}\\) 和 \\(\\boldsymbol{\\beta}\\) 正交（即垂直），因为点积为零表示它们之间的夹角为 90 度。

### 2. **正交补空间的概念**
   - 在线性代数中，对于一个子空间 \\(W\\)，它的正交补空间（记为 \\(W^\\perp\\)）定义为所有与 \\(W\\) 中每个向量正交的向量的集合。即：
     \\[
     W^\\perp = \\{ \\mathbf{v} \\in \\mathbb{R}^3 \\mid \\mathbf{v} \\cdot \\mathbf{w} = 0 \\text{ 对于所有 } \\mathbf{w} \\in W \\}
     \\]
   - 例如，如果 \\(W\\) 是由一个向量 \\(\\boldsymbol{\\alpha}\\) 张成的一维子空间（即 \\(W = \\operatorname{span}\\{\\boldsymbol{\\alpha}\\}\\)），那么 \\(W^\\perp\\) 就是所有与 \\(\\boldsymbol{\\alpha}\\) 正交的向量构成的二维平面。
### 3. **\\(\\boldsymbol{\\alpha}^T \\boldsymbol{\\beta} = 0\\) 与正交补空间的联系**
   - 当 \\(\\boldsymbol{\\alpha}^T \\boldsymbol{\\beta} = 0\\) 时，这意味着：
     - \\(\\boldsymbol{\\beta}\\) 属于 \\(\\operatorname{span}\\{\\boldsymbol{\\alpha}\\}\\) 的正交补空间，即 \\(\\boldsymbol{\\beta} \\in (\\operatorname{span}\\{\\boldsymbol{\\alpha}\\})^\\perp\\)。
     - 同样，\\(\\boldsymbol{\\alpha}\\) 也属于 \\(\\operatorname{span}\\{\\boldsymbol{\\beta}\\}\\) 的正交补空间，即 \\(\\boldsymbol{\\alpha} \\in (\\operatorname{span}\\{\\boldsymbol{\\beta}\\})^\\perp\\)。
   - 换句话说，\\(\\boldsymbol{\\beta}\\) 与 \\(\\boldsymbol{\\alpha}\\) 张成的直线正交，因此 \\(\\boldsymbol{\\beta}\\) 位于该直线的垂直平面（即正交补空间）上。反之亦然。

### 4. **在三维空间中的几何意义**
   - 在三维空间中，如果 \\(\\boldsymbol{\\alpha}\\) 是一个非零向量，那么 \\(\\operatorname{span}\\{\\boldsymbol{\\alpha}\\}\\) 是一条通过原点的直线，而它的正交补空间 \\((\\operatorname{span}\\{\\boldsymbol{\\alpha}\\})^\\perp\\) 是一个通过原点且与该直线垂直的平面。
   - \\(\\boldsymbol{\\alpha}^T \\boldsymbol{\\beta} = 0\\) 表示 \\(\\boldsymbol{\\beta}\\) 位于这个垂直平面上。同样，如果 \\(\\boldsymbol{\\beta}\\) 非零，那么 \\(\\boldsymbol{\\alpha}\\) 也位于与 \\(\\boldsymbol{\\beta}\\) 垂直的平面上。

### 5. **推广到更一般的情况**
   - 如果考虑多个向量，正交补空间的概念可以扩展。例如，如果有一组向量 \\(\\{\\boldsymbol{\\alpha}_1, \\boldsymbol{\\alpha}_2, \\ldots, \\boldsymbol{\\alpha}_k\\}\\)，那么它们的张成子空间 \\(W = \\operatorname{span}\\{\\boldsymbol{\\alpha}_1, \\ldots, \\boldsymbol{\\alpha}_k\\}\\) 的正交补空间 \\(W^\\perp\\) 包含所有与这些向量正交的向量。
   - 在这种情况下，\\(\\boldsymbol{\\alpha}^T \\boldsymbol{\\beta} = 0\\) 可以看作 \\(\\boldsymbol{\\beta}\\) 与 \\(W\\) 正交的一个特例（当 \\(W\\) 只由 \\(\\boldsymbol{\\alpha}\\) 张成时）。
总之，\\(\\boldsymbol{\\alpha}^T \\boldsymbol{\\beta} = 0\\) 直接体现了正交补空间的关系：它表明一个向量属于另一个向量张成子空间的正交补空间。如果你有更多向量或子空间，这种联系可以进一步深化。

**示例：** emm\`1-(5)\`、\`3-(3)\`、\`3-(4)\` complex test \`1-(4)\`“heiheihei”中，hello world。
`;
export const streamLatexContent = `
在文本中嵌入数学公式，如：勾股定理 $ a^2 + b^2 = c^2 $，欧拉公式 $ e^{i\\pi} + 1 = 0 $。

圆的面积公式是

$$
S = \\pi r^2
$$

，其中 $ r $ 是半径。

二次方程 \\( ax^2 + bx + c = 0 \\) 的解为

\\[
x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}
\\]
。

## 块级公式

### 基础数学运算

$$
\\begin{aligned}
a + b &= c \\\\
d - e &= f \\\\
g \\times h &= i \\\\
\\frac{j}{k} &= l
\\end{aligned}
$$

### 平方根和指数

$$
\\sqrt{x} = x^{\\frac{1}{2}}
$$

$$
\\sqrt[n]{x} = x^{\\frac{1}{n}}
$$

$$
e^{i\\theta} = \\cos\\theta + i\\sin\\theta
$$

### 分数和比例

$$
\\frac{\\partial f}{\\partial x} = \\lim_{h \\to 0} \\frac{f(x+h) - f(x)}{h}
$$

$$
\\frac{a}{b} = \\frac{c}{d} \\Rightarrow ad = bc
$$

### 求和与积分

#### 求和公式

$$
\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}
$$

$$
\\sum_{i=1}^{n} i^2 = \\frac{n(n+1)(2n+1)}{6}
$$

#### 积分公式

$$
\\int_a^b f(x) dx = F(b) - F(a)
$$

$$
\\int_{-\\infty}^{+\\infty} e^{-x^2} dx = \\sqrt{\\pi}
$$

$$
\\int_0^{\\pi} \\sin x dx = 2
$$



### 统计学公式

#### 正态分布

$$
f(x) = \\frac{1}{\\sigma\\sqrt{2\\pi}} e^{-\\frac{(x-\\mu)^2}{2\\sigma^2}}
$$

#### 贝叶斯定理

$$
P(A|B) = \\frac{P(B|A) \\cdot P(A)}{P(B)}
$$

#### 标准差

$$
\\sigma = \\sqrt{\\frac{1}{N}\\sum_{i=1}^{N}(x_i - \\mu)^2}
$$

### 三角函数

$$
\\sin^2\\theta + \\cos^2\\theta = 1
$$

$$
\\tan\\theta = \\frac{\\sin\\theta}{\\cos\\theta}
$$

$$
e^{i\\theta} = \\cos\\theta + i\\sin\\theta
$$

### 级数展开

#### 泰勒级数

$$
f(x) = \\sum_{n=0}^{\\infty} \\frac{f^{(n)}(a)}{n!}(x-a)^n
$$

#### 指数函数展开

$$
e^x = \\sum_{n=0}^{\\infty} \\frac{x^n}{n!} = 1 + x + \\frac{x^2}{2!} + \\frac{x^3}{3!} + \\cdots
$$

#### 正弦函数展开

$$
\\sin x = \\sum_{n=0}^{\\infty} \\frac{(-1)^n x^{2n+1}}{(2n+1)!} = x - \\frac{x^3}{3!} + \\frac{x^5}{5!} - \\cdots
$$

### 复数运算

复数的一般形式： $ z = a + bi $

复数的模： $ |z| = \\sqrt{a^2 + b^2} $

复数的乘法：

$$
(a + bi)(c + di) = (ac - bd) + (ad + bc)i
$$

德摩弗定理：

$$
(\\cos\\theta + i\\sin\\theta)^n = \\cos(n\\theta) + i\\sin(n\\theta)
$$

### 极限

$$
\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1
$$

$$
\\lim_{x \\to \\infty} \\left(1 + \\frac{1}{x}\\right)^x = e
$$

$$
\\lim_{n \\to \\infty} \\sqrt[n]{n} = 1
$$

### 组合数学

排列数： $ P(n,r) = \\frac{n!}{(n-r)!} $

组合数： $ C(n,r) = \\binom{n}{r} = \\frac{n!}{r!(n-r)!} $

二项式定理：

$$
(x + y)^n = \\sum_{k=0}^{n} \\binom{n}{k} x^{n-k} y^k
$$



三维向量的叉积：

$$
\\vec{a} \\times \\vec{b} = \\begin{vmatrix}
\\vec{i} & \\vec{j} & \\vec{k} \\\\
a_1 & a_2 & a_3 \\\\
b_1 & b_2 & b_3
\\end{vmatrix}
$$


### 支持的语法格式

本示例支持以下 LaTeX 语法格式：

#### 行内公式
- 使用单个 $ 包围：$E=mc^2$
- 使用 \\( \\) 包围：\\(a^2+b^2=c^2\\)
- 使用两个 $ 包围（行内块级）：$$E=mc^2$$
- 使用 \\[ \\] 包围（行内块级）：\\[a^2+b^2=c^2\\]

#### 块级公式
- 使用双 $$ 包围（独占行）：
$$
\\int_a^b f(x)dx = F(b) - F(a)
$$
- 使用 \\[ \\] 包围（独占行）：
\\[
\\sum_{i=1}^n i = \\frac{n(n+1)}{2}
\\]

> **注意**：LaTeX 公式的渲染依赖于 KaTeX 库，确保已正确配置相关依赖。
`;
export const streamMermaidContent = `
Here are several Mermaid diagram examples 

#### 1. Flowchart (Vertical)

\`\`\` mermaid
graph TD
    A[Start] --> B{Data Valid?}
    B -->|Yes| C[Process Data]
    B -->|No| D[Error Handling]
    C --> E[Generate Report]
    D --> E
    E --> F[End]
    style A fill:#2ecc71,stroke:#27ae60
    style F fill:#e74c3c,stroke:#c0392b
\`\`\`

#### 2. Sequence Diagram

\`\`\` mermaid
sequenceDiagram
    participant Client
    participant Server
    participant Database
    
    Client->>Server: POST /api/data
    Server->>Database: INSERT record
    Database-->>Server: Success
    Server-->>Client: 201 Created
\`\`\`

#### 3. Quadrant Chart

\`\`\`mermaid
quadrantChart
    title Reach and engagement of campaigns
    x-axis Low Reach --> High Reach
    y-axis Low Engagement --> High Engagement
    quadrant-1 We should expand
    quadrant-2 Need to promote
    quadrant-3 Re-evaluate
    quadrant-4 May be improved
    Campaign A: [0.3, 0.6]
    Campaign B: [0.45, 0.23]
    Campaign C: [0.57, 0.69]
    Campaign D: [0.78, 0.34]
    Campaign E: [0.40, 0.34]
    Campaign F: [0.35, 0.78]
\`\`\`
`;
export const streamCodeContent = `
Here's a Python code block example that demonstrates how to calculate Fibonacci numbers:

\`\`\` python
def fibonacci(n):
    """
    Calculate the nth Fibonacci number
    :param n: The position in the Fibonacci sequence (must be a positive integer)
    :return: The value at position n
    """
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        a, b = 0, 1
        for _ in range(2, n+1):
            a, b = b, a + b
        return b

# Example usage
if __name__ == "__main__":
    num = 10
    print(f"The {num}th Fibonacci number is: {fibonacci(num)}")
    
    # Print the first 15 Fibonacci numbers
    print("First 15 Fibonacci numbers:")
    for i in range(1, 16):
        print(fibonacci(i), end=" ")
\`\`\`

This code includes:

1. A function to compute Fibonacci numbers
2. Docstring documentation
3. Example usage in the main block
4. A loop to print the first 15 numbers

You can modify the parameters or output format as needed. The Fibonacci sequence here starts with fib(1) = 1, fib(2) = 1.
`;
export const commonContent = `---
__Advertisement :)__

- __[pica](https://nodeca.github.io/pica/demo/)__ - high quality and fast image
  resize in browser.
- __[babelfish](https://github.com/nodeca/babelfish/)__ - developer friendly
  i18n with plurals support and easy syntax.

You will like those projects!

---

# h1 Heading 8-)
## h2 Heading
### h3 Heading
#### h4 Heading
##### h5 Heading
###### h6 Heading


## Horizontal Rules

___

---

***


## Typographic replacements

Enable typographer option to see result.

(c) (C) (r) (R) (tm) (TM) (p) (P) +-

test.. test... test..... test?..... test!....

!!!!!! ???? ,,  -- ---

"Smartypants, double quotes" and 'single quotes'


## Emphasis

**This is bold text**

__This is bold text__

*This is italic text*

_This is italic text_

~~Strikethrough~~


## Blockquotes


> Blockquotes can also be nested...
>> ...by using additional greater-than signs right next to each other...
> > > ...or with spaces between arrows.


## Lists

Unordered

+ Create a list by starting a line with \`+\`, \`-\`, or \`*\`
+ Sub-lists are made by indenting 2 spaces:
  - Marker character change forces new list start:
    * Ac tristique libero volutpat at
    + Facilisis in pretium nisl aliquet
    - Nulla volutpat aliquam velit
+ Very easy!

Ordered

1. Lorem ipsum dolor sit amet
2. Consectetur adipiscing elit
3. Integer molestie lorem at massa


1. You can use sequential numbers...
1. ...or keep all the numbers as \`1.\`

Start numbering with offset:

57. foo
1. bar


## Code

Inline \`code\`

Indented code

    // Some comments
    line 1 of code
    line 2 of code
    line 3 of code


Block code "fences"

\`\`\`
Sample text here...
\`\`\`

Syntax highlighting

\`\`\` js
var foo = function (bar) {
  return bar++;
};

console.log(foo(5));
\`\`\`

## Tables

| Option | Description |
| ------ | ----------- |
| data   | path to data files to supply the data that will be passed into templates. |
| engine | engine to be used for processing templates. Handlebars is the default. |
| ext    | extension to be used for dest files. |

Right aligned columns

| Option | Description |
| ------:| -----------:|
| data   | path to data files to supply the data that will be passed into templates. |
| engine | engine to be used for processing templates. Handlebars is the default. |
| ext    | extension to be used for dest files. |


## Links

[link text](http://dev.nodeca.com)

[link with title](http://nodeca.github.io/pica/demo/ "title text!")

Autoconverted link https://github.com/nodeca/pica (enable linkify to see)


## Images

![Minion](https://octodex.github.com/images/minion.png)
![Stormtroopocat](https://octodex.github.com/images/stormtroopocat.jpg "The Stormtroopocat")

Like links, Images also have a footnote style syntax

![Alt text][id]

With a reference later in the document defining the URL location:

[id]: https://octodex.github.com/images/dojocat.jpg  "The Dojocat"


## Plugins

The killer feature of \`markdown-it\` is very effective support of
[syntax plugins](https://www.npmjs.org/browse/keyword/markdown-it-plugin).


### [Emojies](https://github.com/markdown-it/markdown-it-emoji)

> Classic markup: :wink: :cry: :laughing: :yum:
>
> Shortcuts (emoticons): :-) :-( 8-) ;)

see [how to change output](https://github.com/markdown-it/markdown-it-emoji#change-output) with twemoji.


### [Subscript](https://github.com/markdown-it/markdown-it-sub) / [Superscript](https://github.com/markdown-it/markdown-it-sup)

- 19^th^
- H~2~O


### [<ins>](https://github.com/markdown-it/markdown-it-ins)

++Inserted text++


### [<mark>](https://github.com/markdown-it/markdown-it-mark)

==Marked text==


### [Footnotes](https://github.com/markdown-it/markdown-it-footnote)

Footnote 1 link[^first].

Footnote 2 link[^second].

Inline footnote^[Text of inline footnote] definition.

Duplicated footnote reference[^second].



### [Definition lists](https://github.com/markdown-it/markdown-it-deflist)

Term 1

:   Definition 1
with lazy continuation.

Term 2 with *inline markup*

:   Definition 2

        { some code, part of Definition 2 }

    Third paragraph of definition 2.

_Compact style:_

Term 1
  ~ Definition 1

Term 2
  ~ Definition 2a
  ~ Definition 2b


### [Abbreviations](https://github.com/markdown-it/markdown-it-abbr)

This is HTML abbreviation example.

It converts "HTML", but keep intact partial entries like "xxxHTMLyyy" and so on.

*[HTML]: Hyper Text Markup Language

### [Custom containers](https://github.com/markdown-it/markdown-it-container)

::: warning
*here be dragons*
:::

`;
export const testContent = `
# 深度解析：从技术底层到生态实践的全栈开发知识体系构建

## 引言：为什么我们需要系统化的技术认知？

在数字化浪潮席卷全球的今天，软件开发早已突破"写代码解决问题"的单一维度，演变为融合计算机科学理论、工程化思维、行业场景理解与持续创新的复合型领域。无论是初学者面临的"知识碎片化"困境，还是资深开发者遭遇的"技术选型焦虑"，本质都源于对技术体系缺乏全局视角的串联。本文将以「全栈开发」为线索，从底层原理到上层应用逐层拆解，结合具体案例与数据支撑，构建一套可验证、可扩展的知识框架——这不仅是一次技术的巡礼，更是对"如何高效学习"这一永恒命题的实践回应。

---

## 第一章 计算机科学基石：那些决定上限的基础原理

### 1.1 计算的本质：从图灵机到现代CPU的抽象演进

1936年，艾伦·图灵提出的「图灵机」模型（Turing Machine）首次用数学语言定义了「计算」的边界：一条无限长的纸带（存储）、一个读写头（控制器）和一组状态转移规则（程序），这个看似简陋的思想实验，却奠定了现代计算机的理论基础。当我们今天讨论「高性能计算」「分布式系统」时，本质上仍在图灵机的框架下优化输入/输出效率与状态管理策略。

现代CPU（中央处理器）则是这一理论的工程化结晶。以Intel Core i9-13900K为例，其采用「混合架构设计」（Performance Cores + Efficient Cores），通过硬件线程调度器（Intel Thread Director）动态分配任务：计算密集型任务（如视频编码）由8个性能核（最高5.8GHz）处理，而高并发但低复杂度的任务（如网页渲染）则交给16个能效核（优化功耗）。这种分层设计背后，是对「阿姆达尔定律」（Amdahl's Law）的深刻实践——提升并行计算效率的关键，在于识别并优化程序中的串行瓶颈部分。

> **知识点延伸**：冯·诺依曼体系结构（存储程序概念）与哈佛体系结构（指令/数据分离存储）的对比，解释了为何嵌入式设备（如STM32单片机）常采用后者以提升实时性。

### 1.2 数据结构与算法：代码背后的「逻辑骨架」

任何软件系统的核心功能，最终都会转化为对数据的操作——存储、检索、修改与删除。选择合适的数据结构，能让时间复杂度从O(n²)降至O(log n)，这在百万级数据处理的场景中意味着从「分钟级响应」到「毫秒级反馈」的质变。

以电商平台的商品搜索功能为例：若采用线性表（数组）存储所有商品信息，每次搜索需遍历全部数据（O(n)）；若改用哈希表（Hash Table）建立「商品ID→详情」的映射，查找时间可压缩至O(1)；若进一步引入倒排索引（Inverted Index，将关键词映射到包含它的商品列表），结合B+树（平衡多路搜索树）实现范围查询（如价格区间筛选），则能同时满足精确匹配与模糊检索的需求。

常见算法的时间复杂度对比表：
| 算法类型       | 典型场景                | 平均时间复杂度 | 最坏情况       |
|----------------|-------------------------|----------------|----------------|
| 排序           | 商品列表排序            | 快速排序O(n log n) | 冒泡排序O(n²)  |
| 搜索           | 用户ID查询              | 哈希表O(1)     | 二叉搜索树O(n) |
| 图遍历         | 社交网络关系分析        | BFS/DFS O(V+E) | Dijkstra O((V+E)log V) |
| 动态规划       | 最优路径规划（如地图导航）| O(n²)          | O(2^n)（无优化）|

> **实践建议**：LeetCode高频题库（Top 100）的练习应聚焦于「问题抽象能力」——将业务需求转化为「查找/排序/最短路径」等经典模型，而非死记硬背代码模板。

### 1.3 操作系统：资源调度的「隐形管家」

操作系统（OS）是用户程序与硬件之间的抽象层，其核心功能可概括为「进程管理」「内存管理」「文件系统」与「设备驱动」四大模块。以Linux内核（当前主流服务器操作系统）为例，其采用「CFS（完全公平调度器）」管理多任务：通过虚拟运行时间（vruntime）计算每个进程的CPU占用权重，确保短任务优先执行的同时，避免长任务被饿死。

内存管理的「页式存储」机制（将物理内存划分为4KB/页，虚拟地址通过页表映射）解决了程序地址空间隔离的问题，而「LRU（最近最少使用）算法」则用于淘汰不活跃的页缓存（Page Cache），平衡性能与资源消耗。当我们在浏览器中打开多个标签页时，后台未激活的页面数据会被自动换出到磁盘交换区（Swap），这正是页式管理的典型应用。

> **关键指标**：Linux系统的「上下文切换次数」（通过\`vmstat\`命令监控）超过1万次/秒时，可能引发性能瓶颈——过多的进程抢占会导致CPU花费大量时间保存/恢复寄存器状态。

---

## 第二章 前端开发：用户交互的「最后一公里」

### 2.1 浏览器工作原理：从URL输入到页面渲染的全流程

当你在地址栏输入\`https://www.example.com\`并回车，背后会发生一系列精密协作：  
1. **DNS解析**：浏览器首先检查本地缓存（Hosts文件→浏览器缓存→系统DNS缓存），若未命中则向配置的DNS服务器（如8.8.8.8）发起UDP请求，最终获得目标服务器的IP地址（如192.0.2.1）。  
2. **TCP三次握手**：建立可靠连接（SYN→SYN+ACK→ACK），HTTPS场景下还需额外进行TLS握手（交换密钥证书，协商加密算法）。  
3. **HTTP请求/响应**：浏览器发送包含\`User-Agent\`、\`Cookie\`等头部的GET请求，服务器返回HTML文档（状态码200）及关联的CSS/JS资源。  
4. **渲染流水线**：  
   - **HTML解析**：构建DOM树（Document Object Model），遇到\`<script>\`标签会暂停解析（除非标记为\`async\`/\`defer\`）；  
   - **CSS解析**：生成CSSOM树（CSS Object Model），与DOM树合并为渲染树（Render Tree，仅包含可见元素）；  
   - **布局（Layout）**：计算每个节点的几何信息（位置、尺寸）；  
   - **绘制（Paint）**：将布局结果转换为屏幕像素（栅格化）；  
   - **合成（Composite）**：对多层内容（如固定导航栏+滚动内容）按顺序绘制到屏幕。

> **性能优化点**：通过Chrome DevTools的「Performance面板」可观察到，首屏加载时间（FP/FCP）的瓶颈常出现在「未优化的图片（如未压缩的PNG）」或「阻塞渲染的同步JS脚本」。

### 2.2 HTML/CSS/JavaScript：前端三剑客的深度协作

**HTML5的语义化标签**（如\`<header>\`、\`<article>\`、\`<section>\`）不仅是SEO友好的关键，更能帮助屏幕阅读器（视障用户辅助工具）正确理解页面结构。例如，使用\`<nav>\`包裹导航菜单，比传统的\`<div class="nav">\`更符合无障碍标准。

**CSS的层叠与继承机制**决定了样式优先级（权重计算公式：内联样式1000 > ID选择器100 > 类选择器10 > 标签选择器1）。Flexbox（弹性布局）与Grid（网格布局）的出现，彻底改变了传统「浮动+定位」的复杂方案——一个简单的\`display: grid; grid-template-columns: 1fr 3fr; gap: 16px;\`即可实现响应式的两栏布局。

**JavaScript的运行时环境**（浏览器中的BOM/DOM API，Node.js中的fs/net模块）决定了其能力边界。ES6+的新特性（如箭头函数、Promise、async/await）大幅提升了异步代码的可读性：  
\`\`\`javascript
// 传统回调地狱 vs 现代async/await
// 回调地狱示例
fetch('/api/user').then(res => res.json()).then(user => {
  fetch(\`/api/orders/\${user.id}\`).then(res => res.json()).then(orders => {
    console.log(orders);
  });
});

// async/await优化
async function loadUserData() {
  const user = await fetch('/api/user').then(res => res.json());
  const orders = await fetch(\`/api/orders/\${user.id}\`).then(res => res.json());
  console.log(orders);
}
\`\`\`

> **前沿趋势**：WebAssembly（WASM）允许C/Rust等语言编译为高性能字节码，在浏览器中运行（如Figma的矢量编辑核心即用Rust+WASM实现），突破了JS的执行效率限制。

### 2.3 前端框架的演进逻辑：从jQuery到React/Vue/Angular

早期jQuery（2006年诞生）通过封装DOM操作（如\`$('#id').hide()\`）解决了浏览器兼容性问题（IE6/7/8的差异），但随着单页应用（SPA）的兴起，其「操作DOM直接更新视图」的模式暴露出维护成本高的缺陷——数据变化时需要手动同步UI，容易产生不一致。

现代框架（React/Vue/Angular）的核心创新在于「声明式编程+虚拟DOM」：  
- **React** 采用「组件化+单向数据流」，通过JSX语法将UI描述为函数（\`function App() { return <div>{data}</div>; }\`），利用虚拟DOM（轻量级的JS对象树）计算最小更新路径（Diff算法），最终只修改真实DOM中变化的部分。  
- **Vue** 则强调「响应式数据绑定」，通过Object.defineProperty（Vue 2）或Proxy（Vue 3）监听数据变化，自动触发视图更新，配合单文件组件（SFC，\`.vue\`文件整合模板/脚本/样式）提升开发效率。  
- **Angular** 作为全功能框架，内置依赖注入（DI）、路由守卫、表单验证等企业级特性，更适合大型团队协作。

> **数据对比**：根据2023年Stack Overflow开发者调查，React（40.5%）和Vue（19.3%）仍是前端框架的首选，而Svelte（基于编译时优化的新兴框架）在性能敏感场景（如动画密集型应用）中逐渐崭露头角。

---

## 第三章 后端开发：业务逻辑的「中枢神经系统」

### 3.1 编程语言与运行时：选择背后的权衡

后端开发的语言选择需综合考虑「性能需求」「开发效率」「生态成熟度」三大因素：  
- **Java**（JVM平台）凭借强类型、丰富的类库（Spring全家桶）和企业级支持（如微服务框架Spring Cloud），长期占据金融、政务等高稳定性场景的头部位置。JVM的「即时编译（JIT）」技术（将热点代码编译为机器码）使其在长时间运行的服务中性能接近原生（如TPS可达万级）。  
- **Python**（解释型语言）因语法简洁（缩进定义代码块）、库生态丰富（Django/Flask用于Web，NumPy/Pandas用于数据分析），成为快速原型开发与AI集成的首选。但其全局解释器锁（GIL）限制了多线程并行能力（CPU密集型任务建议改用多进程或C扩展）。  
- **Go**（Google开发）专为高并发场景设计，内置协程（Goroutine，轻量级线程，初始栈仅2KB）和内置HTTP服务器，适合构建微服务（如Kubernetes的控制平面即用Go编写）。其编译为静态二进制文件的特性，避免了动态语言的依赖管理问题。  
- **Rust**（系统级语言）通过所有权系统（编译时检查内存安全）和零成本抽象，在保证性能（媲美C/C++）的同时消除了内存泄漏和数据竞争风险，逐渐应用于区块链（如Solana）、游戏引擎等对安全性要求极高的领域。

> **性能基准测试**（Techempower Web Framework Benchmarks）：处理JSON序列化（简单API响应）时，Rust的Actix-web（约1.2M req/s）> Go的Gin（约0.9M req/s）> Java的Spring Boot（约0.6M req/s）> Python的FastAPI（约0.3M req/s）。

### 3.2 数据库：从关系型到NoSQL的多元选择

数据库是业务数据的「数字仓库」，其选型直接影响系统的扩展性与一致性保障：  

#### 关系型数据库（RDBMS）  
以MySQL（当前最流行的开源RDBMS）为例，其采用「InnoDB存储引擎」（支持事务ACID特性）和「B+树索引」（主键索引的叶子节点直接存储数据行，二级索引指向主键）。典型的电商订单表设计会包含以下优化：  
- **索引策略**：为高频查询条件（如\`user_id\`、\`create_time\`）创建联合索引（\`INDEX idx_user_time (user_id, create_time)\`），利用最左前缀原则加速范围查询；  
- **分库分表**：当单表数据量超过500万行时，通过水平分表（按用户ID哈希拆分）或垂直分表（将大字段如\`order_detail\`拆分到关联表）降低单节点压力；  
- **事务隔离级别**：默认的「可重复读（REPEATABLE READ）」通过MVCC（多版本并发控制）解决幻读问题，平衡一致性与并发性能。

#### NoSQL数据库  
- **Redis**（内存键值存储）凭借「单线程+事件驱动」架构（避免锁竞争）和丰富的数据结构（字符串、哈希、有序集合等），成为缓存（热点数据存储）、分布式锁（SETNX命令）和消息队列（Stream类型）的首选。其持久化机制（RDB快照+AOF日志）可在宕机后恢复数据。  
- **MongoDB**（文档型数据库）以「BSON格式（类JSON的二进制扩展）」存储灵活模式的数据（如用户画像的多维度标签），支持地理空间索引（2dsphere）和聚合管道（类似SQL的GROUP BY操作）。  
- **Elasticsearch**（搜索引擎）基于Lucene库，通过「倒排索引+分片集群」实现全文检索（如商品标题的模糊匹配）和复杂分析（如日志的聚合统计），广泛应用于站内搜索和大数据分析场景。

> **数据一致性模型**：CAP定理（一致性Consistency、可用性Availability、分区容错性Partition Tolerance）指出，分布式系统最多只能同时满足两项——例如，CP系统（如etcd）优先保证数据一致，适合配置管理；AP系统（如Cassandra）优先保证可用性，适合日志记录。

### 3.3 微服务架构：从单体到分布式的演进之路

随着业务规模扩大，单体应用（Monolithic Architecture）的缺陷逐渐显现：代码耦合度高（修改支付模块可能影响订单模块）、部署效率低（全量打包重启）、技术栈单一（无法为不同模块选用最优语言）。微服务架构（Microservices）通过「将单体拆分为多个独立服务」解决这些问题，每个服务聚焦单一业务能力（如用户服务、订单服务、库存服务），并通过轻量级通信（REST/gRPC）协作。

#### 关键组件与挑战  
- **服务注册与发现**：Consul/Eureka维护服务实例的健康状态（心跳检测），客户端通过查询注册中心获取目标服务的可用节点列表（如订单服务调用库存服务时，动态选择负载最低的实例）。  
- **API网关**：Kong/Traefik作为统一入口，处理跨域（CORS）、鉴权（JWT验证）、限流（令牌桶算法）等横切关注点，减轻后端服务的负担。  
- **分布式事务**：Saga模式（将长事务拆分为多个本地事务，通过补偿操作回滚）和TCC模式（Try-Confirm-Cancel三阶段提交）用于保证跨服务的数据一致性（如电商下单涉及扣库存、支付、发券三个子事务）。  
- **链路追踪**：Jaeger/Zipkin通过「TraceID（全局唯一请求ID）」串联各个服务的日志，可视化展示请求在微服务间的流转路径（如定位某个慢请求是由库存服务的数据库慢查询引起）。

> **实践案例**：Netflix的微服务架构包含超过700个独立服务，通过「混沌工程」（主动注入网络延迟、服务宕机等故障）验证系统的容错能力，其开源工具Hystrix（熔断器模式）已成为故障隔离的标准方案。

---

## 第四章 DevOps与云原生：高效交付的「自动化引擎」

### 4.1 持续集成/持续交付（CI/CD）：从手动部署到自动化流水线

传统软件开发中，「代码提交→本地测试→打包→手动部署到测试环境→反馈问题→重新修改」的流程效率低下且易出错。CI/CD通过自动化工具链（如GitLab CI/Jenkins/GitHub Actions）实现：  
- **持续集成（CI）**：开发者每次推送代码到Git仓库时，触发自动化构建（编译、单元测试、静态代码分析），确保新代码不会破坏现有功能（如SonarQube检测代码异味）。  
- **持续交付（CD）**：通过自动化部署将经过测试的代码发布到预发布环境（Staging），供产品经理和测试团队验收；最终通过人工确认后，自动部署到生产环境（Production）。  

典型的CI/CD流水线包含以下阶段：  
1. **代码拉取**：从Git仓库（如GitHub）获取最新提交；  
2. **依赖安装**：运行\`npm install\`（前端）或\`mvn dependency:resolve\`（Java）；  
3. **构建打包**：前端生成静态资源（\`npm run build\`），后端编译为可执行JAR/WAR；  
4. **自动化测试**：单元测试（JUnit/pytest）、接口测试（Postman/Newman）、性能测试（JMeter）；  
5. **容器化**：使用Docker将应用及其依赖打包
`;
export const streamContent = `
**斜体**
_斜体_
*斜体*
**粗体**
__粗体__
***粗斜体***
___粗斜体___
**_粗斜体_**
_**粗斜体**_

#### 斜体

#### 4. 链接与 a 标签示例
**Markdown 行内链接**：[腾讯蓝鲸](https://bk.tencent.com/) · [chat-x npm](https://www.npmjs.com/package/@blueking/chat-x)
**Markdown 自动链接**：<https://github.com/TencentBlueKing/bk-aidev-agent>

#### 3. Align content

::: hljs-left
This is left aligned content.
:::

::: hljs-center
This is center aligned content.
:::

::: hljs-right
This is right aligned content.
:::

---

#### 4. Code markdown 示例

行内代码：使用 \`npm run build\` 或 \`const x = 1\` 包裹短片段。

无语言标注的围栏代码块：

\`\`\`
plain text / 任意文本
no language hint
\`\`\`

**JavaScript**

\`\`\` js
export const sum = (a, b) => a + b;

async function fetchUser(id) {
  const res = await fetch(\`/api/users/\${id}\`);
  if (!res.ok) throw new Error('failed');
  return res.json();
}
\`\`\`

**TypeScript**

\`\`\` ts
interface User {
  id: string;
  name: string;
}

function greet(user: User): string {
  return \`Hello, \${user.name}\`;
}
\`\`\`

**Vue SFC（节选）**

\`\`\` vue
<script setup lang="ts">
import { ref } from 'vue';

const count = ref(0);
</script>

<template>
  <button type="button" @click="count++">{{ count }}</button>
</template>
\`\`\`

**Bash**

\`\`\` bash
pnpm install
pnpm dev:ui
git status
\`\`\`

**JSON**

\`\`\` json
{
  "name": "chat-x",
  "version": "0.0.19",
  "private": false
}
\`\`\`

**缩进代码块（4 空格）**

    function legacy() {
      return 'indented block';
    }
`;
