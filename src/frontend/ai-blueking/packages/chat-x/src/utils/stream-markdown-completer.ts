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
/**
 * Stream Markdown Completer
 *
 * 用于在流式渲染中补全未闭合的 Markdown 和 KaTeX 语法，
 * 避免因语法不完整导致的渲染错误或布局混乱。
 */

export interface CompletionResult {
  content: string; // 补全后的完整内容
  isIncomplete?: boolean; // 是否处于不完整状态（正在输入命令）
  suffix: string; // 补全的后缀
}

type ScanState = 'CODE_BLOCK' | 'INLINE_CODE' | 'MATH' | 'NORMAL';

/**
 * 检测字符是否是中文字符
 */
function isChinese(char: string | undefined): boolean {
  if (!char) return false;
  const code = char.charCodeAt(0);
  // CJK 统一汉字范围
  return code >= 0x4e00 && code <= 0x9fff;
}

/**
 * 检测 $$ 是否是有效的块级公式定界符
 * 块级公式的特征：
 * 1. $$ 在行首（前面只有空白）
 * 2. 或者 $$ 后面紧跟换行符
 * 3. 且 $$ 后面不是中文字符
 */
function isValidBlockMathDelimiter(content: string, pos: number): boolean {
  // pos 指向第一个 $ 的位置

  // 检查 $$ 后面的内容
  const afterPos = pos + 2;
  if (afterPos < content.length) {
    const nextChar = content[afterPos];

    // 如果后面是中文字符，不是有效的数学定界符
    if (isChinese(nextChar)) {
      return false;
    }

    // 如果后面是换行符，是块级公式
    if (nextChar === '\n') {
      return true;
    }

    // 如果后面是空格，检查是否紧跟中文
    if (nextChar === ' ') {
      let i = afterPos + 1;
      while (i < content.length && content[i] === ' ') {
        i++;
      }
      if (i < content.length && isChinese(content[i])) {
        return false;
      }
    }
  }

  // 检查 $$ 是否在行首
  let k = pos - 1;
  while (k >= 0 && content[k] === ' ') {
    k--;
  }
  if (k < 0 || content[k] === '\n') {
    // $$ 在行首，是块级公式
    return true;
  }

  // $$ 在行中间，检查后面是否是数学内容
  return looksLikeMathContent(content, afterPos);
}

/**
 * 检测 $ 或 $$ 后面的内容是否像是数学公式
 * 如果后面紧跟中文字符，很可能是描述性文本而非数学公式
 */
function looksLikeMathContent(content: string, pos: number): boolean {
  if (pos >= content.length) {
    // $ 在末尾，检查 $ 前面的内容来判断
    // 如果 $ 前面是中文或标点（如 "单个 $"），可能是描述性文本
    const dollarPos = pos - 1;
    if (dollarPos >= 0) {
      // 检查 $ 前面是否有空格
      const prevChar = content[dollarPos - 1];
      if (prevChar === ' ' || prevChar === '：' || prevChar === ':') {
        // $ 前面是空格或冒号，可能是描述性的 "$"
        // 向前查找，看是否在描述性文本中
        let j = dollarPos - 1;
        while (j >= 0 && content[j] === ' ') {
          j--;
        }
        if (j >= 0 && isChinese(content[j])) {
          // $ 前面空格之前是中文，可能是描述性文本如 "单个 $"
          return false;
        }
      }
    }
    return true; // 其他情况，假设是数学公式开始
  }

  const nextChar = content[pos];

  // 如果后面是中文字符，不是数学公式
  if (isChinese(nextChar)) {
    return false;
  }

  // 如果后面是空格或换行，需要更仔细判断
  if (nextChar === ' ' || nextChar === '\n') {
    // 先向后查找配对的 $
    let endDollar = -1;
    for (let i = pos + 1; i < content.length; i++) {
      if (content[i] === '$') {
        // 检查是否是转义的
        if (i > 0 && content[i - 1] === '\\') continue;
        endDollar = i;
        break;
      }
      // 如果遇到换行符（对于行内公式），停止搜索
      if (content[i] === '\n') break;
    }

    if (endDollar !== -1) {
      // 找到了配对的 $，检查中间内容
      const mathContent = content.slice(pos, endDollar);
      // 如果中间内容主要是中文，不是数学公式
      const chineseCount = (mathContent.match(/[\u4e00-\u9fff]/g) || []).length;
      const totalNonSpace = mathContent.replace(/\s/g, '').length;
      if (chineseCount > 0 && chineseCount >= totalNonSpace * 0.3) {
        // 中文占比超过 30%，不是数学公式
        return false;
      }
    } else {
      // 没有找到配对的 $，检查空格后是否紧跟中文
      let i = pos + 1;
      while (i < content.length && content[i] === ' ') {
        i++;
      }
      if (i < content.length && isChinese(content[i])) {
        return false;
      }
    }
  }

  // 其他情况，认为是数学公式
  return true;
}

