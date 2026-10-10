# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.redaction.utils

TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

检测器共享原语（自 ``detectors.py`` 抽取，原 ``redaction/{pem,entropy}.py`` 三层中的前两层）：

1. **PEM 解析 / 分类**：``normalize_label`` / ``classify_pem_label`` / ``PemBlock`` /
   ``iter_pem_blocks`` / ``is_substantive_pem_body`` / ``iter_unterminated_secret_pem_spans``。
2. **共享统计工具**：``shannon_entropy`` / ``char_class_count`` / ``classify_alphabet`` /
   形状判据（UUID / 定长 hex / 连续序列 / 重复串）/ ``is_pem_non_secret_span`` /
   ``is_public_key_span`` / ``is_non_secret_field_value`` / ``is_base64_container_span``。

``classify_pem_label`` 仍是 label 分类的**唯一**判据 —— ``PemDetector``（产 finding 侧，
在 ``detectors.py``）与 ``is_pem_non_secret_span``（熵侧排除，在本模块）都只经它决定
「要不要保留」。二者共用同一实现是**结构性**保证：在任一侧重写 PEM 谓词会重现
**缺陷 7/8 的 fail-open 明文泄露漂移**（两份分类实现分叉，CI 全绿也发现不了）。

**模块级私有名与类命名空间隔离**：本模块承载的模块级私有名全部来自原 ``pem`` / ``entropy``
的模块级定义；detector 类的私有常量仍留在 ``detectors.py`` 各自类体内
（``detectors.py`` 内同名但字面量不同的 ``_VAR_REF_RE`` 等**不得**摊平到模块级）。
类命名空间隔离是「合并前各文件已完成封装」（T-vq0）建立的不变量。

**预筛选所有权（T-vq0，缺陷 3 根因防线）**：``could_match`` 仍是 ``Detector`` 协议的一部分，
但调用方不再负责调用它 —— 每个 ``scan`` 实现必须在自身开头调用一次自家的 ``could_match``。

**依赖方向**：``packages.security`` 约定 —— 仅标准库 / pydantic / langchain_core /
``pydantic_models`` / 本包内模块；**禁止** ``core`` / ``services`` / ``api``。

