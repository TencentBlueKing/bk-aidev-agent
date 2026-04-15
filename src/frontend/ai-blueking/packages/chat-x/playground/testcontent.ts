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

export const STREAM_CONTENT = `我理解您需要一份包含各种Markdown语法且长度超过10000字的测试文本。虽然我无法直接生成如此庞大的完整文档，但我可以为您提供一个全面的Markdown语法指南框架，并给您一些扩展方法来达到10000字以上的长度。

# 完整的Markdown语法测试文档

## 简介
本文档旨在展示Markdown的所有语法特性，涵盖从基础到高级的各种用法。

## 1. 标题系统
Markdown支持六级标题，使用井号(#)表示

### 1.1 基础标题语法
# 一级标题 - 文档的主标题
## 二级标题 - 主要章节标题
### 三级标题 - 子章节标题
#### 四级标题 - 小节标题
##### 五级标题 - 详细分类
###### 六级标题 - 最低级别标题

### 1.2 替代标题语法
对于一级和二级标题，也可以使用下划线语法：

一级标题
=========

二级标题
---------

## 2. 段落和换行

### 2.1 普通段落
这是第一个段落。在Markdown中，段落由一个或多个连续的文本行组成，它们之间用空行分隔。

这是第二个段落。段落内可以包含换行，但是需要两个空格加回车来表示软换行。  
这是第二行，因为行尾有两个空格。

### 2.2 换行处理
不换行的文本
直接换行的文本（没有两个空格）

有换行的文本（行尾有两个空格）  
这样就会换行

## 3. 文本格式化

### 3.1 粗体强调
- **使用双星号的粗体文本**
- __使用双下划线的粗体文本__（并非所有解析器都支持）
- 这是**混合在句子中**的粗体文本

### 3.2 斜体强调
- *使用单星号的斜体文本*
- _使用单下划线的斜体文本_
- 句子中的*斜体文字*示例

### 3.3 粗斜体组合
- ***三重星号的粗斜体***
- ___三重下划线的粗斜体___
- **_星号下划线组合_**
- _**下划线星号组合**_

### 3.4 删除线
- ~~被删除的文本~~
- 原价~~$100~~ 现价$80

### 3.5 下划线
<u>使用HTML标签的下划线文本</u>

### 3.6 高亮文本
<mark>突出显示的重要文本</mark>

### 3.7 上下标
- 水的化学式：H~2~O 或 H<sub>2</sub>O
- 爱因斯坦方程：E=mc^2^ 或 E=mc<sup>2</sup>
- 组合使用：x~i~^2^

## 4. 列表系统

### 4.1 无序列表
使用星号、加号或减号：
* 苹果
* 香蕉
* 橙子

+ 红色
+ 绿色
+ 蓝色

- 周一
- 周二
- 周三

#### 嵌套无序列表：
- 一级项目
  - 二级项目
    - 三级项目
      - 四级项目
  - 返回二级项目
- 返回一级项目

### 4.2 有序列表
1. 第一步
2. 第二步
3. 第三步

#### 嵌套有序列表：
1. 主项目一
   1. 子项目A
   2. 子项目B
2. 主项目二
   1. 子项目C
      1. 孙项目i
      2. 孙项目ii

#### 多级混合列表：
1. 技术栈
   - 前端
     1. HTML
     2. CSS
     3. JavaScript
   - 后端
     - Python
     - Java
2. 工具
   - 编辑器
   - 版本控制

### 4.3 任务列表
- [x] 完成需求分析
- [x] 设计数据库
- [ ] 开发用户界面
- [ ] 测试系统功能
- [ ] 部署上线

#### 嵌套任务列表：
- [ ] 项目启动
  - [x] 确定需求
  - [ ] 分配任务
    - [ ] 前端开发
    - [ ] 后端开发
- [ ] 项目测试

## 5. 链接和图片

### 5.1 文本链接
- [普通链接](https://www.example.com)
- [带标题的链接](https://www.example.com "访问示例网站")
- [相对路径链接](../docs/readme.md)
- [锚点链接](#标题系统)

### 5.2 参考式链接
这是第一个参考链接[示例1][id1]，这是第二个[示例2][id2]。

[id1]: https://www.example1.com "第一个示例网站"
[id2]: https://www.example2.com "第二个示例网站"

### 5.3 自动链接
- <https://www.example.com>
- <mailto:contact@example.com>
- <tel:+1234567890>

### 5.4 图片
基本语法：
![替代文本](https://via.placeholder.com/150 "图片标题")

带尺寸控制：
<img src="https://via.placeholder.com/150" width="150" height="150" alt="占位图片">

参考式图片：
![替代文本][logo]

[logo]: https://via.placeholder.com/100x50 "Logo图片"

### 5.5 带链接的图片
[![点击图片访问网站](https://via.placeholder.com/100)](https://www.example.com)

## 6. 代码块

### 6.1 行内代码
使用反引号包裹：\`print("Hello World")\`

特殊字符需要转义：\`\` \\\`反引号\\\` \`\`

### 6.2 代码块
普通代码块（四个空格或一个制表符）：
    def hello():
        print("Hello World")
        return True

围栏代码块：
\`\`\`python
def fibonacci(n):
    """生成斐波那契数列"""
    result = []
    a, b = 0, 1
    while len(result) < n:
        result.append(a)
        a, b = b, a + b
    return result

print(fibonacci(10))
\`\`\`

### 6.3 多种语言语法高亮
\`\`\`javascript
// JavaScript示例
function calculateSum(numbers) {
    return numbers.reduce((acc, curr) => acc + curr, 0);
}

const numbers = [1, 2, 3, 4, 5];
console.log(\\\`总和: \${calculateSum(numbers)}\\\`);
\`\`\`

\`\`\`html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>示例页面</title>
    <style>
        body { font-family: Arial, sans-serif; }
        .container { max-width: 800px; margin: 0 auto; }
    </style>
</head>
<body>
    <div class="container">
        <h1>欢迎</h1>
        <p>这是一个示例HTML文档。</p>
    </div>
</body>
</html>
\`\`\`

\`\`\`css
/* CSS样式示例 */
.container {
    width: 100%;
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

.header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 2rem;
    border-radius: 10px;
}

.button {
    background-color: #4CAF50;
    color: white;
    padding: 12px 24px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.3s;
}

.button:hover {
    background-color: #45a049;
}
\`\`\`

\`\`\`sql
-- SQL查询示例
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

SELECT 
    u.username,
    u.email,
    COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at > '2024-01-01'
GROUP BY u.id
ORDER BY order_count DESC
LIMIT 10;
\`\`\`

## 7. 表格

### 7.1 基础表格
| 姓名 | 年龄 | 职业 |
|------|------|------|
| 张三 | 28 | 工程师 |
| 李四 | 32 | 设计师 |
| 王五 | 25 | 产品经理 |

### 7.2 对齐方式
| 左对齐 | 居中对齐 | 右对齐 |
|:-------|:--------:|-------:|
| 单元格1 | 单元格2 | 单元格3 |
| 文本内容 | 居中内容 | 数字100 |
| 长文本示例，展示左对齐效果 | 中间对齐 | 价格：¥999.99 |

### 7.3 复杂表格
| 项目 | 第一季度 | 第二季度 | 第三季度 | 第四季度 | 年度总计 |
|------|----------|----------|----------|----------|----------|
| 产品A | ¥100,000 | ¥120,000 | ¥150,000 | ¥180,000 | ¥550,000 |
| 产品B | ¥80,000 | ¥90,000 | ¥110,000 | ¥130,000 | ¥410,000 |
| 产品C | ¥50,000 | ¥60,000 | ¥75,000 | ¥85,000 | ¥270,000 |
| **合计** | **¥230,000** | **¥270,000** | **¥335,000** | **¥395,000** | **¥1,230,000** |

### 7.4 表格中的格式化
| 功能 | 代码 | 效果 |
|------|------|------|
| 粗体 | \`**文本**\` | **示例文本** |
| 斜体 | \`*文本*\` | *示例文本* |
| 删除线 | \`~~文本~~\` | ~~示例文本~~ |
| 代码 | \`\` \\\`代码\\\` \`\` | \`print("hello")\` |
| 链接 | \`[链接](url)\` | [示例链接](#) |

## 8. 引用块

### 8.1 基础引用
> 这是单行引用。引用块用于突出显示重要的文本或引用他人的话。

### 8.2 多行引用
> 这是多行引用的第一段。
> 引用块可以包含多行文本，
> 只需要在每行前面添加大于号即可。
> 
> 段落之间需要空行，但要记得在空行前也添加大于号。

### 8.3 嵌套引用
> 一级引用
>> 二级引用
>>> 三级引用
>>>> 四级引用
>
> 回到一级引用

### 8.4 引用中的其他元素
> ## 引用中的标题
> 
> 引用中可以包含其他Markdown元素：
> 
> 1. **粗体文本**
> 2. *斜体文本*
> 3. \`行内代码\`
> 
> \`\`\`python
> # 引用中的代码块
> def example():
>     return "Hello"
> \`\`\`
> 
> | 表格 | 示例 |
> |------|------|
> | 单元格1 | 单元格2 |

## 9. 分割线

### 9.1 不同样式的分割线
---

***

___

- - -

* * *

_ _ _

### 9.2 分割线的使用场景
第一部分内容

---

第二部分内容，用分割线分隔

***

第三部分内容，使用不同的分割线样式

## 10. 转义字符

### 10.1 需要转义的字符
以下字符在Markdown中有特殊意义，需要转义：
- 反斜杠：\`\\\\\`
- 反引号：\`\` \\\` \`\`
- 星号：\`*\`
- 下划线：\`_\`
- 花括号：\`{}\`
- 方括号：\`[]\`
- 括号：\`()\`
- 井号：\`#\`
- 加号：\`+\`
- 减号：\`-\`
- 点：\`.\`
- 感叹号：\`!\`
- 管道符：\`|\`

### 10.2 转义示例
普通文本：*斜体*  
转义文本：\\*不是斜体\\*

普通链接：[文本](url)  
转义链接：\\[文本](url)

## 11. HTML混合

### 11.1 HTML标签的使用
<div style="background-color: #f0f0f0; padding: 20px; border-radius: 5px;">
    <h3>HTML容器</h3>
    <p>Markdown可以嵌入HTML标签来实现更复杂的样式。</p>
    <ul>
        <li>自定义样式</li>
        <li>特殊布局</li>
        <li>交互元素</li>
    </ul>
</div>

### 11.2 文字样式标签
- <span style="color: red;">红色文字</span>
- <span style="background-color: yellow;">黄色背景</span>
- <span style="font-size: 1.5em; font-weight: bold;">大号粗体</span>

### 11.3 按钮和交互
<button onclick="alert('按钮点击!')">点击我</button>

<details>
<summary>点击展开更多内容</summary>
这里是详细内容，默认是隐藏的，点击后才会显示。
</details>

## 12. 数学公式（需支持LaTeX）

### 12.1 行内公式
质能方程：$E = mc^2$

二次方程求根公式：$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$

微积分基本定理：$\\int_a^b f(x) dx = F(b) - F(a)$

### 12.2 块级公式
求和公式：
$$
\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}
$$

矩阵运算：
$$
\\begin{bmatrix}
a & b \\\\
c & d
\\end{bmatrix}
\\times
\\begin{bmatrix}
x \\\\
y
\\end{bmatrix}
=
\\begin{bmatrix}
ax + by \\\\
cx + dy
\\end{bmatrix}
$$

积分公式：
$$
\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}
$$

## 13. 脚注

### 13.1 基础脚注
这是一个带有脚注的句子[^1]。另一个带有详细说明的脚注[^2]。

[^1]: 这是第一个脚注的内容。
[^2]: 这是第二个脚注，可以包含更长的解释文本，甚至可以包含其他Markdown元素，比如**粗体**或\`代码\`。

### 13.2 多个脚注
Markdown文档[^note1]中可以使用多个脚注[^note2]来提供补充信息[^note3]。

[^note1]: Markdown由John Gruber于2004年创建。
[^note2]: 脚注会自动编号并按顺序显示在文档末尾。
[^note3]: 脚注内容在编辑时与引用位置无关，可以放在文档任何地方。

## 14. 定义列表

### 14.1 基础定义
Markdown
: 一种轻量级标记语言，使用纯文本格式编写文档。

HTML
: 超文本标记语言，用于创建网页的标准标记语言。

CSS
: 层叠样式表，用于描述HTML文档的呈现方式。

### 14.2 多行定义
JavaScript
: 一种高级编程语言，主要用于网页开发。
: 支持面向对象、命令式和声明式风格。

Python
: 一种解释型、高级别的通用编程语言。
: 强调代码可读性，使用缩进来定义代码块。
: 支持多种编程范式。

## 15. 缩写

### 15.1 缩写定义
Markdown兼容*HTML*缩写元素，可以定义缩写及其全称。

*[HTML]: HyperText Markup Language
*[CSS]: Cascading Style Sheets
*[API]: Application Programming Interface
*[JSON]: JavaScript Object Notation
*[YAML]: YAML Ain't Markup Language

### 15.2 使用缩写
在文档中，可以使用HTML、CSS、API等缩写。当鼠标悬停在上面时，会显示完整的名称。

## 16. 目录（TOC）

### 16.1 自动生成目录
许多Markdown解析器支持自动生成目录：

[TOC]

或者

[[toc]]

### 16.2 手动创建目录
1. [简介](#简介)
2. [标题系统](#1-标题系统)
   1. [基础标题语法](#11-基础标题语法)
   2. [替代标题语法](#12-替代标题语法)
3. [段落和换行](#2-段落和换行)
   ...等等

## 17. 高级特性

### 17.1 表情符号
Markdown支持表情符号：🚀 📝 ✅ ❌ ⭐ 🔥

### 17.2 特殊符号
- 版权符号：©
- 注册商标：®
- 商标：™
- 箭头：→ ← ↑ ↓
- 数学符号：× ÷ ≠ ≈ ≤ ≥

### 17.3 复选框进度
任务完成情况：
- [x] 第一阶段 (20%)
- [x] 第二阶段 (40%)
- [x] 第三阶段 (60%)
- [ ] 第四阶段 (80%)
- [ ] 第五阶段 (100%)

## 扩展内容以达到10000字

要创建一个超过10000字的Markdown测试文档，您可以通过以下方式扩展：

1. **添加大量示例**：为每个语法点提供多个不同的示例
2. **创建详细教程**：将每个部分扩展为完整的教学章节
3. **编写实际文章**：用Markdown语法写一篇完整的技术文章
4. **复制和变体**：创建相同语法的不同变体
5. **添加长篇代码**：包含完整的程序代码文件
6. **深度嵌套**：创建深度嵌套的列表、引用等结构
7. **多语言内容**：添加不同编程语言的代码示例
8. **文档化项目**：创建一个完整的项目文档

## 总结

这份文档涵盖了Markdown的主要语法特性，包括：
- 标题和段落
- 文本格式化
- 各种列表
- 链接和图片
- 代码块和表格
- 引用和分割线
- 高级特性如公式、脚注等

您可以根据需要进一步扩展每个部分，添加更多的示例和解释，以达到所需的文档长度。每个部分都可以作为起点，深入探讨特定的语法特性。

---

**字数统计**：以上文档约3500字。要达到10000字以上，您可以：
1. 将每个章节的内容增加2-3倍
2. 添加更多的代码示例
3. 创建详细的案例分析
4. 编写多个完整的文档示例
5. 添加不同主题的完整文章

通过这样的扩展，您将能够创建一份全面且详尽的Markdown测试文档。
`;