/**
 * 检测定界符（如 \(、\[）后面的内容是否像数学公式
 * 用于区分描述性文本如 "使用 \( \) 包围" 和实际公式 "\(a^2+b^2\)"
 */
function looksLikeMathContentAfterDelimiter(content: string, pos: number): boolean {
  if (pos >= content.length) {
    // 定界符在末尾，假设是数学开始
    return true;
  }

  const nextChar = content[pos];

  // 如果后面是空格，检查空格后的内容
  if (nextChar === ' ') {
    let i = pos + 1;
    while (i < content.length && content[i] === ' ') {
      i++;
    }

    if (i < content.length) {
      const charAfterSpaces = content[i];

      // 空格后是闭合定界符（如 \)、\]），说明是描述性的如 "\( \)"
      if (charAfterSpaces === '\\') {
        const nextNext = i + 1 < content.length ? content[i + 1] : '';
        if (nextNext === ')' || nextNext === ']') {
          return false;
        }
      }

      // 空格后是中文，不是数学公式
      if (isChinese(charAfterSpaces)) {
        return false;
      }
    }
  }

  // 如果紧跟中文字符，不是数学公式
  if (isChinese(nextChar)) {
    return false;
  }

  // 其他情况，认为是数学公式
  return true;
}

// 常见的 LaTeX 环境名列表，用于猜测不完整的环境名
const COMMON_ENVS = [
  'aligned',
  'align',
  'equation',
  'gather',
  'matrix',
  'pmatrix',
  'bmatrix',
  'vmatrix',
  'Bmatrix',
  'Vmatrix',
  'cases',
  'array',
  'split',
  'multline',
];

// 独立的符号命令（不需要参数）
const STANDALONE_SYMBOLS = new Set([
  'alpha',
  'beta',
  'gamma',
  'delta',
  'epsilon',
  'varepsilon',
  'zeta',
  'eta',
  'theta',
  'vartheta',
  'iota',
  'kappa',
  'lambda',
  'mu',
  'nu',
  'xi',
  'pi',
  'varpi',
  'rho',
  'varrho',
  'sigma',
  'varsigma',
  'tau',
  'upsilon',
  'phi',
  'varphi',
  'chi',
  'psi',
  'omega',
  'Gamma',
  'Delta',
  'Theta',
  'Lambda',
  'Xi',
  'Pi',
  'Sigma',
  'Upsilon',
  'Phi',
  'Psi',
  'Omega',
  'times',
  'div',
  'cdot',
  'pm',
  'mp',
  'ast',
  'star',
  'circ',
  'bullet',
  'ldots',
  'cdots',
  'vdots',
  'ddots',
  'infty',
  'nabla',
  'partial',
  'forall',
  'exists',
  'nexists',
  'leq',
  'geq',
  'neq',
  'approx',
  'equiv',
  'sim',
  'cong',
  'propto',
  'in',
  'notin',
  'subset',
  'supset',
  'subseteq',
  'supseteq',
  'cup',
  'cap',
  'setminus',
  'emptyset',
  'to',
  'gets',
  'leftarrow',
  'rightarrow',
  'Leftarrow',
  'Rightarrow',
  'leftrightarrow',
  'Leftrightarrow',
  'quad',
  'qquad',
  'space',
  'sin',
  'cos',
  'tan',
  'cot',
  'sec',
  'csc',
  'arcsin',
  'arccos',
  'arctan',
  'sinh',
  'cosh',
  'tanh',
  'coth',
  'log',
  'ln',
  'lg',
  'exp',
  'lim',
  'limsup',
  'liminf',
  'max',
  'min',
  'sup',
  'inf',
  'det',
  'dim',
  'ker',
  'hom',
  'deg',
  'arg',
  'sum',
  'prod',
  'int',
  'iint',
  'iiint',
  'oint',
  'll',
  'gg',
  'le',
  'ge',
  'ne',
]);

// 需要参数的命令
const COMMANDS_REQUIRING_ARGS = new Set([
  'begin',
  'end',
  'frac',
  'dfrac',
  'tfrac',
  'cfrac',
  'sqrt',
  'root',
  'text',
  'textbf',
  'textit',
  'textrm',
  'textsf',
  'texttt',
  'mathbf',
  'mathit',
  'mathrm',
  'mathsf',
  'mathtt',
  'mathcal',
  'mathbb',
  'mathfrak',
  'mathscr',
  'hat',
  'bar',
  'vec',
  'dot',
  'ddot',
  'tilde',
  'widehat',
  'widetilde',
  'overline',
  'underline',
  'overbrace',
  'underbrace',
  'overset',
  'underset',
  'binom',
  'dbinom',
  'tbinom',
]);

