import { addClassToHast, getSingletonHighlighter, type Highlighter } from "shiki"

let highlighterPromise: Promise<Highlighter> | null = null

async function getHighlighter(): Promise<Highlighter> {
  if (!highlighterPromise) {
    highlighterPromise = getSingletonHighlighter({
      themes: ["github-light", "github-dark"],
      langs: ["vue", "typescript", "javascript", "html", "css", "json"],
    })
  }
  return highlighterPromise
}

type HastElement = Parameters<typeof addClassToHast>[0]

/**
 * 与 VitePress 内置 Markdown 高亮对齐（node 侧 `vitepress:add-class` / `vitepress:clean-up`）：
 * - `defaultColor: false` 时 token 使用 `--shiki-light` / `--shiki-dark`
 * - 默认主题在 `vp-code.css` 里把这些变量作用在 **`.vp-code span`** 上，故给 `<pre>` 加上 `vp-code`
 * - 去掉 `<pre>` 内联 `style`，避免与 VP 代码块布局冲突
 */
const vitePressCompatibleTransformers = [
  {
    name: "docs:vp-code-on-pre",
    pre(node: HastElement) {
      addClassToHast(node, "vp-code")
    },
  },
  {
    name: "docs:cleanup-pre-inline-style",
    pre(node: HastElement) {
      if ("style" in node.properties && node.properties.style !== undefined) {
        delete node.properties.style
      }
    },
  },
]

/**
 * 运行时高亮 Vue SFC：主题与 VitePress 默认 markdown 一致（github-light / github-dark）。
 */
export async function highlightVueSfc(code: string): Promise<string> {
  const highlighter = await getHighlighter()
  return highlighter.codeToHtml(code.trimEnd() ? code : " ", {
    lang: "vue",
    themes: {
      light: "github-light",
      dark: "github-dark",
    },
    defaultColor: false,
    transformers: vitePressCompatibleTransformers,
  })
}