**ReDoS 防护（T-06-12）**：PEM 跨行匹配用 ``re.DOTALL``，但 body 用**有界**量词
（``{0,65536}``）；超过上限则不产出块（宁可漏也不让热路径失控）。
"""

from __future__ import annotations

import math
import re
from bisect import bisect_right
from collections import Counter
from typing import NamedTuple

# ===== PEM 解析 / 分类（原 redaction/pem.py，260915-0dr 并入本文件）=====
#
# 本段是「什么是完整且 label 匹配的 PEM 块」与「某个 label 属于哪一类」的**唯一**真源，
# 被 detector 侧（``PemDetector``）与熵侧（``is_pem_non_secret_span``）共同依赖。
#
# **ReDoS 防护（T-06-12）**：跨行匹配用 ``re.DOTALL``，但 body 用**有界**量词（``{0,65536}``）；超过上限则不产出块（宁可漏也不让热路径失控）。

# LABEL 白名单（private key 类）—— 成员必须是**归一化后**的 label（见 normalize_label）
_PRIVATE_LABELS: tuple[str, ...] = (
    "RSA PRIVATE KEY",
    "EC PRIVATE KEY",
    "OPENSSH PRIVATE KEY",
    "ENCRYPTED PRIVATE KEY",
    "PGP PRIVATE KEY BLOCK",
    "PRIVATE KEY",
    # RFC 4716 §3 规定的 SSH2 私钥封装 —— 4 短横形态的标准 label（此前落 unknown → 不遮）
    "SSH2 ENCRYPTED PRIVATE KEY",
)

# 非 private 的 label（显式排除，用于可读性与文档化）—— 同为归一化后形式。
# 仅这些**精确** label 才被视为非秘密；白名单匹配取代此前的正则字符串前缀匹配。
_NON_PRIVATE_LABELS: tuple[str, ...] = (
    "PUBLIC KEY",
    "RSA PUBLIC KEY",
    "EC PUBLIC KEY",
    "DSA PUBLIC KEY",
    "OPENSSH PUBLIC KEY",
    "CERTIFICATE",
    "X509 CERTIFICATE",
    "TRUSTED CERTIFICATE",
    "PGP PUBLIC KEY BLOCK",
    "SSH2 PUBLIC KEY",
    # CSR（PKCS#10）—— 含公钥与主体名，不含私钥material（RFC 2986）。
    # README 策略：「公钥、证书、CSR 不因 PEM 包装成为秘密，本测试保留它们」。
    # 此前缺失这两个 label ⇒ classify 落 `unknown` ⇒ fail-closed 当秘密
    # ⇒ ``EntropyDetector`` 逐行把 CSR body 当 base64 秘密脱敏（S037）。
    "CERTIFICATE REQUEST",
    "NEW CERTIFICATE REQUEST",
)

# body 有界量词上限（T-06-12：超限不命中，避免无界扫描）
_BODY_MAX = 65536

# BEGIN ... END 两段独立匹配（label 一致性由代码比对，不用 backreference）
_BEGIN_RE = re.compile(r"-----BEGIN ([A-Z0-9 ]+?)-----")
_END_RE = re.compile(r"-----END ([A-Z0-9 ]+?)-----")

# 4 短横 RFC 4716 形态（``---- BEGIN X ----``）；仅用于「非秘密块排除」识别，
# 与 5 短横 private key 匹配相互独立（见 iter_pem_blocks 的 dash 参数）。
_RFC4716_BEGIN_RE = re.compile(r"---- BEGIN ([A-Z0-9 ]+?) ----")
_RFC4716_END_RE = re.compile(r"---- END ([A-Z0-9 ]+?) ----")

# 归一化后的 label 集合（frozenset 便于 O(1) 判定）
_NON_SECRET_LABEL_SET = frozenset(_NON_PRIVATE_LABELS)
_PRIVATE_LABEL_SET = frozenset(_PRIVATE_LABELS)

# label 内部分隔符：PEM label 是 RFC 定义的固定词表，空白（空格 / 制表符等）
# 只有分隔语义、无区分语义，故一律折叠为单个空格并 strip。
_LABEL_WS_RE = re.compile(r"\s+")


def normalize_label(raw: str) -> str:
    """把 BEGIN/END 捕获到的原始 label 归一化为**规范形式**。

    这是「两个 label 是否相同」「label 是否属于某集合」的**唯一**规范来源
    （缺陷 8 / fix 轮 4）：``iter_pem_blocks`` 在解析时即归一化，
    故下游（``PemDetector`` 与 ``is_pem_non_secret_span``）看到的是同一个字符串，
    不可能再各自对原始空白做不同解释。

    规则：折叠所有内部空白（正则 ``\\s+``，含空格 / 制表符）为单个空格，并 strip 首尾。
    PEM label 是 RFC 定义的固定词表（``PUBLIC KEY`` / ``RSA PRIVATE KEY`` …），
    空白差异不是语义差异 ——
    ``-----BEGIN  PUBLIC KEY-----``（双空格）与 ``-----BEGIN PUBLIC KEY-----`` 指同一 label。

    **安全影响（fail-closed）**：仅当原始 label 折叠后**精确等于**
    验证白名单中的某个非秘密 label 时才会被排除。
    归一化使得「空白变体」与规范形等价，从而与 detector 判定一致
    （此前 ``' PUBLIC KEY'`` 被正则前缀匹配误判为非秘密、
    却不被 ``PemDetector`` 识别，**两边都不遮**而泄露）。
    近义但不精确的 label（``PUBLIC KEYX`` / ``X509`` 等）归一化后仍不在白名单
    → 不排除 → 遮（fail-closed）。

    Args:
        raw: ``iter_pem_blocks`` 正则捕获的原始 label（可能含前导 / 内部 / 尾随空白）。

    Returns:
        归一化 label（空白折叠为单空格 + strip）。
    """
    return _LABEL_WS_RE.sub(" ", raw).strip()


def classify_pem_label(label: str) -> str:
    """把（**已归一化**的）PEM label 分类为 ``"non_secret"`` / ``"secret"`` / ``"unknown"``。

    这是 label 分类的**唯一**判据（缺陷 8）：
    ``PemDetector`` 与 ``is_pem_non_secret_span`` 都只通过本函数决定「要不要保留」，
    二者因此不可能再对同一 label 给出不同结论。
    此前两端各用一套平行检查（私有集合成员 vs 正则前缀匹配），正是漂移来源。
    合并（``260915-0dr``）后二者同处本文件，共用同一实现是**结构性**保证。

    调用方**必须**传入 ``normalize_label()`` 的结果；
    本函数不重复归一化（避免「谁负责归一化」的二义性）。

    Args:
        label: 已归一化的 label。

    Returns:
        ``"non_secret"``（公钥 / 证书，可字节级保留）/ ``"secret"``（私钥类，必须遮）/
        ``"unknown"``（无法确证 —— 调用方按 fail-closed 处理）。
    """
    if label in _NON_SECRET_LABEL_SET:
        return "non_secret"
    if label in _PRIVATE_LABEL_SET:
        return "secret"
    return "unknown"


class PemBlock(NamedTuple):
    """一个**完整且 BEGIN/END label 一致**的 PEM 块在原文中的位置。

    Args:
        start: 块起点偏移（BEGIN 标记首字符，闭）。
        end: 块终点偏移（END 标记末字符之后，开）。
        label: 块 label（BEGIN 与 END 已确认一致）。
        body_start: body 起点偏移（BEGIN 标记末字符之后）——
            body 必须从此处**另起一行**才有意义；
            暴露给调用方用于「命中是否在 body 行内」的判定。
    """

    start: int
    end: int
    label: str
    body_start: int


def iter_pem_blocks(text: str, *, dash: int = 5) -> list[PemBlock]:
    """枚举文本中**完整且 BEGIN/END label 一致**的 PEM 块。

    这是「什么算一个完整 PEM 块」的**唯一**定义（缺陷 7 回归）：
    ``PemDetector`` 与熵侧的非秘密块排除都消费它，两端语义不可能再漂移。

    **fail-closed 语义**：只有 **BEGIN 之后存在一个 label 完全相同的 END**
    的块才会产出。END 缺失 / label 不一致 /
    本块被上一个未闭合块「吞掉」的块一律**不产出** ——
    调用方因此不会把未闭合或错配的块误判为「已识别 → 可排除」，
    未识别的 PEM-ish body 会继续走裸熵兜底被遮（宁遮不漏）。

    参数 ``dash`` 选择拼写：
      * ``5``：标准 ``-----BEGIN X-----`` / ``-----END X-----``（本 detector 使用）；
      * ``4``：RFC 4716 ``---- BEGIN X ----`` / ``---- END X ----``（非秘密排除使用）。

    匹配算法与旧 ``PemDetector.scan`` 逐字一致（分组捕获 + 代码比对 label，
    非 backreference；body 起点到 END 起点不超过 ``_BODY_MAX``，超限不产出），
    故对既有 5 短横行为是**零语义变更**的抽取。

    Args:
        text: 原始文本。
        dash: ``5`` 或 ``4``，选择短横拼写。

    Returns:
        ``PemBlock`` 列表（按 BEGIN 出现顺序）。
    """
    if not isinstance(text, str) or not text:
        return []
    if dash == 4:
        begin_re, end_re = _RFC4716_BEGIN_RE, _RFC4716_END_RE
    else:
        begin_re, end_re = _BEGIN_RE, _END_RE

    blocks: list[PemBlock] = []
    for begin in begin_re.finditer(text):
        # 归一化 **在解析时** 完成（缺陷 8 根因修复）：PemBlock.label 保证是规范形式，
        # 故 BEGIN/END 一致性比对与下游分类都建立在同一字符串上。
        # ``-----BEGIN  PUBLIC KEY-----``（双空格）→ ``'PUBLIC KEY'``。
        label = normalize_label(begin.group(1))
        end = end_re.search(text, begin.end())
        if end is None:
            continue
        # BEGIN/END label 必须一致（代码比对，非 backreference）—— 比对**归一化后**的 label：
        # ``BEGIN  PUBLIC KEY`` + ``END PUBLIC KEY``（空白不对称）视为同一 label，与 PEM 语义一致（空白不承载信息），
        # 并避免「空白变体」落到 unknown 而含糊。
        if normalize_label(end.group(1)) != label:
            continue
        # 跨块错配（本次修正）：``end_re.search`` 找的是「本 BEGIN 之后的**任意** END」，
        # 并不知道那个 END 属于谁。若本 BEGIN 与候选 END 之间还存在**同 label** 的 BEGIN，
        # 说明本 BEGIN **自己未闭合** —— 该 END 属于更靠后的那个 BEGIN，不得借用。
        # 否则 ``BEGIN K1  <正常内容>  BEGIN K2  END K2`` 会被并成一个跨块 span
        # （``K1..END K2``），把中间的正常内容一并吞掉。
        # 仅比对**同 label**：异 label 的介入者不构成「本 BEGIN 未闭合」的证据
        # （PEM body 内嵌异名 header 的既有行为因此保持不变）。
        between = begin_re.search(text, begin.end(), end.start())
        if between is not None and normalize_label(between.group(1)) == label:
            continue
        # body 有界（T-06-12）：超限不产出
        if end.start() - begin.end() > _BODY_MAX:
            continue
        blocks.append(PemBlock(begin.start(), end.end(), label, begin.end()))
    return blocks


# PEM body 中的「非实质内容」字符：base64 折行产生的空白 + 教学省略号。
# 一个块若 BEGIN/END 之间**只**含这些字符，说明它是「空壳 / 教学省略占位」，
# 而非真实密钥 —— README 策略：
#   「单独的BEGIN标记和明确的教学省略占位符保持原样，**有实质内容的**截断私钥则遮罩」。
_PEM_NON_SUBSTANTIVE_RE = re.compile(r"^[\s.\u2026]*$")


def is_substantive_pem_body(text: str, block: PemBlock) -> bool:
    """判断 PEM 块的 body 是否含**实质内容**（真实 base64 材料）。

    判据：BEGIN 与 END 之间除空白 / 教学省略号（``...`` / ``…``）外，
    至少存在一个其他字符。用于区分：

    - **空壳 / 教学省略**：``-----BEGIN PRIVATE KEY-----``（无配对 END，或
      ``-----BEGIN X----- ... -----END X-----``）⇒ 不含实质内容 ⇒ 不该脱敏（S115/S116）；
    - **真实（含截断）私钥**：body 含 base64 字符 ⇒ 含实质内容 ⇒ 照常脱敏。

    Args:
        text: 原始文本（用于按偏移切片）。
        block: :func:`iter_pem_blocks` 产出的块。

    Returns:
        True 表示 body 含实质内容。
    """
    body = text[block.body_start : block.end]
    # 剥离 END 标记行：END 标记以 ``-----END``（5 短横）或 ``---- END``（RFC 4716 4 短横）开头。
    # 取**最靠后**的那个候选，而不是先探 5 短横再回退 —— 本块的 END 必定位于 ``block.end`` 之前
    # 紧邻处，故「最靠后」即本块的定界符。
    # 有序回退（先 ``rfind("-----END")``）会在 body 内嵌 5 短横字样时误取该字样：
    # 4 短横块的 body 里出现 ``-----END FOO-----``（例如被截断的样例 / 嵌套内容）时，
    # 剥离点被提前到字样处，剩下的前缀若只有空白/省略号就会被误判为「非实质」
    # ⇒ detector 与 ``is_pem_non_secret_span`` 双双放行 ⇒ 私钥正文明文泄露（fail-open）。
    candidates = [idx for idx in (body.rfind("-----END"), body.rfind("---- END")) if idx != -1]
    if candidates:
        body = body[: max(candidates)]
    return not bool(_PEM_NON_SUBSTANTIVE_RE.match(body))


# 未闭合私钥块的空 body 判据 —— 与 ``is_substantive_pem_body`` 使用**同一字符集**
# （空白 / 教学省略号），保证「空壳 / 教学省略」在两条路径下判定一致。
_UNTERMINATED_SHELL_RE = _PEM_NON_SUBSTANTIVE_RE


def iter_unterminated_secret_pem_spans(text: str) -> list[tuple[int, int]]:
    """枚举**未闭合 secret PEM 块**的遮罩区间（BEGIN 起 → 下一个 BEGIN 或文末）。

    背景（本次修复）：``iter_pem_blocks`` 只产出「BEGIN + **配对** END」的完整块
    （缺陷 7 的 fail-closed 设计）。未闭合私钥因此**零 finding**，而裸熵兜底又会把
    纯 base64 body（``char_class_count < 3``，见 ``EntropyDetector._classify_if_secret``
    第 4 步）拦在熵阈值之前 —— 两者叠加 ⇒ **私钥正文明文泄露**。
    真实随机 RSA 私钥截断到中点即复现（1188/1200 个截断点泄露）。

    本函数补齐该缺口，判据（顺序即短路顺序）：

    1. label 分类为 ``"secret"`` —— 经 ``normalize_label`` + ``classify_pem_label``，
       与 ``PemDetector`` / ``is_pem_non_secret_span`` **共用同一分类判据**（缺陷 8：
       不得另写一套，否则两端漂移即 fail-open 泄露）。非秘密（公钥 / 证书 / CSR）与
       ``unknown`` 一律不在此遮罩 —— 前者本就该保留，后者仍由裸熵兜底。
    2. 该 BEGIN **已被 ``iter_pem_blocks`` 识别为完整块**则跳过 —— 交由原路径整块替换，
       避免与完整块 span 重叠。
    3. **不存在与本 BEGIN 配对的 END**（未闭合）。配对判据与 ``iter_pem_blocks`` 一致：
       向后找同 label 的 END，且二者之间无同 label 的 BEGIN 介入。有 END 但 label
       错配者同理视为未闭合（其 body 同样是私钥 material）。
    4. BEGIN 到区间末尾含**实质 body** —— 空壳（只有 BEGIN）与教学省略占位
       （``...`` / ``…``）保持原样，与 ``is_substantive_pem_body`` 同一字符集。

    区间右界 = **下一个同拼写 BEGIN 的起点**（``bisect_right``，O(log n)），否则文末；
    并受 ``_BODY_MAX`` 约束（T-06-12 精神，不放大无界扫描）。
    5 短横与 4 短横（RFC 4716）两套拼写**各自独立**枚举，与 ``iter_pem_blocks`` 的
    消费方式一致（``PemDetector.scan`` 亦为两套相加）。

    Args:
        text: 原始文本。

    Returns:
        ``(start, end)`` 列表，按 start 升序、两两不重叠。

    **已知取舍（用户 2026-09-17 确认）**：右界止于下一个 BEGIN 或文末 —— 未闭合私钥
    之后紧跟的同段普通文本会被一并遮掉。未闭合时**无法判定密钥的真实边界**
    （body 可能是任意长度的 base64），故取「宁遮不漏」：私钥是不可逆泄露，
    过度遮蔽是可接受的代价。对照：**已闭合**的块仍严格按 BEGIN/END 精确切分，
    故「完整块 + 中间正常内容 + 完整块」的形态不受影响。
    """
    if not isinstance(text, str) or not text:
        return []

    spans: list[tuple[int, int]] = []
    for begin_re, end_re, dash in (
        (_BEGIN_RE, _END_RE, 5),
        (_RFC4716_BEGIN_RE, _RFC4716_END_RE, 4),
    ):
        begins = list(begin_re.finditer(text))
        if not begins:
            continue
        # 已被识别为完整块的起点集合（复用共享解析源，不重跑正则、不另写解析）
        complete_starts = {b.start for b in iter_pem_blocks(text, dash=dash)}
        starts = [m.start() for m in begins]

        for match in begins:
            if match.start() in complete_starts:
                continue
            label = normalize_label(match.group(1))
            if classify_pem_label(label) != "secret":
                continue
            # 是否存在与本 BEGIN **配对**的 END？配对 = 同 label，且二者之间无同 label BEGIN。
            paired_end = None
            probe = end_re.search(text, match.end())
            while probe is not None:
                if normalize_label(probe.group(1)) == label:
                    intervenes = begin_re.search(text, match.end(), probe.start())
                    if intervenes is None or normalize_label(intervenes.group(1)) != label:
                        paired_end = probe
                        break
                probe = end_re.search(text, probe.end())
            if paired_end is not None:
                continue  # 已闭合 —— 属 ``iter_pem_blocks`` 的辖区（含 label 错配形态）

            # 右界：下一个同拼写 BEGIN 的起点，否则文末；再受 _BODY_MAX 约束。
            index = bisect_right(starts, match.start())
            boundary = starts[index] if index < len(starts) else len(text)
            span_end = min(boundary, match.end() + _BODY_MAX)
            # 空壳 / 教学省略豁免：无实质 body 则保持原样（与 is_substantive_pem_body 同字符集）。
            if _UNTERMINATED_SHELL_RE.match(text[match.end() : span_end]):
                continue
            spans.append((match.start(), span_end))

    spans.sort()
    return spans


# ===== 共享统计工具（原 redaction/entropy.py，260915-0dr 并入本文件）=====
#
# 共享统计工具（Shannon 熵 / 字符类别 / 字符集分类 / 形状判据 / base64 容器排除）。
#
# PR3 把原先内联在 ``detectors/assignment.py`` 的 ``_shannon_entropy`` / ``_char_class_count`` /``_is_uuid_like`` / ``_is_fixed_hex`` **收口**到这里（公共名，去下划线），
# ``assignment.py`` 改为 import —— 消除跨模块重复实现，
# 也让裸熵 detector 与歧义字段评分共用同一份判据（DESIGN §3.5 / §3.6）。
#
# **判据是形状，不是熵**（DESIGN §3.5 明确）：长度 8 的 hex 空间小、长度 64 的 SHA-256 熵可达 4.0+，
# 故排除项一律走形状（纯 hex + 特定长度 / UUID / 连续序列 /重复串），熵只用于「是否达到阈值」的加分与触发判定。
#
# 纯统计工具段：无 I/O、无 registry 依赖、不读环境变量。

# 字符集分类标签（classify_alphabet 返回值）
_ALPHABET_ALNUM = "alnum"
_ALPHABET_BASE64 = "base64"
_ALPHABET_BASE64URL = "base64url"
_ALPHABET_OTHER = "other"

# 纯 hex 排除长度形状（GPG key ID / fingerprint / 常见 digest）—— 形状判据，不依赖熵。
#
# **64 已移出**（S057/S058/S076/S081 召回修复）：长度 64 是 SHA-256 / HMAC / AES-256
# 密钥的**标准宽度**，且其熵可达 3.6~4.0 —— 与「业务 digest」无法用形状区分，
# 一律豁免会把「hex 编码的真实密钥」整体漏掉。故 64 位交给熵/上下文判据决定：
# - 裸熵路径（``EntropyDetector``）熵 >= 4.2 才命中 ⇒ 本测试值的 3.675 仍不命中，
#   故「裸 64-hex digest 不脱敏」的既有行为**未变**（见 test_entropy 的 64-hex 负例）；
# - 赋值路径由字段名上下文决定（``secret`` 后缀 +2 等）。
# 8 / 16 / 32 / 40 保留豁免：固定宽度小 ID（GPG key ID、fingerprint、git short SHA）
# 在源码与日志里极常见，且熵本就低于阈值，豁免是净收益。
_HEX_EXCLUDE_LENGTHS = frozenset({8, 16, 32, 40})
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")

# UUID 标准形（带连字符 36 位）
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
# ULID（26 位 Crockford base32）/ KSUID（27 位 base62）
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
_KSUID_RE = re.compile(r"^[0-9A-Za-z]{27}$")

# 字符集成员判定
_ALNUM_RE = re.compile(r"^[A-Za-z0-9]+$")
# 标准 Base64：含 + / 或 padding =，其余为 base64 字符
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
_BASE64_CHARS_RE = re.compile(r"^[A-Za-z0-9+/]+$")
# Base64URL：含 - 或 _，其余为 base64url 字符
_BASE64URL_CHARS_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# base64 容器前缀（D-08 硬排除）：命中区间落在这些前缀之后则跳过
_BASE64_CONTAINERS: tuple[str, ...] = ("data:", ";base64,")
# 容器前缀与命中区间之间若出现「空白 / 引号」，
# 说明命中是独立 token 而非载荷（data URI 的 MIME 段 `text/plain;base64,` 里的 `;` `/` `,` 是 URI 语法，不算分隔）
_CONTAINER_GAP_RE = re.compile(r"[\s\"'`]")

# ---------------------------------------------------------------------------
# PEM 非秘密块硬排除（缺陷 4 / 缺陷 6 / 缺陷 7）
#
# PemDetector 已正确排除公钥 / 证书（LABEL 白名单），
# 但它**不产出 finding**，故裸熵兜底仍会把 ``-----BEGIN PUBLIC KEY-----`` 的 base64 body 当裸密文遮掉，
# 使「公钥不被触碰」的显式负例失效（误伤：破坏正常配置 / 信任链）。
#
# 此处以 **span 位置谓词**实现排除（与上面的 D-08 data: 容器排除同构，不做正则改写），
# 但谓词的**判定依据是「解析出的完整块」而非「孤立的 BEGIN 标记」**。
#
# 缺陷 7（fail-open 泄露回归）：早先的实现在命中之前找**最近的非秘密 BEGIN**，只看 BEGIN label、只要求「BEGIN 与命中之间无 END」，
# 于是「BEGIN PUBLIC KEY + END RSA PRIVATE KEY（错配）」「BEGIN PUBLIC KEY + 无 END（未闭合）」
# 这两类畸形块被熵侧判为「可排除」，同时 PemDetector 因 BEGIN != END 而拒绝动作 ——**两边都不遮**，body 原样泄露。
# 这是比误伤严重得多的 fail-open。
#
# 现在改为：委托 ``iter_pem_blocks``（与 PemDetector 共享的唯一解析源，定义在本文件上方）
# 枚举**完整且 BEGIN/END label 一致**的块，命中区间只有**落在某个已完整识别的非秘密块内**才排除。
# 无法正识别为「完整的非秘密块」→ **不排除** → 裸熵兜底遮掉（fail-closed）。
#
# 缺陷 8（fix 轮 4）：此前**分类本身**仍是两套平行检查 —— 本段用正则``[A-Z0-9 ]*PUBLIC KEY`` 做前缀匹配，
# PemDetector 用精确集合成员判定。二者对畸形 label 结论不一致：``iter_pem_blocks`` 曾保留 label 的原始空白，
# 于是``-----BEGIN  PUBLIC KEY-----``（双空格）产出 label ``' PUBLIC KEY'`` —— 被前者前缀匹配判为非秘密（排除），
# 却不在后者集合内（不产 finding）→ **两边都不遮**， body 原样泄露（fail-open）。现在：
# ``iter_pem_blocks`` **解析时即归一化** label（折叠内部空白 + strip），
# 本段与 PemDetector 都委托 ``classify_pem_label``（**唯一**分类判据）判定。
# ``non_secret`` 白名单为**精确** label 集合：
# ``PUBLIC KEY`` / ``RSA|EC|DSA|OPENSSH PUBLIC KEY`` / ``CERTIFICATE`` / ``X509 CERTIFICATE`` / ``TRUSTED CERTIFICATE`` /``PGP PUBLIC KEY BLOCK`` / RFC 4716 ``SSH2 PUBLIC KEY``；private key 块**不在**排除集内 —— PemDetector（priority 95）
# 负责整块替换；``unknown`` 一律不排除（fail-closed）。
# 4 短横 RFC 4716 形态（``---- BEGIN SSH2 PUBLIC KEY ----``）同样经共享解析器识别。
# ---------------------------------------------------------------------------

# 非秘密 label 分类**不再**用正则前缀匹配 —— 那是缺陷 8 的第二个漂移点：
# ``[A-Z0-9 ]*PUBLIC KEY`` 会匹配 ``' PUBLIC KEY'``（前导空白），而 PemDetector 按精确集合判定，
# 于是畸形 label 被熵侧放过、又被 detector 拒绝 → 两边都不遮而泄露。
# 现统一委托 ``classify_pem_label``（label 已在 iter_pem_blocks 内归一化），两端共用**同一**判据，不可能再漂移。

# BEGIN 与命中之间允许的内容：换行起头（PEM body 必须起于新行），其后可为空行 /前导空白 / body 字符。禁止在同一行内（未换行）
# 直接出现命中 —— 保证``CERTIFICATE AUTHORITY=...`` 这类「label 后接空格 + 普通赋值」的普通文本不放过。
_PEM_BODY_GAP_RE = re.compile(r"^\r?\n[\s\S]*$")

# 连续序列判据：单一相邻字符差值占比阈值
_SEQUENCE_STEP_RATIO = 0.9
# 重复串判据：去重后字符数不超过此值即视为重复
_REPETITION_UNIQUE_MAX = 2


def shannon_entropy(value: str) -> float:
    """计算 Shannon 熵（bit/字符，底为 2）。

    空串与单字符返回 ``0.0``（无不确定性）。

    Args:
        value: 待计算字符串。

    Returns:
        Shannon 熵值（bit/字符）。
    """
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def char_class_count(value: str) -> int:
    """统计字符类别数（upper / lower / digit / symbol 四类命中几类）。

    Args:
        value: 待统计字符串。

    Returns:
        命中类别数（0-4）。
    """
    classes = 0
    if any(c.isupper() for c in value):
        classes += 1
    if any(c.islower() for c in value):
        classes += 1
    if any(c.isdigit() for c in value):
        classes += 1
    if any(not c.isalnum() for c in value):
        classes += 1
    return classes


def classify_alphabet(value: str) -> str:
    """判断候选值的字符集归属。

    ``EntropyDetector`` 现自持本判据（T-vq0）；本定义保留以兼容 ``__all__``
    与既有导入面，二者由
    ``test_detectors.py::TestDetectorConstantEncapsulation::test_entropy_self_hosts_moved_helpers``
    与源实现钉住同结果。

    Args:
        value: 待分类字符串。

    Returns:
        ``"alnum"``（仅 ``[A-Za-z0-9]``）/ ``"base64"``（含 ``+`` ``/`` 或 padding ``=``）/
        ``"base64url"``（含 ``-`` 或 ``_``）/ ``"other"``（不符合上述任一）。
    """
    if not value:
        return _ALPHABET_OTHER
    if _ALNUM_RE.match(value):
        return _ALPHABET_ALNUM
    if _BASE64_RE.match(value) and ("+" in value or "/" in value or "=" in value):
        return _ALPHABET_BASE64
    if _BASE64URL_CHARS_RE.match(value) and ("-" in value or "_" in value):
        return _ALPHABET_BASE64URL
    return _ALPHABET_OTHER


def is_uuid_like(value: str) -> bool:
    """判断是否为 UUID / ULID / KSUID 形状。

    与 :func:`is_fixed_hex` 在「无连字符 32 位 hex」上有重叠 —— 两者可同时为 True，
    调用方按「任一为真即排除」处理，重叠无害。

    Args:
        value: 待判断字符串。

    Returns:
        True 表示形如标准 UUID（36 位带连字符）/ 无连字符 32 位 hex / ULID（26）/
        KSUID（27）；ULID / KSUID 要求至少含一个数字，避免误伤纯字母单词。
    """
    if _UUID_RE.match(value):
        return True
    if len(value) == 32 and _HEX_RE.match(value):
        return True
    if len(value) == 26 and _ULID_RE.match(value) and any(c.isdigit() for c in value):
        return True
    return len(value) == 27 and bool(_KSUID_RE.match(value)) and any(c.isdigit() for c in value)


def is_fixed_hex(value: str) -> bool:
    """判断是否为「纯 hex + 长度 ∈ {8,16,32,40}」形状（GPG key ID / fingerprint）。

    这是**形状判据**而非熵判据 —— 实测真实 fingerprint 熵约 3.4-3.8 本就低于阈值，
    长度 8 的 hex 空间小，故形状判据更稳。

    **64 不在集内**：64 位是 SHA-256 / AES-256 密钥的标准宽度，与业务 digest
    无法用形状区分，一律豁免会漏掉 hex 编码的真实密钥（S057 族）。
    故 64 位的「是否脱敏」由熵阈值与字段名上下文决定，而非形状。

    Args:
        value: 待判断字符串。

    Returns:
        True 表示纯 hex 且长度命中排除集。
    """
    return bool(_HEX_RE.match(value)) and len(value) in _HEX_EXCLUDE_LENGTHS


# 占位符形态：值的**本身**就是一个「此处应有值但未填」的标记，
# 而非指向别处的引用（后者由各 detector 的 ``_VAR_REF_RE`` 负责）。
#
# 与 `_VAR_REF_RE` 的分工（T-06-17 只覆盖了前者，本判据补齐后者）：
#   - 引用型：`${VAR}` / `$VAR` / `{var}` / `os.getenv(...)` —— 取值来自运行环境；
#   - 占位符型：`null` / `********` / `<REDACTED>` / `{{ jinja }}` / `!vault` /
#     `...` / `changeme` —— 取值**根本不存在或已被人工遮蔽**。
# 两者都不该被当作真实 secret 替换：前者替换会破坏配置模板，后者替换会污染
# 已经脱敏过的文本（二次脱敏应幂等 —— README「二次脱敏结果应不变」）。
_PLACEHOLDER_RE = re.compile(
    r"""(?ix)^(
       null|none|nil|undefined|empty            # 空值关键字
      |\*{3,}|\.{3,}|-{3,}|_{3,}                # 星号 / 省略 / 分隔线掩码
      |[<\[\(]\s?(redacted|hidden|removed|masked|omitted|secret)[^>\])]*\s?[>\]\)]  # 已脱敏标记
      |\{\{.*?\}\}                              # Jinja / Ansible Vault 模板
      |![a-z_]+                                 # YAML tag（`!vault` / `!secret`）
      |change\s?me|todo|placeholder|example|your[_-]?\w*
    )$""",
)


def is_placeholder_value(value: str) -> bool:
    """判断值本身是否为「占位符 / 已脱敏标记」而非真实凭据。

    Args:
        value: 待判断的值本体（不含 key 与分隔符）。

    Returns:
        True 表示该值是占位符，调用方应跳过脱敏。

    Note:
        与 :func:`is_fixed_hex` / :func:`is_uuid_like` 同为**形状判据**，不依赖熵。
        判据刻意保持精确字符串全等，不做「包含」匹配 ——
        否则 `my-password-example` 这类真实值会被误豁免。
    """
    if not value:
        return False
    return bool(_PLACEHOLDER_RE.match(value))


def is_monotonic_sequence(value: str) -> bool:
    """判断是否为连续递增 / 递减序列（``abcdefg…`` / ``123456…`` / 反向）。

    ``EntropyDetector`` 现自持本判据（T-vq0）；本定义保留以兼容 ``__all__``
    与既有导入面，二者由
    ``test_detectors.py::TestDetectorConstantEncapsulation::test_entropy_self_hosts_moved_helpers``
    与源实现钉住同结果。

    判据：对相邻字符差值取 ``Counter``，若单一差值占绝对多数（``>= len-2`` 次）
    即判为序列。长度 < 4 无意义，直接返回 False。

    Args:
        value: 待判断字符串。

    Returns:
        True 表示形如连续序列。
    """
    if len(value) < 4:
        return False
    steps = Counter(ord(b) - ord(a) for a, b in zip(value, value[1:]))
    return steps.most_common(1)[0][1] >= len(value) - 2


def is_repetition(value: str) -> bool:
    """判断是否为重复串（同一字符反复，或去重后字符极少）。

    ``EntropyDetector`` 现自持本判据（T-vq0）；本定义保留以兼容 ``__all__``
    与既有导入面，二者由
    ``test_detectors.py::TestDetectorConstantEncapsulation::test_entropy_self_hosts_moved_helpers``
    与源实现钉住同结果。

    Args:
        value: 待判断字符串。

    Returns:
        True 表示去重后字符数 <= 2（如 ``aaaa…`` / ``ababab…``）。
    """
    if len(value) < 4:
        return False
    return len(set(value)) <= _REPETITION_UNIQUE_MAX


# OpenSSH 公钥算法前缀（单行 ``<算法> <base64> [comment]`` 形态，无 PEM 包装）。
# 公钥不是秘密；裸熵兜底须据此前缀排除其 body（S035）。
# 只列**公钥**算法 —— ``OPENSSH PRIVATE KEY`` 是 PEM 包装的私钥，由 PemDetector 处理，
# 不在此列（否则会把私钥 body 误放过）。
_PUBLIC_KEY_PREFIXES: tuple[str, ...] = (
    "ssh-ed25519",
    "ssh-rsa",
    "ssh-dss",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "sk-ssh-ed25519@openssh.com",
    "sk-ecdsa-sha2-nistp256@openssh.com",
)

# 公钥前缀与其 body 命中之间的允许内容：空白 + base64 字符（**含**被熵候选字母表
# 排除的 ``/`` 与 ``=`` 填充）。用于 :func:`is_public_key_span` 的回退扫描 ——
# body 因 ``/`` 被切碎时，命中起点落在中段，中间必然含有 base64 字符。
_PUBLIC_KEY_GAP_RE = re.compile(r"^(?=[\sA-Za-z0-9+/=]*$)[\sA-Za-z0-9+/=]*")

# 保留字段名（**公开**密码学参数，不是凭据）：`nonce=` / `salt=` / `iv=` 等。
# 含义与 assignment 的 `_EXCLUDED_FIELD_NAMES` 一致，但作用于**裸熵**路径 ——
# 该路径不看字段名，故须回看命中前的上下文自行判断。
# 归一化比较（去分隔符 + 小写），与 assignment 同一套归一化逻辑。
#
# 为什么必须做在熵侧：`nonce=<高熵串>` 与 `token=<高熵串>` 在取值上**完全同形**
# （S120 熵 4.88），assignment 的字段名排除拦不住熵兜底，实测 S120 会被
# `entropy.bare_alnum` 遮掉 —— 必须在此按「命中值属于哪个字段」再拦一次。
_NON_SECRET_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "nonce",
        "salt",
        "iv",
        "initializationvector",
        "initialisationvector",
    }
)

# 捕获 `<field>=` / `<field>: ` 中紧邻命中之前的那一段 key
_PRECEDING_KEY_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.-]*)\s*[:=]\s*$")


def _normalize_field_name(raw: str) -> str:
    """字段名归一化：去除非字母数字字符并小写（与 ``AssignmentDetector`` 同一口径）。"""
    return re.sub(r"[^a-z0-9]", "", raw.lower())


def is_non_secret_field_value(text: str, start: int) -> bool:
    """判断裸熵命中是否属于「公开密码学参数」字段（`nonce=` / `salt=` / `iv=` 等）。

    判据是 **span 位置 + 紧邻字段名**（与 D-08 / 公钥前缀同构的位置谓词）：
    命中之前须紧邻 ``<field>=`` 或 ``<field>:``，且字段名归一化后落在保留集内。

    Args:
        text: 原始文本。
        start: 命中区间起始偏移（闭）。

    Returns:
        True 表示该命中应作为非秘密参数被保留。
    """
    prefix = text[:start]
    match = _PRECEDING_KEY_RE.search(prefix)
    if match is None:
        return False
    return _normalize_field_name(match.group(1)) in _NON_SECRET_FIELD_NAMES


def is_public_key_span(text: str, start: int, end: int) -> bool:
    """OpenSSH 公钥硬排除（S035）：命中区间是否为 ``<算法> <base64>`` 公钥行。

    OpenSSH 公钥是 ``authorized_keys`` / ``known_hosts`` 里的常见内容，
    body 是 base64 且熵天然高（实测 ``ssh-ed25519`` 的 body 熵 4.78 > 阈值 4.2），
    故裸熵兜底会把它整段遮掉 —— 但公钥不是秘密（README：
    「公钥、证书和 CSR 不因 PEM 包装成为秘密，本测试保留它们」）。

    PEM 侧的 ``is_pem_non_secret_span`` 管不到这种形态：OpenSSH 公钥
    **没有** PEM 的 ``-----BEGIN/END`` 包装，是单行 ``算法 base64 [comment]``。

    判据是 **span 位置谓词**（与 D-08 ``is_base64_container_span`` 同构）：
    命中区间之前须存在一个已知公钥算法前缀，且（前缀, 命中）之间**只含空白与
    base64 字符** —— 即该命中确是该前缀 body 的一部分。

    不能只检查「紧邻前缀」：``_CANDIDATE_RE`` 的字母表**不含** ``/``
    （该字符被保留给 DSN/URL 结构 detector），故含 ``/`` 的 base64 body 会在
    ``/`` 处被切碎，命中起点落在 body **中段**（S035 实测）——
    此时命中前紧邻的是 ``AAAAIIm/`` 而非 ``ssh-ed25519 ``。
    因此回退扫描时允许中间存在 base64 字符，只要最终能找到一个公钥前缀。

    这样 ``ssh-ed25519 AAAAC3...``（含 ``/`` 被切段）的任一片段都被排除，
    而 ``comment=QGBZ...`` 这类**另起 token** 的高熵值仍会被正常脱敏
    （前缀与它之间隔着空白 + 非 base64 字符，回退会在遇到 ``=`` 时终止）。

    Args:
        text: 原始文本。
        start: 命中区间起始偏移（闭）。
        end: 命中区间结束偏移（开）。

    Returns:
        True 表示该命中应为 OpenSSH 公钥 body 被硬排除。
    """
    for prefix in _PUBLIC_KEY_PREFIXES:
        idx = text.rfind(prefix, 0, start)
        if idx == -1:
            continue
        # 前缀须是 token 起点（前一字符不是字母/数字/下划线），避免命中 `myssh-ed25519`
        if idx > 0 and (text[idx - 1].isalnum() or text[idx - 1] == "_"):
            continue
        # 前缀与命中之间只允许空白 + base64 字符（含被字符类排除的 ``/``）
        gap = text[idx + len(prefix) : start]
        if _PUBLIC_KEY_GAP_RE.match(gap):
            return True
    return False


def is_pem_non_secret_span(text: str, start: int, end: int) -> bool:
    """PEM 非秘密块硬排除（缺陷 4 / 缺陷 6 / 缺陷 7）：命中区间是否落在公钥 / 证书块内。

    **fail-closed 判据**：只有命中区间落在某个**已完整识别**的 PEM 非秘密块之内，
    才返回 True（可排除）。
    任何「畸形 / 未闭合 / label 错配 / 含糊」的块一律返回 False → 交给裸熵兜底遮掉。
    **宁遮不漏**：多遮公钥是可接受的误伤，少遮私钥是不可逆泄露。

    判据分两步：

    1. 用 ``iter_pem_blocks``（与 ``PemDetector`` **共享的唯一解析源**）
       解析文本中**完整且 BEGIN/END label 一致**的块（5 短横与 RFC 4716
       4 短横两种拼写）。
       未闭合（无 END）/ label 错配的块**不会**被解析出来 ——
       这正是缺陷 7 的根因修复：旧实现只读 BEGIN label、
       只要求「BEGIN 与命中之间无 END」，于是畸形块被熵侧放过、
       又被 ``PemDetector``（要求 BEGIN == END）拒绝，**两边都不遮**而泄露。
    2. 命中区间须落在某块内（``block_start < start`` 且 ``end <= block_end``），
       且 ``classify_pem_label(block.label) == "non_secret"`` —— 与 ``PemDetector``
       **共用同一分类函数**（缺陷 8），只有精确命中非秘密白名单的 label 才排除。
       private key 家族不在排除集内 —— 其 body 由 ``PemDetector``（priority 95）
       整块高优先级替换，即便 PemDetector 因故未命中，裸熵兜底也会遮它。
       非秘密块另要求命中**延伸进 body 区间**（``end > block.body_start``）——
       防止把块内 BEGIN/END 标记本身当作 body 命中而排除。

    原第 2 步还带一道「命中不得与 BEGIN 同行」的位置护栏（以 ``_PEM_BODY_GAP_RE``
    校验 ``text[body_start:start]`` 须以换行开头），**已于 2026-09-17 删除**：
    该护栏声称防 ``CERTIFICATE AUTHORITY=...`` 被误排除，但该场景不含配对块、
    进不了本循环（第 1 步已达成防护），护栏在「有块」时的唯一效果是把
    body 与 BEGIN **同行**的块也取消豁免 —— 而 RFC 7468 §2 要求两者之间必须有 eol，
    同行形态在真实 PEM 中不存在。保留它只会误遮公钥/证书 body。

    Args:
        text: 原始文本。
        start: 命中区间起始偏移（闭）。
        end: 命中区间结束偏移（开）。

    Returns:
        True 表示该命中应作为 PEM 非秘密块 body 被硬排除。
    """
    # ``iter_pem_blocks`` / ``classify_pem_label`` 定义在本文件上方（合并前它们位于``redaction.pem``）——同文件直接调用，
    # 无循环依赖。
    for block in iter_pem_blocks(text, dash=5) + iter_pem_blocks(text, dash=4):
        # 命中须落在块内（块起点在命中之前、块终点不早于命中终点）
        if block.start >= start or block.end < end:
            continue
        label_kind = classify_pem_label(block.label)
        if label_kind == "secret":
            # 空 body 豁免（S115/S116）：无实质内容的「空壳 / 教学省略」块不是真实密钥，
            # 其 body 也不该被裸熵兜底遮掉 —— 与 PemDetector 的豁免判据**同一函数**，
            # 保证两侧不会一边放过、一边遮住（缺陷 7 的同类漂移）。
            if not is_substantive_pem_body(text, block):
                gap = text[block.body_start : start]
                if gap and _PEM_BODY_GAP_RE.match(gap):
                    return True
            continue
        if label_kind != "non_secret":
            # ``unknown``（含所有 malformed / 近义 label）不排除 → 遮。
            continue
        # 命中须**延伸进 body 区间**（``end > block.body_start``），即区间相交。
        # 原实现要求「命中起于 BEGIN 之后的新行」（``text[body_start:start]`` 须以换行开头），
        # 该位置护栏已删除：它的既定目标（防 ``CERTIFICATE AUTHORITY=...`` 被误排除）
        # 由**本循环第 1 步**达成 —— ``iter_pem_blocks`` 要求 BEGIN/END 完整配对，
        # 而 ``CERTIFICATE AUTHORITY=<value>`` 不含配对块 ⇒ 根本进不了循环体。
        # 护栏在「有块」时的唯一实际效果，是把 body 与 BEGIN **同行**的块也取消豁免，
        # 致熵候选（其 ``start`` 常早于 ``body_start``，因它吞掉了 BEGIN 标记尾部）
        # 落到区间外而豁免失效 → 公钥/证书 body 被误遮为 ``bare_secret``。
        # RFC 7468 §2 要求 BEGIN 行与 body 之间必须有 eol（``textualmsg = preeb *WSP eol *posteb``），
        # 故同行形态在真实 PEM 中不存在 —— 删除护栏不影响真实输入。
        if end > block.body_start:
            return True
    return False


def is_base64_container_span(text: str, start: int, end: int) -> bool:
    """D-08 硬排除：命中区间是否落在 ``data:`` / ``;base64,`` 容器载荷内。

    ``EntropyDetector`` 现自持本判据（T-vq0）；本定义保留以兼容 ``__all__``
    与既有导入面，二者由
    ``test_detectors.py::TestDetectorConstantEncapsulation::test_entropy_self_hosts_moved_helpers``
    与源实现钉住同结果。

    判据是 **span 位置关系**，不是「文本含 data:」——
    命中区间之前最近的容器前缀与命中起点之间若**不含**空格 / 引号 / 标点等分隔符，
    则命中确在 data URI 载荷里，返回 True。

    Args:
        text: 原始文本。
        start: 命中区间起始偏移（闭）。
        end: 命中区间结束偏移（开）。

    Returns:
        True 表示该命中应作为 base64 容器载荷被硬排除。
    """
    for marker in _BASE64_CONTAINERS:
        idx = text.rfind(marker, 0, start)
        if idx == -1:
            continue
        # 命中区间须在该前缀之后
        if idx + len(marker) > start:
            continue
        gap = text[idx + len(marker) : start]
        if not _CONTAINER_GAP_RE.search(gap):
            return True
    return False