export function completeMarkdownSyntax(content: string): CompletionResult {
  if (!content) {
    return { content: '', suffix: '' };
  }

  const len = content.length;
  let i = 0;

  // State
  let state: ScanState = 'NORMAL';

  // Context Data
  let fenceChar = '';
  let fenceLength = 0;
  let backtickLength = 0;
  let mathDelim = ''; // '$', '$$', '\\(', '\\['
  let mathOpenStack: string[] = [];
  let mathBraceCount = 0;
  let mathStartPos = 0; // 记录数学块开始位置

  while (i < len) {
    const char = content[i];

    // ----------------------------------------------------------------
    // NORMAL STATE
    // ----------------------------------------------------------------
    if (state === 'NORMAL') {
      // Escape char in NORMAL: skip next
      if (char === '\\') {
        // Special case: check for \( or \[ which start math mode
        if (i + 1 < len) {
          const nextChar = content[i + 1];
          if (nextChar === '(') {
            // 检查 \( 后面是否像数学内容
            // 如果 \( 后面是空格或中文（如 "\( \) 包围"），跳过
            if (!looksLikeMathContentAfterDelimiter(content, i + 2)) {
              i += 2; // 跳过 \(，当作普通文本
              continue;
            }
            state = 'MATH';
            mathDelim = '\\(';
            mathOpenStack = [];
            mathBraceCount = 0;
            mathStartPos = i + 2; // 记录 \( 后的位置
            i += 2;
            continue;
          } else if (nextChar === '[') {
            // 检查 \[ 后面是否像数学内容
            if (!looksLikeMathContentAfterDelimiter(content, i + 2)) {
              i += 2; // 跳过 \[，当作普通文本
              continue;
            }
            state = 'MATH';
            mathDelim = '\\[';
            mathOpenStack = [];
            mathBraceCount = 0;
            mathStartPos = i + 2; // 记录 \[ 后的位置
            i += 2;
            continue;
          }
        }

        // Skip escaped char
        i += 2;
        continue;
      }

      // Code Fence Check
      // Check if this is a fence start: ` or ~
      // Must be at start of line or preceded by spaces (up to 3)
      if (char === '`' || char === '~') {
        // Backward check for indentation
        let k = i - 1;
        let spaceCount = 0;
        let isStart = false;

        while (k >= 0) {
          if (content[k] === '\n') {
            isStart = true;
            break;
          }
          if (content[k] !== ' ') {
            isStart = false; // Non-space char found
            break;
          }
          spaceCount++;
          k--;
        }
        if (k < 0) isStart = true; // Start of file

        if (isStart && spaceCount <= 3) {
          let count = 0;
          let j = i;
          while (j < len && content[j] === char) {
            count++;
            j++;
          }
          if (count >= 3) {
            state = 'CODE_BLOCK';
            fenceChar = char;
            fenceLength = count;
            i = j;
            continue;
          }
        }
      }

      // Math Block/Inline ($ or $$)
      if (char === '$') {
        if (i + 1 < len && content[i + 1] === '$') {
          // 检测 $$ 是否是有效的块级公式定界符
          // 如果后面紧跟中文字符，跳过
          if (!isValidBlockMathDelimiter(content, i)) {
            i += 2; // 跳过这对 $$，当作普通文本
            continue;
          }

          state = 'MATH';
          mathDelim = '$$';
          mathOpenStack = [];
          mathBraceCount = 0;
          mathStartPos = i + 2; // 记录 $$ 后的位置
          i += 2;
        } else {
          // Inline Math check
          // If followed by a digit, treat as currency and skip (e.g. $100)
          const nextChar = i + 1 < len ? content[i + 1] : null;
          if (nextChar && /\d/.test(nextChar)) {
            i++;
            continue;
          }

          // 如果 $ 后面紧跟中文字符，跳过（描述性文本）
          if (!looksLikeMathContent(content, i + 1)) {
            i++;
            continue;
          }

          state = 'MATH';
          mathDelim = '$';
          mathOpenStack = [];
          mathBraceCount = 0;
          mathStartPos = i + 1; // 记录 $ 后的位置
          i += 1;
        }
        continue;
      }

      // Inline Code
      if (char === '`') {
        let count = 0;
        let j = i;
        while (j < len && content[j] === '`') {
          count++;
          j++;
        }
        state = 'INLINE_CODE';
        backtickLength = count;
        i = j;
        continue;
      }

      i++;
    }
    // ----------------------------------------------------------------
    // CODE_BLOCK STATE
    // ----------------------------------------------------------------
    else if (state === 'CODE_BLOCK') {
      // Check for closing fence
      if (char === fenceChar) {
        // Backward check for indentation
        let k = i - 1;
        let spaceCount = 0;
        let isStart = false;

        while (k >= 0) {
          if (content[k] === '\n') {
            isStart = true;
            break;
          }
          if (content[k] !== ' ') {
            isStart = false; // Non-space char found
            break;
          }
          spaceCount++;
          k--;
        }
        if (k < 0) isStart = true;

        if (isStart && spaceCount <= 3) {
          let count = 0;
          let j = i;
          while (j < len && content[j] === fenceChar) {
            count++;
            j++;
          }
          if (count >= fenceLength) {
            // Check if rest of line is whitespace
            let m = j;
            let isClosed = true;
            while (m < len && content[m] !== '\n') {
              if (content[m] !== ' ' && content[m] !== '\r') {
                isClosed = false;
                break;
              }
              m++;
            }
            if (isClosed) {
              state = 'NORMAL';
              i = m; // consume the rest of line
              continue;
            }
          }
        }
      }
      i++;
    }
    // ----------------------------------------------------------------
    // INLINE_CODE STATE
    // ----------------------------------------------------------------
    else if (state === 'INLINE_CODE') {
      if (char === '`') {
        let count = 0;
        let j = i;
        while (j < len && content[j] === '`') {
          count++;
          j++;
        }
        if (count === backtickLength) {
          state = 'NORMAL';
          i = j;
          continue;
        }
        // if backticks found but length mismatch, treat as content
        i = j;
        continue;
      }
      i++;
    }
    // ----------------------------------------------------------------
    // MATH STATE
    // ----------------------------------------------------------------
    else if (state === 'MATH') {
      // Escape handling in Math
      if (char === '\\') {
        // Check for delimiters \) or \]
        if (mathDelim === '\\(' && i + 1 < len && content[i + 1] === ')') {
          state = 'NORMAL';
          i += 2;
          continue;
        }
        if (mathDelim === '\\[' && i + 1 < len && content[i + 1] === ']') {
          state = 'NORMAL';
          i += 2;
          continue;
        }

        // Check for \begin{...} or \end{...}
        const commandResult = parseLatexCommand(content, i);
        if (commandResult) {
          const { cmd, endIdx } = commandResult;

          // Look ahead for {envName}
          const envNameResult = parseLatexEnvName(content, endIdx);

          if (cmd === 'begin' && envNameResult) {
            mathOpenStack.push(envNameResult.name);
            i = envNameResult.endIdx;
            continue;
          } else if (cmd === 'end' && envNameResult) {
            const last = mathOpenStack[mathOpenStack.length - 1];
            if (last === envNameResult.name) {
              mathOpenStack.pop();
            }
            i = envNameResult.endIdx;
            continue;
          }

          // Other commands or failed begin/end parsing
          // Just consume the command part if it was a command,
          // but carefully: if parseLatexEnvName failed (e.g. unclosed brace),
          // we should let the main loop handle the braces.
          // So if it is 'begin' but no name, we just skip 'begin'.

          i = endIdx;
          continue;
        }

        // Regular escape
        i += 2;
        continue;
      }

      // Check for delimiters $ or $$
      if (mathDelim === '$$' && char === '$') {
        if (i + 1 < len && content[i + 1] === '$') {
          state = 'NORMAL';
          i += 2;
          continue;
        }
      } else if (mathDelim === '$' && char === '$') {
        state = 'NORMAL';
        i += 1;
        continue;
      }

      // Check for braces {}
      if (char === '{') {
        mathBraceCount++;
      } else if (char === '}') {
        if (mathBraceCount > 0) mathBraceCount--;
      }

      i++;
    }
  }

  // Generate Suffix
  let suffix = '';

  if (state === 'CODE_BLOCK') {
    suffix = '\n' + fenceChar.repeat(fenceLength);
  } else if (state === 'INLINE_CODE') {
    suffix = '`'.repeat(backtickLength);
  } else if (state === 'NORMAL') {
    // 在 NORMAL 状态下检查其他未闭合的 Markdown 语法
    const lines = content.split('\n');
    const lastLine = lines[lines.length - 1] || '';

    // 检查链接语法 [text](url)
    const linkSuffix = checkLink(content);
    if (linkSuffix) {
      suffix += linkSuffix;
    }

    // 检查图片语法 ![alt](url)
    const imageSuffix = checkImage(content);
    if (imageSuffix) {
      suffix += imageSuffix;
    }

    // 检查成对符号语法（在最后一行检查）
    // 粗体 **text** 或 __text__
    const boldSuffix = checkPairedMarker(lastLine, '**') || checkPairedMarker(lastLine, '__');
    if (boldSuffix) {
      // 检查补全后是否会产生 hr 模式（连续 3 个或更多的 *、- 或 _）
      // 例如：末尾是 "**"，补全 "**" 后变成 "****"，会被解析为 hr
      suffix += getSafeMarkerSuffix(lastLine, boldSuffix);
    }

    // 斜体 *text* 或 _text_（需要排除已经检查过的 ** 和 __）
    if (!boldSuffix) {
      const italicSuffix = checkSingleMarker(lastLine, '*') || checkSingleMarker(lastLine, '_');
      if (italicSuffix) {
        // 同样需要检查 hr 模式
        suffix += getSafeMarkerSuffix(lastLine, italicSuffix);
      }
    }

    // 删除线 ~~text~~
    const strikeSuffix = checkPairedMarker(lastLine, '~~');
    if (strikeSuffix) {
      suffix += strikeSuffix;
    }

    // 高亮 ==text== (markdown-it-mark)
    const markSuffix = checkPairedMarker(lastLine, '==');
    if (markSuffix) {
      suffix += markSuffix;
    }

    // 插入 ++text++ (markdown-it-ins)
    const insSuffix = checkPairedMarker(lastLine, '++');
    if (insSuffix) {
      suffix += insSuffix;
    }

    // 脚注语法 (markdown-it-footnote)
    // 脚注引用 [^name] 和 内联脚注 ^[text]
    const footnoteSuffix = checkFootnote(lastLine);
    if (footnoteSuffix) {
      suffix += footnoteSuffix;
    }

    // 上标 ^text^ (markdown-it-sup)
    // 注意：需要排除脚注语法 ^[ 和 [^
    const supSuffix = checkSupSubscript(lastLine, '^');
    if (supSuffix) {
      suffix += supSuffix;
    }

    // 下标 ~text~ (markdown-it-sub)
    // 注意：需要排除删除线 ~~
    const subSuffix = checkSupSubscript(lastLine, '~');
    if (subSuffix) {
      suffix += subSuffix;
    }

    // 自定义容器 ::: name ... ::: (markdown-it-container)
    const containerSuffix = checkContainer(lines);
    if (containerSuffix) {
      suffix += containerSuffix;
    }
  } else if (state === 'MATH') {
    // 检测是否处于不完整的 LaTeX 命令输入状态
    // 在这种状态下，不补全闭合符号，让内容保持为普通文本
    // 避免无效的 LaTeX 导致渲染失败
    if (isIncompleteLatexInput(content, mathStartPos)) {
      return {
        content,
        suffix: '',
        isIncomplete: true,
      };
    }

    // 智能补全逻辑：
    // 1. 尝试修复不完整的尾部语法（如 ^, _），使其可渲染
    // 2. 闭合未闭合的括号和环境
    // 3. 始终闭合定界符，确保作为 Math 渲染（而不是普通文本）

    const trimmed = content.trimEnd();
    const lastChar = trimmed.length > 0 ? trimmed[trimmed.length - 1] : '';

    // 1. 语法修复
    // 如果以 ^ 或 _ 结尾，补全 {} 以避免 "Unexpected end of input" 错误
    if (lastChar === '^' || lastChar === '_') {
      suffix += '{}';
    }
    // 如果以 \ 结尾，补全空格，防止转义掉补全的 $
    // 注意：这个情况已经被 isIncompleteLatexInput 处理了，这里作为 fallback
    else if (lastChar === '\\') {
      suffix += ' ';
    }

    // 2. 闭合结构
    // Close braces first
    if (mathBraceCount > 0) {
      suffix += '}'.repeat(mathBraceCount);
    }
    // Close environments (reverse order)
    const tempEnvStack = [...mathOpenStack];
    while (tempEnvStack.length > 0) {
      const env = tempEnvStack.pop();
      suffix += `\\end{${env}}`;
    }

    // 3. 闭合定界符
    if (mathDelim === '\\(') suffix += '\\)';
    else if (mathDelim === '\\[') {
      if (content.length > 0 && content[content.length - 1] !== '\n') {
        suffix += '\n';
      }
      suffix += '\\]';
    } else if (mathDelim === '$$') {
      // 优化：只有当内容不为空，且不是刚刚开始输入 $$ 时才补换行
      // 防止空内容时补全出 $$ \n $$ 这种奇怪结构
      // 实际上，只要闭合 $$ 即可，markdown parser 对块级公式的识别通常要求前后有换行，
      // 但对于 stream 补全，我们主要目的是让 katex 能渲染。
      // Katex 在 display mode 下不需要换行符。
      // Markdown-it-latex 插件可能需要。

      // 如果当前内容以 \n 结尾，直接补 $$
      // 如果不是，补 \n$$

      if (content.length > 0 && content[content.length - 1] !== '\n') {
        suffix += '\n';
      }
      suffix += '$$';
    } else {
      suffix += mathDelim;
    }
  }

  return {
    content: content + suffix,
    suffix,
  };
}

