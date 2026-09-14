# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.redaction.operations

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

脱敏操作层：本包**全部 ``redact_*`` 出口**集中于此。

**唯一出口是 detector 管线**（``scan_text`` / ``redact_text`` / ``redact_payload`` /
``redact_for_export`` / ``count_sensitive_hits``）：所有 detector 扫描**同一份原始
文本**，产出 ``Finding``；合并重叠区间后从后往前**一次性替换**（避免位移），
替换与计数共享同一 ``ScanResult``。

**已知值走同一条管线**：runtime 工具出口（``core/tools/runtime_tools``）把
SBX / backend 的已知值并入 ``settings.known_sensitive_values`` 后调用
``redact_text``，与其它命中一起在 ``merge_spans`` 中按 ``priority`` 决策。
历史上曾有一条独立的「已知值精确替换」出口（``redact_known_values`` + legacy
占位符 ``__BKAI_AGENT_REDACTED__``），因与本管线共用同一匹配机制却只改文案、
且无生产调用点，已删除。

**预筛选（缺陷 3 修复）**：每个 detector 的 ``scan()`` 自身在方法开头调用一次自家
``could_match()`` —— 这是 ``detectors.Detector`` 协议既有契约，此前无调用点（dead code）。
缺此守卫时 ``AssignmentDetector._KEY_VALUE_RE`` 在无 ``=`` / ``:`` 的长文本上
O(n²) 退化。**预筛选所有权现由 ``scan()`` 独有**（T-vq0）：
本模块**不再**显式调用 ``detector.could_match()``，避免同一预筛选跑两遍，
也让「新 detector 忘记接入预筛选」不可能因调用方遗漏而复现。

外层：本模块 ``_detectors_for_scan()`` ——
PR2 已接入 9 个 detector；PR3 追加的 ``EntropyDetector`` 在同一列表末尾并入。

**detector 清单（按证据强度降序）**：
``registered``（100）> ``pem``（95）> ``headers`` / ``dsn``（90）> ``jwt``（88）>
``cookie`` / ``url``（85）> ``vendor``（80）> ``assignment``（70）> ``entropy``（50）。
顺序不决定语义（所有 detector 扫同一份原始文本，最终由 ``merge_spans``
按 ``priority`` 决策），排列仅为可读性。

**配置注入（T-06-24）**：``scan_text`` / ``redact_text`` / ``redact_payload`` 接受
可选关键字参数 ``settings: SecurityRedactionSettings | None``，默认 ``None``
回落 ``SecurityRedactionSettings()``（env 默认工厂路径）。调用方（``security_wrapper``）
按需传平台下发实例 —— 叶节点不各自读环境变量，
配置唯一入口是 ``AgentConfig.security_settings.redaction``。

**保行替换（``preserve_line_breaks``）**：``scan_text`` / ``redact_text``
接受可选关键字参数 ``preserve_line_breaks: bool = False``。默认 ``False`` ⇒
输出与引入本参数之前**逐字节相同**。启用时**只改变替换输出**：把命中区间折叠为
占位符的同时，**保留其原有的行分隔符**（``len(value.split("\\n")) - 1`` 个
``"\\n"`` 原样保留），占位符占首行、其余被遮行留空 —— 即「被遮 N 行 ⇒ 输出 N 行」，
故展示层加入的行号不会因为掩码压缩行数而错位。``\\r\\n`` 天然满足守恒。

检测集合 / ``merge_spans`` 结果 / ``unique_findings`` / ``raw_rule_hits`` 在该参数
的任何取值下都相同 —— 它**不参与检测阶段**。

用途：runtime 工具（``core/tools/runtime_tools``）必须先对**原文**完成整段脱敏，
再由 provider 添加 ``行号 + TAB``，否则「格式化后的展示字符」会被后续 guard
当成秘密正文而误报；同时跨行掩码若压缩行数，展示行号会与源码行号错位。
无换行（单行 / 空串）时输出与默认替换相同，故该参数对单行输入是空操作。

---

