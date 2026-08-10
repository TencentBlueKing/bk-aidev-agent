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
 * 文件类型图标注册表。
 *
 * 只按需引入 `src/svgs` 中实际用到的图标（`?raw` 内联为字符串），
 * 避免全量 glob 把两百余个未使用的图标打进产物；同时无运行时请求、无额外资源产物。
 */
import cSvg from '../svgs/c.svg?raw';
import cmdSvg from '../svgs/cmd.svg?raw';
import consoleSvg from '../svgs/console.svg?raw';
import cppSvg from '../svgs/cpp.svg?raw';
import csharpSvg from '../svgs/csharp.svg?raw';
import cssSvg from '../svgs/css.svg?raw';
import dartSvg from '../svgs/dart.svg?raw';
import dockerSvg from '../svgs/docker.svg?raw';
import documentSvg from '../svgs/document.svg?raw';
import gitSvg from '../svgs/git.svg?raw';
import goSvg from '../svgs/go.svg?raw';
import htmlSvg from '../svgs/html.svg?raw';
import imageSvg from '../svgs/image.svg?raw';
import javaSvg from '../svgs/java.svg?raw';
import jsSvg from '../svgs/js.svg?raw';
import jsonSvg from '../svgs/json.svg?raw';
import kotlinSvg from '../svgs/kotlin.svg?raw';
import lessSvg from '../svgs/less.svg?raw';
import luaSvg from '../svgs/lua.svg?raw';
import markdownSvg from '../svgs/markdown.svg?raw';
import pdfSvg from '../svgs/pdf.svg?raw';
import phpSvg from '../svgs/php.svg?raw';
import powerpointSvg from '../svgs/powerpoint.svg?raw';
import pythonSvg from '../svgs/python.svg?raw';
import rSvg from '../svgs/r.svg?raw';
import reactSvg from '../svgs/react.svg?raw';
import rubySvg from '../svgs/ruby.svg?raw';
import rustSvg from '../svgs/rust.svg?raw';
import sassSvg from '../svgs/sass.svg?raw';
import scalaSvg from '../svgs/scala.svg?raw';
import sqlSvg from '../svgs/sql.svg?raw';
import svgSvg from '../svgs/svg.svg?raw';
import swiftSvg from '../svgs/swift.svg?raw';
import tableSvg from '../svgs/table.svg?raw';
import texSvg from '../svgs/tex.svg?raw';
import tuneSvg from '../svgs/tune.svg?raw';
import typescriptSvg from '../svgs/typescript.svg?raw';
import unknownSvg from '../svgs/unknown.svg?raw';
import vueSvg from '../svgs/vue.svg?raw';
import wordSvg from '../svgs/word.svg?raw';
import xmlSvg from '../svgs/xml.svg?raw';
import yamlSvg from '../svgs/yaml.svg?raw';
import { normalizeFileExtension } from '../utils/file-type';

/** 未识别类型的兜底图标 */
export const UNKNOWN_FILE_ICON_SVG = unknownSvg;

/** 图标 → 其覆盖的扩展名清单；按图标分组书写，避免同一份 svg 在映射表里重复出现 */
const FILE_ICON_GROUPS: [string, string[]][] = [
  [cSvg, ['c', 'h']],
  [cmdSvg, ['ps1']],
  [consoleSvg, ['bash', 'sh', 'zsh']],
  [cppSvg, ['cpp', 'hpp']],
  [csharpSvg, ['cs']],
  [cssSvg, ['css']],
  [dartSvg, ['dart']],
  [dockerSvg, ['dockerfile', 'dockerignore']],
  [documentSvg, ['rst', 'txt']],
  [gitSvg, ['gitignore']],
  [goSvg, ['go']],
  [htmlSvg, ['htm', 'html']],
  [imageSvg, ['jpeg', 'jpg', 'png']],
  [javaSvg, ['java']],
  [jsSvg, ['cjs', 'js', 'mjs']],
  [jsonSvg, ['json', 'jsonc']],
  [kotlinSvg, ['kt']],
  [lessSvg, ['less']],
  [luaSvg, ['lua']],
  [markdownSvg, ['markdown', 'md']],
  [pdfSvg, ['pdf']],
  [phpSvg, ['php']],
  [powerpointSvg, ['pptx']],
  [pythonSvg, ['py']],
  [rSvg, ['r']],
  [reactSvg, ['jsx', 'tsx']],
  [rubySvg, ['rb']],
  [rustSvg, ['rs']],
  [sassSvg, ['scss']],
  [scalaSvg, ['scala']],
  [sqlSvg, ['sql']],
  [svgSvg, ['svg']],
  [swiftSvg, ['swift']],
  [tableSvg, ['csv', 'tsv', 'xls', 'xlsm', 'xlsx']],
  [texSvg, ['tex']],
  // 配置类文件统一用「调节」图标：ini / toml / env / Makefile 等
  [tuneSvg, ['cfg', 'conf', 'editorconfig', 'env', 'ini', 'makefile', 'toml']],
  [typescriptSvg, ['ts']],
  [vueSvg, ['vue']],
  [wordSvg, ['docx']],
  [xmlSvg, ['xml']],
  [yamlSvg, ['yaml', 'yml']],
];

const FILE_ICON_MAP = new Map<string, string>(
  FILE_ICON_GROUPS.flatMap(([svg, extensions]) => extensions.map(extension => [extension, svg] as const)),
);

/** 按文件类型 / 文件名解析图标 svg 源码；未登记的类型返回兜底图标 */
export const getFileIconSvg = (type?: string, name?: string): string =>
  FILE_ICON_MAP.get(normalizeFileExtension(type, name)) ?? UNKNOWN_FILE_ICON_SVG;