/**
 * 根据部分环境名猜测完整的环境名
 * 用于未来可能的智能补全功能
 */
export function guessEnvironmentName(partial: string): string {
  for (const env of COMMON_ENVS) {
    if (env.startsWith(partial)) {
      return env;
    }
  }
  return '';
}

/**
 * 检查自定义容器语法 ::: name ... ::: (markdown-it-container)
 * 返回需要补全的后缀
 */
function checkContainer(lines: string[]): string {
  // 计算 ::: 的开闭数量
  let openCount = 0;

  for (const line of lines) {
    const trimmed = line.trim();
    // 开始标记: ::: 后面跟着容器名称
    if (/^:::\s*\S+/.test(trimmed)) {
      openCount++;
    }
    // 结束标记: 单独的 :::
    else if (trimmed === ':::') {
      openCount--;
    }
  }

  if (openCount > 0) {
    return '\n:::';
  }
  return '';
}

/**
 * 检查脚注语法 (markdown-it-footnote)
 * 脚注引用: [^name]
 * 内联脚注: ^[text]
 * 返回需要补全的后缀
 */
function checkFootnote(line: string): string {
  // 1. 检查内联脚注 ^[text]
  // 从后向前找最后一个 ^[
  const inlineFootnoteStart = line.lastIndexOf('^[');
  if (inlineFootnoteStart !== -1) {
    const afterStart = line.slice(inlineFootnoteStart + 2);
    // 如果 ^[ 后面没有 ]，需要补全
    if (!afterStart.includes(']')) {
      return ']';
    }
  }

  // 2. 检查脚注引用 [^name]
  // 从后向前找最后一个 [^
  const footnoteRefStart = line.lastIndexOf('[^');
  if (footnoteRefStart !== -1) {
    const afterStart = line.slice(footnoteRefStart + 2);
    // 如果 [^ 后面没有 ]，需要补全
    if (!afterStart.includes(']')) {
      return ']';
    }
  }

  return '';
}