**已知值只有一个通道**：``scan_text`` 的已知值取自 ``settings.known_sensitive_values``，
**没有独立的 ``known_values`` 参数** —— 此前那个参数是 6 跳透传链，且与 ``settings``
语义重复：调用方若只设了 ``settings.known_sensitive_values`` 而漏传 ``known_values``，
脱敏会**静默失效**。收敛为单通道后该缺陷不复现。

**匹配机制**：``RegisteredSecretDetector`` 组内按值长度降序，长值优先命中，
顺序无关；并经 ``merge_spans`` 消解重叠 span。历史上那条独立出口曾是逐值
``str.replace``，顺序即列表顺序 —— 短值先替换会把长值切碎
（``["abc", "abcdef"]`` 对 ``abcdef`` 只得到 ``__REDACTED__def``）。
删除该出口后，这个「未复用 detector」的缺陷也从根上消失。

**依赖方向**：本包只复用同包内的 ``detectors`` / ``findings``，
**禁止** import ``aidev_agent.config`` / 任何 backend 类型 / ``core`` / ``services`` /
``api`` —— 配置与 backend 的解析留在**调用方（core）**。

公开接口：``redact_text`` / ``redact_payload`` / ``scan_text`` /
``count_sensitive_hits`` / ``redact_for_export``。
"""

from __future__ import annotations

import re
from typing import Any

from aidev_agent.packages.security.redaction.detectors import (
    AssignmentDetector,
    CookieDetector,
    Detector,
    DsnDetector,
    DsnJdbcDetector,
    EntropyDetector,
    HeadersDetector,
    JwtDetector,
    PemDetector,
    RegisteredSecretDetector,
    UrlDetector,
    VendorTokenDetector,
)
from aidev_agent.packages.security.redaction.findings import Finding, ScanResult, merge_spans
from aidev_agent.packages.security.redaction.masking import mask
from aidev_agent.packages.security.redaction.policy import RedactionPurpose, mask_style_for
from aidev_agent.pydantic_models import SecurityRedactionSettings

# 凭据字段名后缀（不区分大小写，忽略分隔符）——迁移自旧实现
_CREDENTIAL_FIELD_SUFFIXES: tuple[str, ...] = (
    "apikey",
    "api_key",
    "access_key",
    "access_token",
    "secret",
    "secret_key",
    "app_secret",
    "password",
    "passwd",
    "pwd",
    "token",
    "auth_token",
    "credential",
    "credentials",
    "private_key",
    "authorization",
)

_NORMALIZED_CREDENTIAL_SUFFIXES: tuple[str, ...] = tuple(
    re.sub(r"[^a-z0-9]", "", suffix.lower()) for suffix in _CREDENTIAL_FIELD_SUFFIXES
)


def _is_credential_field(key: str) -> bool:
    """判断字段名是否为凭据字段（忽略大小写与下划线 / 连字符等分隔符）。"""
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return normalized.endswith(_NORMALIZED_CREDENTIAL_SUFFIXES)


def _split_known_sensitive_values(raw: str | None) -> list[str]:
    """把 ``SecurityRedactionSettings.known_sensitive_values``（逗号分隔原文）拆成 list。

    **刻意不做任何规范化**（不 lower / 不去尾点）：敏感值是大小写敏感的 secret，
    规范化会让脱敏静默失效。只做 ``strip`` + 过滤空串。
    """
    return [v.strip() for v in (raw or "").split(",") if v.strip()]


def _detectors_for_scan(*, settings: SecurityRedactionSettings) -> list[Detector]:
    """组装本次扫描的 detector 列表（新 detector 的接入点）。

    按证据强度降序排列（registered > pem > headers/dsn > jwt > cookie/url >
    vendor > assignment > entropy）；顺序不决定语义 —— 所有 detector
    扫描同一份原始文本，由 ``scan_text`` 统一 ``merge_spans`` 后按 ``priority`` 决策。

    已知敏感值取自 ``settings.known_sensitive_values``（逗号分隔原文）——
    **唯一配置通道是 ``settings``**：不再有独立的 ``known_values`` 参数，
    避免同一条配置数据出现两个入口（后者会被静默忽略）。空值 ⇒ 空 detector
    ⇒ ``could_match`` 返回 False ⇒ 零命中。本模块不读 env / backend
    （依赖方向硬约束，配置由调用方经 ``settings`` 传入）。

    裸熵兜底（``EntropyDetector``）排在**最后**，阈值与开关取自 ``settings``。

    **开关（组装层独占，全字段平等）**：

    - ``enable_redact_secrets`` 是**总开关**，也是**硬熔断**：置 False 时本函数
      直接返回 ``[]`` —— 不存在任何绕过它的子项，脱敏引擎完全不跑。
    - 其余各 ``enable_redact_*`` 是**分项开关**，作用域仅限自己的 detector：
      关闭 ⇒ 该 detector 根本不构造、不入列表。
      DSN 与 JDBC 串共用 ``enable_redact_dsn_passwords``，二者要么都在、要么都不在。
    - **子项无法穿透总开关**：总开关为 False 时逐项判断根本不会执行，
      故「关闭总开关 + 打开某子项」仍然是全关（无优先级冲突语义）。
    - **本列表不是脱敏出口的全部**：``redact_payload`` 的字段名驱动整体掩码
      （凭据字段分支）不经本函数，但同样受 ``enable_redact_secrets`` 硬熔断与
      ``enable_redact_structured_fields`` 分项管辖（见 ``redact_payload``）。

    分项开关关闭 **不等于** 该能力彻底失效 —— 脱敏是多 detector 分层兜底，
    同一份文本可能被更高层的 detector 命中（例：关掉 ``enable_redact_structured_fields``
    后 ``password=<高熵值>`` 仍可能由裸熵兜底遮掉）。要彻底关闭脱敏用总开关。

    开关的**唯一实现方式是整项排除**：关闭的 detector **不进**返回列表，
    故不参与 ``scan_text`` 的扫描循环。detector 自身不持有任何门控状态
    （``detectors`` 模块里没有 ``enabled`` 构造参数 / 实例属性）——
    「扫什么」是 detector 的职责，「这轮要不要跑」是本函数的决策。
    代价是**返回列表的长度随开关变化**（默认全开时为 11；总开关关闭时为 0），
    调用方需要「列表成员即本轮全跑」这一不变量的地方（如断言 / 计数）须以此为前提。
    """
    # 总开关 = 硬熔断：关闭时引擎完全不跑，任何分项开关都不可绕过（无优先级冲突语义）
    if not settings.enable_redact_secrets:
        return []

    # 以下逐项判断分项开关：关闭 ⇒ 该 detector 不构造、不入列表。
    detectors: list[Detector] = []
    if settings.enable_redact_registered_secrets:
        detectors.append(
            RegisteredSecretDetector.from_values(
                _split_known_sensitive_values(settings.known_sensitive_values),
            )
        )
    if settings.enable_redact_private_keys:
        detectors.append(PemDetector())
    if settings.enable_redact_authorization_headers:
        detectors.append(HeadersDetector())
    if settings.enable_redact_jwt:
        detectors.append(JwtDetector())
    if settings.enable_redact_dsn_passwords:
        detectors.extend([DsnDetector(), DsnJdbcDetector()])
    if settings.enable_redact_cookies:
        detectors.append(CookieDetector())
    if settings.enable_redact_url_credentials:
        detectors.append(UrlDetector())
    if settings.enable_redact_vendor_tokens:
        detectors.append(VendorTokenDetector())
    if settings.enable_redact_structured_fields:
        detectors.append(AssignmentDetector())
    if settings.enable_redact_bare_entropy:
        # 裸熵兜底（最低优先级 priority=50，阈值经 SecurityRedactionSettings 下发）
        detectors.append(
            EntropyDetector(
                min_length=settings.redact_secrets_min_length,
                alnum_threshold=settings.redact_secrets_entropy_threshold,
            )
        )
    return detectors


def _preserve_line_breaks_in(value: str, placeholder: str) -> str:
    """把 ``value`` 压成占位符，**保留其原有的行分隔符**（间隔数守恒）。

    ``value`` 是被命中区间的原文，``placeholder`` 是该出口的替换文案
    （typed sentinel / legacy 占位符 / partial 掩码，取决于调用方）。

    判据是 ``value.split("\\n")`` 的**元素个数**：占位符占第一个元素，
    其余每个元素替换为一个空串，元素间用 ``"\\n"`` 连接 —— 即
    ``len(value.split("\\n")) - 1`` 个换行**原样保留**（不是新增）：

    - ``"BEGIN\\nBODY\\nEND"`` ⇒ ``"[REDACTED:private_key]\\n\\n"``
      —— 原来 2 个 LF，替换后仍是 2 个 LF ⇒ 仍是 3 行（占位符 + 2 个空行），
      故区间后（或展示层加的）行号不会因为掩码压缩而错位。
    - ``"A\\nB"``（多行已知值）⇒ ``legacy + "\\n"`` —— 同样是「行数守恒」。

    **区间自带的末换行照常保留**（这是本函数存在的全部意义：不丢分隔符）。
    因此若区间末尾的换行同时也是下一行的分隔符，输出会多出一个空行 ——
    这是刻意的：调用方（``provider``）只应对**整行对齐**的文本使用本模式，
    那时「被遮 N 行」与「输出 N 行」严格等价。

    ``\\r\\n`` 天然满足守恒：``"A\\r\\nB\\r\\n"`` ⇒ ``split("\\n")`` 得
    ``["A\\r", "B\\r", ""]``，尾部空串产出空占位符，故仍是 3 个元素 / 3 行。

    本函数**只作用于替换输出**：不参与检测，不改变 span 合并或命中计数。
    """
    parts = value.split("\n")
    if len(parts) <= 1:
        # 无换行 ⇒ 与默认替换逐字相同
        return placeholder
    # 首元素放占位符，其余元素清空；空元素同样清空 ⇒ 分隔符数量与原文一致
    return "\n".join([placeholder, *("" for _ in parts[1:])])


def _apply_replacements(
    text: str,
    findings: list[Finding],
    *,
    purpose: RedactionPurpose,
    settings: SecurityRedactionSettings,
    preserve_line_breaks: bool = False,
) -> str:
    """从后往前一次性替换（避免位移），保持未命中区间字节级不变。

    partial 掩码阈值由 ``settings`` 派生并显式传给 :func:`mask`（T-urf-03）——
    阈值不再硬编码在 ``masking`` 模块中。

    ``preserve_line_breaks=True`` 时改用 :func:`_preserve_line_breaks_in`：
    命中区间跨 N 行就仍占 N 行（首行放掩码，其后留空）。**仅影响替换输出** ——
    检测集合 / span 合并 / 命中计数与本参数无关（见 :func:`scan_text`）。
    """
    if not findings:
        return text

    style = mask_style_for(purpose)
    partial_min_len = settings.redact_partial_min_len
    partial_head = settings.redact_partial_head
    partial_tail = settings.redact_partial_tail
    result = text
    for finding in sorted(findings, key=lambda f: f.start, reverse=True):
        raw = text[finding.start : finding.end]
        masked = mask(
            raw,
            kind=finding.kind,
            style=style,
            partial_min_len=partial_min_len,
            partial_head=partial_head,
            partial_tail=partial_tail,
        )
        replacement = _preserve_line_breaks_in(raw, masked) if preserve_line_breaks else masked
        result = result[: finding.start] + replacement + result[finding.end :]
    return result


def scan_text(
    text: str,
    *,
    purpose: RedactionPurpose = RedactionPurpose.LOG,
    settings: SecurityRedactionSettings | None = None,
    preserve_line_breaks: bool = False,
) -> ScanResult:
    """扫描文本并按 purpose 脱敏，返回 ``ScanResult``。

    Args:
        text: 待扫描文本。
        purpose: 脱敏出口语义（决定掩码风格）。
        settings: 脱敏配置（阈值 / 开关 / 已知敏感值）。``None`` 时回落
            ``SecurityRedactionSettings()``（env 默认工厂路径，与不传参时行为对等）；
            调用方（``security_wrapper``）应按需传入平台下发实例。
            叶节点不直读 env（T-06-24）。**已知敏感值也经此传入** ——
            见 :func:`_detectors_for_scan`。
        preserve_line_breaks: 保行替换开关，默认 ``False``（与改动前逐字节相同）。
            ``True`` 时命中区间跨 N 行就仍占 N 行 —— 首行放掩码、其后留空，
            换行序列按原文保留（``\\r\\n`` 作为一个单位）。**只作用于替换阶段**：
            检测集合 / span 合并 / ``unique_findings`` / ``raw_rule_hits``
            在任何取值下都相同。用途是让 runtime 工具在**加展示行号之前**脱敏时
            不压缩行数，从而保持源码行号与原文一致。

    Returns:
        ``ScanResult``（脱敏文本 + 合并后 cluster 数 + 合并前 rule_id 计数）。
        ``raw_rule_hits`` 含裸熵的独立键（``entropy.bare_alnum`` / ``entropy.bare_base64``）。
    """
    if not isinstance(text, str) or not text:
        return ScanResult(redacted_text=text, unique_findings=0, raw_rule_hits={})

    effective_settings = settings if settings is not None else SecurityRedactionSettings()
    raw: list[Finding] = []
    for detector in _detectors_for_scan(settings=effective_settings):
        # 预筛选已由 ``detector.scan()`` 自身承担（T-vq0）：
        # 该 detector 的 ``could_match`` 是「廉价预筛选」，此前由本循环调用；
        # 现移入 ``scan``，调用方不再重复判定
        # （缺陷 3 的守卫仍由各 detector 自助持有）。
        raw.extend(detector.scan(text))

    merged = merge_spans(raw)

    # 计数按合并前（raw）口径，同一 rule_id 出现几次计几次
    raw_rule_hits: dict[str, int] = {}
    for finding in raw:
        raw_rule_hits[finding.rule_id] = raw_rule_hits.get(finding.rule_id, 0) + 1

    return ScanResult(
        redacted_text=_apply_replacements(
            text,
            merged,
            purpose=purpose,
            settings=effective_settings,
            preserve_line_breaks=preserve_line_breaks,
        ),
        unique_findings=len(merged),
        raw_rule_hits=raw_rule_hits,
    )


def redact_text(
    text: str,
    *,
    purpose: RedactionPurpose = RedactionPurpose.LOG,
    settings: SecurityRedactionSettings | None = None,
    preserve_line_breaks: bool = False,
) -> str:
    """对自由文本执行脱敏。

    Args:
        text: 待脱敏文本。
        purpose: 脱敏出口语义。
        settings: 脱敏配置（``None`` 回落 ``SecurityRedactionSettings()``）；见 :func:`scan_text`。
        preserve_line_breaks: 保行替换开关（默认 ``False``）；语义见 :func:`scan_text`。

    Returns:
        脱敏后的文本。
    """
    return scan_text(
        text,
        purpose=purpose,
        settings=settings,
        preserve_line_breaks=preserve_line_breaks,
    ).redacted_text


def redact_payload(
    obj: Any,
    *,
    purpose: RedactionPurpose = RedactionPurpose.LOG,
    settings: SecurityRedactionSettings | None = None,
) -> Any:
    """递归脱敏结构化数据（dict / list / tuple）。

    对 dict 中字段名为凭据字段**且值不是容器**的项做整体掩码；容器值**递归进入**
    而非整体替换（解 D6）；str 走 :func:`redact_text`；其余原样返回。

    Args:
        obj: 任意嵌套的 dict / list / tuple / str / 其他。
        purpose: 脱敏出口语义。
        settings: 脱敏配置（``None`` 回落 ``SecurityRedactionSettings()``）；见 :func:`scan_text`。
            已知敏感值经此递归透传（``settings`` 即唯一配置通道）。

    Returns:
        脱敏后的同构数据结构。

    开关口径（与 ``scan_text`` / runtime 工具出口对齐）：

    - ``enable_redact_secrets`` 是总开关：置 False 时本函数**立即返回原对象**，
      结构化字段掩码与 ``redact_text`` 均不执行 —— 属三出口统一的硬熔断。
    - ``enable_redact_structured_fields`` 是分项开关：置 False 时**字段名驱动的整体
      掩码**（凭据字段分支）不执行，但递归进入的字符串仍走 :func:`redact_text`
      （由文本引擎各自的分项开关管辖，可被更高层兜底命中）—— 与
      ``_detectors_for_scan`` 中 ``AssignmentDetector`` 共用同一开关语义。
    """
    effective_settings = settings if settings is not None else SecurityRedactionSettings()

    # 总开关硬熔断：与 ``scan_text``（``_detectors_for_scan`` 返回空）对齐，
    # 一次判定覆盖整棵子树，保证 enable_redact_secrets=False 时三出口口径一致。
    if not effective_settings.enable_redact_secrets:
        return obj

    if isinstance(obj, dict):
        style = mask_style_for(purpose)
        result: dict[Any, Any] = {}
        for key, value in obj.items():
            if (
                effective_settings.enable_redact_structured_fields
                and isinstance(key, str)
                and _is_credential_field(key)
                and not isinstance(value, (dict, list, tuple))
            ):
                result[key] = mask(
                    str(value),
                    kind="credential",
                    style=style,
                    partial_min_len=effective_settings.redact_partial_min_len,
                    partial_head=effective_settings.redact_partial_head,
                    partial_tail=effective_settings.redact_partial_tail,
                )
            else:
                result[key] = redact_payload(value, purpose=purpose, settings=effective_settings)
        return result
    if isinstance(obj, list):
        return [redact_payload(item, purpose=purpose, settings=effective_settings) for item in obj]
    if isinstance(obj, tuple):
        return tuple(redact_payload(item, purpose=purpose, settings=effective_settings) for item in obj)
    if isinstance(obj, str):
        return redact_text(obj, purpose=purpose, settings=effective_settings)
    return obj


def count_sensitive_hits(text: str, *, settings: SecurityRedactionSettings | None = None) -> dict[str, int]:
    """统计文本中的敏感信息命中数（只计数、不落明文）。

    与 ``redact_text`` 共享同一 ``scan_text``，消除「脱敏口径」与「审计口径」漂移。
    保持旧的三键口径（``vendor_token`` / ``credential_key_value`` / ``total``）；
    ``credential_key_value`` 现由 assignment detector 提供**真实计数**
    （``raw_rule_hits`` 中所有 ``assignment.*`` 键之和）。

    ``total`` 以 vendor + credential_key_value 为口径 —— 裸熵（``entropy.bare_*``）
    是兜底命中的**独立命名空间**，其计数保留在 ``ScanResult.raw_rule_hits`` 中供
    误伤校准，不并入此处三键（避免与 vendor/assignment 同口径重叠导致重复计数）。

    Args:
        text: 待统计文本。
        settings: 脱敏配置（``None`` 回落 ``SecurityRedactionSettings()``）；见 :func:`scan_text`，
            已知敏感值同样经此传入。

    Returns:
        命中计数字典：``vendor_token`` / ``credential_key_value`` / ``total``。
    """
    result = scan_text(text, purpose=RedactionPurpose.LOG, settings=settings)
    vendor_token = sum(count for rule_id, count in result.raw_rule_hits.items() if rule_id.startswith("vendor."))
    credential_key_value = sum(
        count for rule_id, count in result.raw_rule_hits.items() if rule_id.startswith("assignment.")
    )
    return {
        "vendor_token": vendor_token,
        "credential_key_value": credential_key_value,
        "total": vendor_token + credential_key_value,
    }


def redact_for_export(obj: Any) -> Any:
    """导出 / 上报前的强制脱敏入口（等价于 ``purpose=EXPORT``）。"""
    if isinstance(obj, str):
        return redact_text(obj, purpose=RedactionPurpose.EXPORT)
    return redact_payload(obj, purpose=RedactionPurpose.EXPORT)


__all__ = [
    # 文本脱敏 / 扫描
    "redact_text",
    "scan_text",
    # 结构化脱敏
    "redact_payload",
    "redact_for_export",
    # 命中统计
    "count_sensitive_hits",
]