/**
 * 检查图片语法 ![alt](url)
 * 返回需要补全的后缀
 */
function checkImage(content: string): string {
  const lines = content.split('\n');
  const lastLine = lines[lines.length - 1] || '';

  // 查找 ![ 的位置
  const lastImageStart = lastLine.lastIndexOf('![');
  if (lastImageStart === -1) return '';

  const afterOpen = lastLine.slice(lastImageStart + 1); // 从 [ 开始

  // 检查是否已经完整闭合
  if (/^\[[^\]]*\]\([^)]*\)/.test(afterOpen)) {
    return '';
  }

  // 情况1: ![ 后面没有 ]，需要补全 ](url)
  if (!afterOpen.includes(']')) {
    return '](#)';
  }

  // 情况2: 有 ] 但没有 (
  const closeBracketPos = afterOpen.indexOf(']');
  const afterClose = afterOpen.slice(closeBracketPos + 1);

  if (!afterClose.startsWith('(')) {
    return '';
  }

  // 情况3: 有 ]( 但没有 )，需要补全 )
  if (afterClose.startsWith('(') && !afterClose.includes(')')) {
    return ')';
  }

  return '';
}

/**
 * 检查链接语法 [text](url)
 * 返回需要补全的后缀
 */
function checkLink(content: string): string {
  // 从后向前查找最后一个未闭合的 [
  const lines = content.split('\n');
  const lastLine = lines[lines.length - 1] || '';

  // 在最后一行中查找未闭合的链接语法
  const lastOpenBracket = lastLine.lastIndexOf('[');
  if (lastOpenBracket === -1) return '';

  // 检查是否是图片语法 ![，如果是则跳过（由 checkImage 处理）
  if (lastOpenBracket > 0 && lastLine[lastOpenBracket - 1] === '!') {
    return '';
  }

  const afterOpen = lastLine.slice(lastOpenBracket);

  // 检查是否已经完整闭合
  if (/^\[[^\]]*\]\([^)]*\)/.test(afterOpen)) {
    return '';
  }

  // 情况1: [ 后面没有 ]，需要补全 ](url)
  if (!afterOpen.includes(']')) {
    return '](#)';
  }

  // 情况2: 有 ] 但没有 (，需要补全 (url)
  const closeBracketPos = afterOpen.indexOf(']');
  const afterClose = afterOpen.slice(closeBracketPos + 1);

  if (!afterClose.startsWith('(')) {
    // ] 后面没有紧跟 (，可能是普通文本中的 []
    return '';
  }

  // 情况3: 有 ]( 但没有 )，需要补全 )
  if (afterClose.startsWith('(') && !afterClose.includes(')')) {
    return ')';
  }

  return '';
}

/**
 * 检查成对标记符号（如 **、~~、==、++、__）
 * 返回需要补全的后缀
 */
function checkPairedMarker(line: string, marker: string): string {
  // 计算标记出现的次数
  let count = 0;
  let i = 0;
  while (i < line.length) {
    if (line.substring(i, i + marker.length) === marker) {
      // 检查是否被转义
      if (i === 0 || line[i - 1] !== '\\') {
        count++;
        i += marker.length;
        continue;
      }
    }
    i++;
  }

  // 如果是奇数个，需要补全
  if (count % 2 === 1) {
    return marker;
  }
  return '';
}

/**
 * 检查单字符标记符号（如 *、_）
 * 需要排除已经被双字符标记处理的情况
 * 返回需要补全的后缀
 */
function checkSingleMarker(line: string, marker: string): string {
  // 先移除双字符标记
  const doubleMarker = marker + marker;
  const lineWithoutDouble = line.split(doubleMarker).join('');

  // 计算单字符标记出现的次数
  let count = 0;
  for (let i = 0; i < lineWithoutDouble.length; i++) {
    if (lineWithoutDouble[i] === marker) {
      // 检查是否被转义
      if (i === 0 || lineWithoutDouble[i - 1] !== '\\') {
        count++;
      }
    }
  }

  // 如果是奇数个，需要补全
  if (count % 2 === 1) {
    return marker;
  }
  return '';
}

/**
 * 检查上标/下标语法 (markdown-it-sup / markdown-it-sub)
 * 上标: ^text^
 * 下标: ~text~
 * 返回需要补全的后缀
 */
function checkSupSubscript(line: string, marker: string): string {
  // 首先移除 LaTeX 数学块，因为 LaTeX 中的 ^ 和 ~ 是数学语法，不是 sup/sub
  // 移除 $...$ 和 $$...$$ 以及 \(...\) 和 \[...\]
  let cleanLine = line;

  // 移除 $$...$$ (块级公式)
  cleanLine = cleanLine.replace(/\$\$[^$]*\$\$/g, '');
  // 移除 $...$ (行内公式)，但要小心不要移除单独的 $
  cleanLine = cleanLine.replace(/\$[^$\n]+\$/g, '');
  // 移除 \(...\)
  cleanLine = cleanLine.replace(/\\\([^)]*\\\)/g, '');
  // 移除 \[...\]
  cleanLine = cleanLine.replace(/\\\[[^\]]*\\\]/g, '');

  // 对于 ^，需要排除脚注语法 ^[ 和 [^
  // 对于 ~，需要排除删除线 ~~

  let count = 0;
  let i = 0;

  while (i < cleanLine.length) {
    if (cleanLine[i] === marker) {
      // 检查是否被转义
      if (i > 0 && cleanLine[i - 1] === '\\') {
        i++;
        continue;
      }

      // 对于 ^，跳过脚注相关语法
      if (marker === '^') {
        // ^[ 是内联脚注开始，跳过
        if (cleanLine[i + 1] === '[') {
          i += 2;
          continue;
        }
        // [^ 前面是 [，是脚注引用，跳过
        if (i > 0 && cleanLine[i - 1] === '[') {
          i++;
          continue;
        }
      }

      // 对于 ~，跳过删除线 ~~
      if (marker === '~') {
        if (cleanLine[i + 1] === '~') {
          // 跳过整个 ~~
          i += 2;
          continue;
        }
      }

      count++;
    }
    i++;
  }

  // 如果是奇数个，需要补全
  if (count % 2 === 1) {
    return marker;
  }
  return '';
}

/**
 * 获取安全的标记后缀，避免补全后产生 hr 模式
 * 在 Markdown 中，连续 3 个或更多的 *、- 或 _ 会被解析为水平分隔线 (hr)
 * 例如：末尾是 "**"，补全 "**" 后变成 "****"，会被解析为 hr
 *
 * @param line 当前行内容
 * @param markerSuffix 要补全的标记符号
 * @returns 安全的后缀（可能包含零宽空格来阻断 hr 模式）
 */
function getSafeMarkerSuffix(line: string, markerSuffix: string): string {
  if (!markerSuffix) return '';

  // hr 模式的字符：*、-、_
  const hrChars = ['*', '-', '_'];
  const suffixChar = markerSuffix[0] ?? '';

  // 只有当后缀是 hr 相关字符时才需要检查
  if (!suffixChar || !hrChars.includes(suffixChar)) {
    return markerSuffix;
  }

  // 计算行末尾连续的相同字符数量
  let trailingCount = 0;
  for (let i = line.length - 1; i >= 0; i--) {
    if (line[i] === suffixChar) {
      trailingCount++;
    } else {
      break;
    }
  }

  // 计算补全后连续字符的总数
  const totalCount = trailingCount + markerSuffix.length;

  // 如果总数 >= 3，会产生 hr 模式，需要插入零宽空格阻断
  if (totalCount >= 3) {
    // 使用零宽空格 (\u200B) 来阻断连续字符
    return '\u200B' + markerSuffix;
  }

  return markerSuffix;
}

/**
 * 检测内容是否处于不完整的 LaTeX 命令输入状态
 * 在这种状态下不应该补全闭合符号，否则会导致无效的 LaTeX
 */
function isIncompleteLatexInput(content: string, mathStartPos: number): boolean {
  // 获取数学块内的内容
  const mathContent = content.slice(mathStartPos).trimEnd();

  // 空内容算不完整，避免渲染空的数学块（如单独的 $ 被补全成 $$）
  if (!mathContent) return true;

  // 1. 检测末尾的单个反斜杠（正准备输入命令）
  // 这个检测放在最前面，因为它是最基本的不完整状态
  if (mathContent.endsWith('\\')) {
    return true;
  }

  // 2. 检测不完整的环境名：\begin{xxx 或 \end{xxx（没有闭合的 }）
  if (/\\(begin|end)\{[^}]*$/.test(mathContent)) {
    return true;
  }

  // 3. 检测末尾的不完整命令：\xxx
  const commandMatch = mathContent.match(/\\([a-zA-Z]+)$/);
  if (commandMatch?.[1]) {
    const cmd = commandMatch[1];

    // 如果是独立符号命令，不需要延迟
    if (STANDALONE_SYMBOLS.has(cmd)) {
      return false;
    }

    // 如果是需要参数的命令，且末尾没有 {，正在输入
    if (COMMANDS_REQUIRING_ARGS.has(cmd)) {
      return true;
    }

    // 检查是否是已知命令的前缀（正在输入中）
    const allKnownCommands = [...STANDALONE_SYMBOLS, ...COMMANDS_REQUIRING_ARGS];
    for (const known of allKnownCommands) {
      if (known.startsWith(cmd) && known !== cmd && known.length > cmd.length) {
        return true;
      }
    }

    // 检查是否是常见环境名的前缀
    for (const env of COMMON_ENVS) {
      if (env.startsWith(cmd) && env !== cmd) {
        return true;
      }
    }

    // 未知命令，可能是用户定义的，允许渲染
    return false;
  }

  // 4. 检测正在输入的 \begin 或 \end（后面没有 {）
  if (/\\(begin|end)$/.test(mathContent)) {
    return true;
  }

  return false;
}

function parseLatexCommand(content: string, startIdx: number): null | { cmd: string; endIdx: number } {
  // startIdx is at '\'
  let i = startIdx + 1;
  const len = content.length;
  if (i >= len) return null;

  // match [a-zA-Z]+
  const start = i;
  while (i < len) {
    const char = content[i];
    if (char && /[a-zA-Z]/.test(char)) {
      i++;
    } else {
      break;
    }
  }

  if (i === start) return null;

  return {
    cmd: content.substring(start, i),
    endIdx: i,
  };
}

function parseLatexEnvName(content: string, startIdx: number): null | { endIdx: number; name: string } {
  // expect {name}
  // skip spaces
  let i = startIdx;
  const len = content.length;

  while (i < len) {
    const char = content[i];
    if (char && /\s/.test(char)) {
      i++;
    } else {
      break;
    }
  }

  if (i >= len || content[i] !== '{') return null;
  i++;

  const nameStart = i;
  while (i < len && content[i] !== '}') {
    i++;
  }

  if (i >= len) return null; // unclosed brace

  return {
    name: content.substring(nameStart, i),
    endIdx: i + 1,
  };
}
