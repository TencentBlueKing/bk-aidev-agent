# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.redaction.detectors

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

**分层（``260915-0dr`` 合并 → 后续抽取至 ``redaction/utils.py``）**：

1. **PEM 原语 + 共享统计工具** 已抽取至 ``redaction/utils.py``（原 ``pem.py`` 与
   ``entropy.py`` 两层）：``normalize_label`` / ``classify_pem_label`` / ``PemBlock`` /
   ``iter_pem_blocks`` / ``shannon_entropy`` / ``char_class_count`` / ``classify_alphabet`` /
   形状判据 / ``is_pem_non_secret_span`` / ``is_base64_container_span`` 等。
2. **detector 类**（本模块）：依赖上述两层，经本模块顶部 import 消费。

**共享原语经本模块按名 re-export**（见顶部 import 与 ``__all__``），
故 ``from ...redaction.detectors import is_pem_non_secret_span`` 等既有导入面保持不变，
且与 ``utils`` 中是**同一对象**（``is`` 成立）—— 不存在实现副本。

``classify_pem_label`` 仍是 label 分类的**唯一**判据 —— ``PemDetector``（产 finding 侧，本模块）
与 ``is_pem_non_secret_span``（熵侧排除，``utils.py``）都只经它决定「要不要保留」。
二者共用同一实现是**结构性**保证：在任一侧重写一份 PEM 谓词会重现
**缺陷 7/8 的 fail-open 明文泄露漂移**（两份 PEM 分类实现分叉，CI 全绿也发现不了）。
该同一性由 ``tests/packages/security/test_detectors.py::TestMergedModuleIntegrity``
**常驻接管**（CI 每次运行；经 11 组植入实证判别力）。

**共享层模块级私有名全部位于 ``utils.py``**（各 detector 的私有常量一律留在本模块各自类体内，
不得摊平到模块级）—— ``_VAR_REF_RE`` / ``_HINT_RE`` / ``_is_variable_reference``
在 ``assignment`` / ``dsn`` / ``url`` 三个 detector 中同名但**字面量 / 实现不同**；
摊到模块级会静默遮蔽（晚绑定的模块全局），行为漂移且**无报错**。
类命名空间隔离是「合并前各文件已完成封装」（T-vq0）建立的不变量，**不得回退**。

**detector 类的定义顺序是硬约束**（``from __future__ import annotations`` 只延迟注解，
不延迟类体内的表达式求值）：
- ``DetectorRule`` 必须在 ``VendorTokenDetector`` 之前 ——
  后者的 ``_VENDOR_RULES`` 在**类体内立即调用** ``DetectorRule(...)``。
- ``RegisteredValue`` 必须在 ``RegisteredSecretDetector`` 之前
  （字段类型 + ``from_values`` 内 ``isinstance`` 检查）。

**共享原语（pem → entropy）与 detector 的定义顺序不再是同文件基线** ——
前两层已迁至 ``utils.py``；本模块与 ``utils`` 的跨模块引用全部位于函数体 / 方法体内
（延迟绑定），故任何排列都能 import 并正确运行。
固定此顺序只为可读性与便于逐行核对搬运完整性。

**依赖方向**：``packages.security`` 约定 —— 仅标准库 / pydantic / langchain_core /
``pydantic_models`` / 本包内模块；**禁止** ``core`` / ``services`` / ``api``。

**预筛选所有权（T-vq0，缺陷 3 根因防线）**：``could_match``
仍是 ``Detector`` 协议的一部分，但**调用方不再负责调用它** ——
每个 ``scan`` 的实现必须在自身开头调用一次自家的 ``could_match``
并在为 False 时立即返回 ``[]``。
``redaction.operations`` **不再显式调用** ``detector.could_match()``
（避免同一预筛选跑两遍，也让「新 detector 忘记接入预筛选」不可能因调用方遗漏而复现）。

**门控所有权（组装方独有）**：detector **不持有任何开关状态** ——
构造参数与实例属性里都没有 ``enabled``。分层开关
（``enable_redact_*``）的唯一实现方式是
:func:`redaction.operations._detectors_for_scan` 组装时**整项排除**：
被关闭的 detector 根本不进返回列表，因而不参与 ``scan_text`` 的循环。
「扫什么」是本模块 detector 的职责，「这轮要不要跑」是组装方的决策 ——
把门控放在 detector 里会让同一份配置同时拥有「构造时忽略」与「运行期早退」
两条语义不同的路径，且关闭项仍会被构造、仍会出现在 ``_detectors_for_scan``
的返回列表里（列表长度与检测集合不再对应）。

公开接口：``Detector`` + 11 个 detector（见 ``__all__``），另含自 ``utils`` re-export 的
共享原语名。``DetectorRule`` / ``RegisteredValue`` 按名可导入
（它们是原**子模块**公开面），但**不进** ``__all__``。

**其余安全理由（逐条随实现保留）**：缺陷 1（query string 值吞掉 ``&``）/
缺陷 2（变量引用误判致真实 secret 漏报）/ 缺陷 3（``_KEY_VALUE_RE`` O(n²) 与预筛选缺失）/
缺陷 4（PEM 非秘密块被裸熵二次遮掉）/ 缺陷 5（``\\b`` 锚点丢弃数字前缀键）/
缺陷 D9（DSN / cookie / PEM 的结构保真）/ 缺陷 D10（短 ``Bearer`` 与 ``Basic`` 凭据漏检）/
T-06-10 ~ T-06-24 系列（ReDoS 有界量词、JWT 整体替换、变量引用例外等）/
T-06-12（ReDoS 防护）/ T-06-13（绝不重新序列化 URL）/ T-06-14（负例排除三层防线）/
T-06-15（JWT 三段 + 五段）/ T-06-17（源码模板例外）/ T-06-21（候选有界量词）/
T-06-22（裸熵独立 rule_id 便于校准）/ T-06-23（裸熵最低优先级不覆盖结构化证据）/
T-06-24（不读环境变量，阈值经构造参数注入；开关由组装方决定 —— detector 无 ``enabled``）/ T-urf-02（已知值显式注入，无模块级态）/
T-urf-03（partial 掩码阈值由 settings 派生）/ D-08（``data:`` / ``;base64,`` 容器硬排除）。
各条理由的完整正文见对应实现处的 docstring 与注释。
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import ClassVar, Protocol
from urllib.parse import unquote

from aidev_agent.packages.security.redaction.findings import Finding

# 共享原语（PEM 解析 / 分类 + 统计工具）已抽取至 ``redaction/utils.py``。
# 此处按名 re-export，保持 ``from ...redaction.detectors import is_pem_non_secret_span``
# 等既有导入面不变（它们是原 pem/entropy 子模块的公开名，见下方 ``_SHARED_REEXPORTS``）。
from aidev_agent.packages.security.redaction.utils import (
    PemBlock,
    _normalize_field_name,
    char_class_count,
    classify_alphabet,
    classify_pem_label,
    is_base64_container_span,
    is_fixed_hex,
    is_monotonic_sequence,
    is_non_secret_field_value,
    is_pem_non_secret_span,
    is_placeholder_value,
    is_public_key_span,
    is_repetition,
    is_substantive_pem_body,
    is_uuid_like,
    iter_pem_blocks,
    iter_unterminated_secret_pem_spans,
    normalize_label,
    shannon_entropy,
)

# 显式 re-export 声明：上列名字中部分仅用于对外导入面（本模块自身不引用）。
# 通过 ``__all__`` 声明转出，既保持既有导入面（原 pem/entropy 子模块的公开名），
# 也锁定转出集合不被静默收窄。
__all__ = [
    # detector 协议
    "Detector",
    # 结构化协议 detector（按证据强度降序：pem 95 > headers/dsn 90 > jwt 88 > cookie/url 85）
    "PemDetector",
    "HeadersDetector",
    "DsnDetector",
    "DsnJdbcDetector",
    "JwtDetector",
    "CookieDetector",
    "UrlDetector",
    # 已注册值与厂商前缀
    "RegisteredSecretDetector",
    "VendorTokenDetector",
    # 上下文推断（严格字段 + 歧义字段评分）
    "AssignmentDetector",
    # 裸高熵兜底（最低优先级）
    "EntropyDetector",
    # 共享原语 re-export（实现已抽取至 ``redaction/utils.py``）
    "PemBlock",
    "char_class_count",
    "classify_alphabet",
    "classify_pem_label",
    "is_base64_container_span",
    "is_fixed_hex",
    "is_monotonic_sequence",
    "is_non_secret_field_value",
    "is_pem_non_secret_span",
    "is_placeholder_value",
    "is_public_key_span",
    "is_repetition",
    "is_substantive_pem_body",
    "is_uuid_like",
    "iter_pem_blocks",
    "iter_unterminated_secret_pem_spans",
    "normalize_label",
    "shannon_entropy",
]

# ===== 检测器（原 detectors.py 内容，260915-0dr 合并后紧随三层定义）=====


class Detector(Protocol):
    """检测器协议：廉价预筛选 + 原文 span 扫描。

    协议**不含**门控面：detector 不持有 ``enabled`` 一类的开关状态，
    是否参与本轮扫描由组装方（``operations._detectors_for_scan``）决定 —— 见模块头。
    """

    rule_id: str

    def could_match(self, text: str) -> bool:
        """廉价预筛选：文本是否可能命中（避免昂贵扫描）。

        实现约定：``scan`` 必须在自身开头调用本方法一次，为 False 时直接返回 ``[]``。
        """
        ...

    def scan(self, text: str) -> list[Finding]:
        """在原始文本上扫描，产出命中列表。"""
        ...


@dataclass(frozen=True)
class DetectorRule:
    """单条检测规则（正则 + 类型标签 + 优先级 + 前缀字面量）。

    Args:
        rule_id: 规则标识（如 ``vendor.openai``）。
        kind: 凭据类型标签（用于 typed sentinel）。
        regex: 编译后的正则。
        priority: 优先级（区间重叠合并时保留最高者）。
        hints: 该规则的前缀字面量（廉价预筛选用）。与 ``regex`` **同处一条规则**，
            修改正则时不会遗漏 —— 任何非空 ``hints`` 都必须能在自身 ``regex``
            的匹配结果中作为前缀出现。
    """

    rule_id: str
    kind: str
    regex: re.Pattern[str]
    priority: int
    hints: tuple[str, ...] = ()


class AssignmentDetector:
    """key=value 赋值检测器（严格字段 + 歧义字段评分）。

    路径 A —— 严格字段
        `_STRICT_FIELD_NAMES`：命中即脱敏，不走评分。
        命中 span 只覆盖值本体（不含 key 与分隔符、不含引号），替换后 password= 前缀保真
        同时让「同一值被 vendor detector 也命中」时的 span 合并自然正确。

    路径 B —— 歧义字段
        字段名归一化后以 key / token / secret 结尾：走**上下文评分**，score >= 4 触发。

    1. 严格字段豁免变量引用：严格字段本无评分流程
       password=$DB_PASSWORD / ${DB_PASSWORD} / os.getenv(...) 不被替换：源码配置模板不可被当作真实 secret 破坏
       故在严格路径命中后追加一次变量引用短路
       同理豁免被 `{` 边界截断的 f-string 前缀（password=f"{x}" → 值 `f`），见 :meth:`_is_fstring_prefix`
    2. 优先使用形状判据而非熵：
       排除项的判据是纯 hex + 特定长度这一**形状**，不是熵
       实测 16 位 hex 在本仓库样本上熵可达 4.000 > 无门限 4.2 判据时的残余。
       但形状豁免是**召回取舍**而非单纯过滤，且**仅作用于歧义路径**（:meth:`_score_ambiguous` 的 -4）：
       那里字段名证据弱，GPG key ID / fingerprint 是主要误报面；
       严格要求字段路径（password / secret / api_key 等）以字段名高置信度为据，不做形状豁免 ——
       否则 password=01234567 这类低熵真值会被整体漏掉（实测 APP_PASSWORD=0123456789abcdef 原样泄露）。
       代价是 strict 路径下 password=<16 位纯 hex> 这类低熵真值也会被脱敏，误伤方向安全。

    评分：
    +2 长度>=24 / +2 熵达阈值 / +1 字符类别>=3 / +2 字段名以 key|token|secret 结尾；
    -4 UUID-ULID-KSUID-常见 digest-trace ID 形状 / -4 纯 hex 且长度 8/16/32/40（仅歧义路径）
    -3 变量引用（$TOKEN / ${TOKEN} / os.getenv(...) / process.env.X）

    性能：
        _KEY_VALUE_RE 的 key 前缀锚定为 (?<![A-Za-z0-9_-])[0-9]* —— 见该正则上方的因果说明，
        数字前缀由**捕获组之外**的 [0-9]* 消费，故 1password= 这类数字前缀键仍命中且线性。
        取真实 token 边界（禁止字母 / 数字 / 下划线 / 连字符）而非仅禁止字母，才能让
        「数字-字母交替」串（1a1a1a...）不在每个字母位重启贪心扫描。
        不用 \\b：\\b 在「数字后接字母」处无边界（1 与 p 同为 \\w）会静默丢弃 1password= / 9api_key= / 2secret=。
        该 detector 的 scan 入口另跑自家 could_match 预筛选，但**不能**依赖它掩盖正则自身的退化 ——
        任何含 = / : 的长文本都会通过预筛选并进入本正则。
    """

    rule_id: str = ""

    # 赋值检测优先级（低于 vendor 的 80、registered 的 100）：vendor 是厂商格式强证据，assignment 是上下文推断
    _ASSIGNMENT_PRIORITY: ClassVar[int] = 70

    # 歧义字段触发阈值（DESIGN §3.5 / CONTEXT D-04）
    _SCORE_THRESHOLD: ClassVar[int] = 4

    # 变量引用上下文窗口：取 value 在原文本中**结束之后**的顺延片段（不是重叠窗口），
    # 用于应对 ${X} / os.getenv('X') 被 _KEY_VALUE_RE 的值边界截断的情形。
    # 恒拼接（context 非空即拼）不会引入假阳性：_VAR_REF_RE 全部 alternative 以 ^ 锚定在值起点。
    _VAR_REF_CONTEXT: ClassVar[int] = 64

    # 路径 A —— 严格凭据字段名（迁移自 redact.py:75-87 的 _HIGH_SIGNAL_TEXT_KEYS）
    _STRICT_FIELD_NAMES: ClassVar[tuple[str, ...]] = (
        "password",
        "passwd",
        "apikey",
        "api_key",
        "access_key",
        "access_token",
        "secret",
        "secret_key",
        "app_secret",
        "authorization",
        "private_key",
    )

    # 路径 B —— 歧义字段后缀：归一化后以这些词结尾时参与评分（而非直接命中）
    _AMBIGUOUS_SUFFIXES: ClassVar[tuple[str, ...]] = ("key", "token", "secret")

    # 负例排除集（必须先于评分判定，命中即跳过该匹配）：
    # 含 key/token/secret 语义但属业务标识，非凭据 —— T-06-14 三层防线之一
    _EXCLUDED_FIELD_NAMES: ClassVar[frozenset[str]] = frozenset(
        re.sub(r"[^a-z0-9]", "", name)
        for name in (
            "token_count",
            "token_type",
            "tokenizer",
            "max_tokens",
            "secret_name",
            "secret_id",
            "secret_arn",
            "key_id",
            "public_key",
            "has_password",
            "authorization_url",
            # nonce / salt / IV 族：密码学意义上是公开参数（nonce 本就是 "number used once"，salt 与 IV 随密文一同存储），不是凭据。
            # 实测其值与真实 token 在熵/形状上完全同形，故检测器无法靠取值区分，只能靠字段名保留。
            "nonce",
            "salt",
            "iv",
            "initialization_vector",
            "initialisation_vector",
        )
    )

    # 严格字段名的归一化形式（去分隔符 + 小写）
    _NORMALIZED_STRICT: ClassVar[frozenset[str]] = frozenset(
        re.sub(r"[^a-z0-9]", "", name.lower()) for name in _STRICT_FIELD_NAMES
    )

    # 路径 A 的后缀族 —— `<前缀>password` 形态的凭据字段名。
    # `password` 不以 key/token/secret 结尾，进不了路径 B；`apppassword` / `dbpassword`
    # 又都不在 _NORMALIZED_STRICT，故被 scan() 的 else 分支整体跳过（实测端到端原样泄露）。
    #
    # 用**前缀白名单**而非通配 `*password` 后缀：仓库语料（排除 .venv）出现
    # is_/has_/hide_/force_/get_/missing_/default_/hashed_/encrypted_/certificate_ 等
    # **非凭据**形态（布尔标志 / 取值函数 / 已加密摘要），通配会把它们一并当凭据脱敏。
    # 白名单只随显式新增而扩大，维护方向与安全方向一致。
    _PASSWORD_PREFIXES: ClassVar[frozenset[str]] = frozenset(
        (
            "app",
            "db",
            "database",
            "redis",
            "mysql",
            "postgres",
            "mongo",
            "rabbitmq",
            "proxy",
            "ssl",
            "client",
            "user",
            "key",
            "auth",
            "sign",
            "vault",
            "admin",
            "service",
            "api",
            "master",
        )
    )

    # key=value / key: value / "key": "value" 赋值形态；
    # value 终止于引号 / 空白 / 逗号 /分号 / 大括号 / & / #。
    # - key 前缀锚定 (?<![A-Za-z0-9_-]) + 捕获组外的 [0-9]* ：
    #   ① quadratic 的真实根因：原锚定 (?<![A-Za-z_]) 只禁止字母 / 下划线，于是 "1a1a1a..." 中
    #      每个 a 的前一字符都是数字 1 —— 断言通过，引擎在每个 a 处重启；随后 key 组
    #      [A-Za-z0-9_-]* 是贪心量词，从该 a 起吞掉余下整段再回溯失败。
    #      O(n) 个重启点 × O(n) 回溯 = O(n²)。实测 "1a"*n + ":" 严格 4 倍倍增
    #      （n=2000 0.27s / 4000 1.06s / 8000 4.21s / 16000 16.39s / 32000 64.46s）。
    #   ② 断言必须禁止数字与连字符：真正的 token 边界是 [A-Za-z0-9_-] 之外。
    #      禁止数字后，1 与 a 之间不再是「合法起点」，重启次数退化为 O(词数)，恢复线性。
    #   ③ 但仅有 ② 会让 1password= 完全不匹配（推进到 p 时前字符 1 ∈ [0-9]，断言失败），
    #      故必须在断言之后显式吃掉 [0-9]*。
    #   ④ [0-9]* 必须在**捕获组之外**：若并入捕获组（如 ([0-9]*[A-Za-z_]...)），
    #      1password 会归一化为 "1password"，既不在 _NORMALIZED_STRICT 也不以 key/token/secret 结尾，
    #      5 个数字前缀键用例会全部从「命中」退化为「漏报」。捕获组内的数字前缀键仍是纯字母开头的键。
    #   ⑤ 不能用 \b 代替：\b 在「数字后接字母」处无边界（1 与 p 同为 \w），会静默丢弃数字前缀键。
    #      两者机理不同、并不等价（\b 在 1→p 处根本不会重启）。
    # - value 组排除 & / #：query string 中它们才是真正的 pair 分隔符， 否则 ?access_token=x&next=/a 的值会吞掉 next=/a
    #   assignment 的 span 与 url detector 命中重叠后按 priority(85>70) 取 url 元数据， 整个 union 被当作一个 url_credential 替换
    #   既破坏无关参数保真，又在 LOG/EXPORT 的 head6/tail4 掩码下泄露 ≥32 字符 secret 的首尾
    # - value 组仍保留 ``{`` 终止符：
    #   ${VAR} / os.getenv(...) 依赖它把值截断成 $ / os.getenv(，再由 _VAR_REF_RE 的后续上下文识别为变量引用
    # - 分隔符 (: 族)：``:=`` 分支必须写在 ``[:=]`` **之前**。
    #   原写法 ``\s*[:=]\s*`` 在 ``password := hunter2hunter2`` 上先匹配 ``:``，
    #   随后值组 ``[^"'\s,;{}&#]+`` 把 ``=`` 吞成值 → 只遮掉一个 ``=``，
    #   真实密码 ``hunter2hunter2`` 明文存活（P012 真泄露）。
    #   改为 alternation 且 ``:=`` 前置，引擎优先整体吃掉两字符。
    #   ``=`` 与 ``:`` 的既有行为不变：``password==hunter2`` 仍在第一个 ``=`` 处匹配、
    #   值仍是 ``=hunter2``（P010/P011 用例钉住）；``password: x`` / ``"k": "v"`` 不变。
    #   注意 alternation 顺序是**语义必需**而非风格：``[=:]`` 在前会重新退化为只吃 ``:``。
    _KEY_VALUE_RE: ClassVar[re.Pattern] = re.compile(
        r"""(?i)(?<![A-Za-z0-9_-])[0-9]*([A-Za-z_][A-Za-z0-9_-]*)\s*["']?\s*(?::=|[=:])\s*["']?([^"'\s,;{}&#]+)["']?""",
    )

    # f-string 截断形态：`password=f"{x}"` / `password=f'{x}'` / `password=f{x}` 的值被 `{`
    # （或 `{` 前的引号）截断成单个 `f` / `F`，值结束后的顺延片段以可选引号 + `{` 起始。
    # 这类 `f` 是 Python f-string 前缀而非凭据，必须豁免 —— 否则会被 strict 路径当作真实 secret 脱敏。
    # 注意：只豁免**恰好一个 f/F** 的值。通用形态 `^[A-Za-z_]+["']?\{` 会误伤
    # `password=abc{def}`（值 `abc` 是真实短凭据，`{` 只是字面量），故不用。
    _FSTRING_PREFIX_RE: ClassVar[re.Pattern] = re.compile(r"^[fF]['\"]?\Z")

    # 变量引用形状：$X / ${X} / os.getenv(...) / process.env.X
    # 注意：${VAR} / os.getenv('X') 这两类形态会被 _KEY_VALUE_RE 的值边界截断
    # { 是值终止符 → $ / os.getenv；引号也是值终止符 → os.getenv，故变量引用检查必须能作用于「截断后的值 + 其后的原始文本」
    #
    # 花括号必须**成对**：原写法 ^\$\{?[A-Za-z_][A-Za-z0-9_]*\}? 两个花括号各自独立 optional，
    # 于是 ${FOO 与 $FOO} 都被判为合法变量引用（畸形接受），会让形似变量引用的畸形值整体豁免脱敏。
    # 仅把花括号打包成 (?:\{...\})? 仍不够 —— 见下方「尾部必选 + 终止边界」说明。
    #
    # f-string 花括号（^{x}）规则**已删除** —— 它不可达：`{` 在 _KEY_VALUE_RE 的值排除类
    # [^"'\s,;{}&#] 中，故 password={x} 根本不产生匹配；password=f"{x}" 的值被 `{` 前的 `"` 截断为 `f`，
    # 而 `f` 不是变量引用形状。f-string 的识别不在本 detector 职责内。
    #
    # 全部 alternative 必须锚定：os\.getenv\s*\( / process\.env
    # 原先未锚定，导致「值之后 64 字符内出现任意 process.env.」都会把前面的**真实 secret**误判为变量引用而跳过
    # 锚定到两串拼接起点后，只有当变量引用形状出现在值**起始处**（真实 `${X}` / `os.getenv(` 值）时才成立
    # `os\.getenv\s*\(` 与 `process\.env\.` 均为定长前缀字面量 —— 无回溯、无 ReDoS。
    #
    # $-族的变量名 / 成对花括号必须完整，不能回溯为裸 $ 或仅接受引用前缀。
    # _is_variable_reference 收到「值 + 顺延上下文」，故引用后只检查终止边界，不能要求覆盖整串：
    # 否则换行、后续文字或闭合引号会让合法引用失去豁免。
    # 终止符沿用值排除类中的空白、引号、,;&#，但不包含花括号；
    # $FOO} / ${FOO}} 等畸形引用及 $FOO-tail / ${FOO}tail 等字面量拼接仍不豁免。
    # os.getenv( / os.environ[ / process.env. 三族**保持前缀锚定**：被 `(` / `[` 截断的值
    #   拼接后是 "os.getenv(('X')" / "os.environ['X']"，未闭合的括号正是其应有形态，
    #   不能要求整串匹配。
    #   `os.environ[` 与 `os.getenv(` 同属「从运行环境取值」的既有豁免族 ——
    #   原先只列了 os.getenv，导致 password=os.environ['DB_PASSWORD'] 被当真实凭据脱敏，
    #   破坏源码配置模板（与 $-族 / os.getenv 的豁免意图不一致）。
    _VAR_REF_RE: ClassVar[re.Pattern] = re.compile(
        r"""^\$\{[A-Za-z_][A-Za-z0-9_]*\}(?=[\s"',;&#]|\Z)"""
        r"""|^\$[A-Za-z_][A-Za-z0-9_]*(?=[\s"',;&#]|\Z)"""
        r"|^os\.getenv\s*\("
        r"|^os\.environ\s*\["
        r"|^process\.env\."
    )

    # 廉价预筛选：文本中须出现赋值分隔符（`=` / `:` 是 assignment 的必要子串）
    _HINT_RE: ClassVar[re.Pattern] = re.compile(r"[:=]")

    # header scheme 名：作为「authorization」字段的值时说明这是 header 结构，
    # 应由 headers detector 处理而非 assignment（否则会把 header 名替换掉）
    _HEADER_SCHEMES: ClassVar[frozenset[str]] = frozenset({"basic", "bearer", "digest", "negotiate"})

    @staticmethod
    def _split_var_ref(value: str, context: str = "") -> str:
        """把「值 + 其后片段」拼成变量引用形状匹配所需的文本。

        语义（缺陷回归防线）：

        1. ``context`` 是 ``value`` 在原文本中**结束之后**的顺延片段
           （:meth:`scan` 取 ``text[match.end(2) : match.end(2) + 64]``），
           不是与值重叠的窗口。因此不存在「值长于 64 字符窗口、窗口在值中途截断」的情形 ——
           原先的 ``len(value) <= len(context)`` 判据建立在「重叠窗口」这一错误前提上，
           并且会**误杀跨截断的合法变量引用**。故只要 ``context`` 非空即拼接。
        2. 拼接不引入假阳性：:data:`_VAR_REF_RE` 的全部 alternative 都以 ``^`` 锚定在**值起点**，
           只有当值本身以变量引用形态起始时才成立；值之后的无关 token（如 ``{Y}``）永远落在
           ``^`` 之后，不可能被匹配到。
        3. ``"$" + "{DB_PASSWORD}"`` → ``"${DB_PASSWORD}"`` 依赖恒拼接，
           这是既有的正确护栏（值被 ``{`` 边界截断成 ``$``，跨边界形态靠拼接还原）。

        Args:
            value: 值本体（可能已被 `_KEY_VALUE_RE` 的边界截断）
            context: ``value`` 在原文本中的后续片段（通常取 value 之后若干字符）

        Returns:
            供 :data:`_VAR_REF_RE` 匹配的文本。
        """
        if context:
            return value + context
        return value

    @staticmethod
    def _is_variable_reference(value: str, context: str = "") -> bool:
        """判断值是否为源码变量引用（``$X`` / ``${X}`` / ``os.getenv(...)`` / ``process.env.X``）。

        Args:
            value: 值本体（可能已被 `_KEY_VALUE_RE` 的边界截断）。
            context: ``value`` 在原文本中**结束之后**的顺延片段（通常取 value 之后若干字符）。
                ``${DB_PASSWORD}`` 会被截断成 ``$``、
                ``os.getenv('X')`` 会被截断成 ``os.getenv(``，
                故必须在「值 + 后续片段」拼接文本上做形状匹配。
        """
        return bool(AssignmentDetector._VAR_REF_RE.match(AssignmentDetector._split_var_ref(value, context)))

    @staticmethod
    def _is_strict_field(normalized: str) -> bool:
        """归一化字段名是否属路径 A（严格凭据字段）。

        两类命中：

        1. ``_NORMALIZED_STRICT`` 直接成员（``password`` / ``secret`` / ``api_key`` …）。
        2. ``<前缀>password`` 形态且前缀在白名单内（``apppassword`` / ``dbpassword`` …）。
           支持两段前缀（``vaultdbpassword`` ← ``vault_db_password``）。

        短路顺序保证零额外开销：现有成员在第一次 ``in`` 即返回；
        非 ``password`` 结尾的字段只多一次 ``str.endswith``（~10ns）。

        Args:
            normalized: 已归一化（去分隔符 + 小写）的字段名。
        """
        if normalized in AssignmentDetector._NORMALIZED_STRICT:
            return True
        if not normalized.endswith("password"):
            return False
        prefix = normalized[: -len("password")]
        if prefix in AssignmentDetector._PASSWORD_PREFIXES:
            return True
        # 两段前缀：vaultdb / rabbitmq 之类本身已在白名单；此处覆盖 <wl><wl> 组合
        return any(
            prefix.startswith(head) and prefix[len(head) :] in AssignmentDetector._PASSWORD_PREFIXES
            for head in AssignmentDetector._PASSWORD_PREFIXES
            if prefix != head
        )

    @staticmethod
    def _is_fstring_prefix(value: str, context: str = "") -> bool:
        """判断值是否为被 `{` 边界截断的 Python f-string 前缀（``f"{x}"`` → 值 ``f``）。

        `{` 是 ``_KEY_VALUE_RE`` 的值终止符，故 ``password=f"{x}"`` 的值被截断成 ``f``；
        该 ``f`` 是 f-string 前缀而非凭据，若走 strict 路径会被整体脱敏（P2c）。

        判据要求**值恰为单个 f/F**（大小写均可）且其后紧跟「可选引号 + `{`」。
        不使用通用形态 ``^[A-Za-z_]+["']?\\{`` —— 它会误伤 ``password=abc{def}``
        （值 ``abc`` 是真实短凭据，``{`` 只是字面量）。

        Args:
            value: 值本体（可能已被 `_KEY_VALUE_RE` 的边界截断）。
            context: ``value`` 在原文本中**结束之后**的顺延片段。
        """
        if not AssignmentDetector._FSTRING_PREFIX_RE.match(value):
            return False
        return context[:1] == "{" or (context[:1] in ('"', "'") and context[1:2] == "{")

    @staticmethod
    def _score_ambiguous(key: str, value: str, context: str = "") -> int:
        """歧义字段的上下文评分（DESIGN §3.5，分值逐条照抄）。"""
        score = 0
        if len(value) >= 24:
            score += 2
        if shannon_entropy(value) >= 4.2:
            score += 2
        if char_class_count(value) >= 3:
            score += 1
        if _normalize_field_name(key).endswith(AssignmentDetector._AMBIGUOUS_SUFFIXES):
            score += 2

        # 减分项：形状判据（不依赖熵）
        if is_uuid_like(value) or is_fixed_hex(value):
            score -= 4
        if AssignmentDetector._is_variable_reference(value, context):
            score -= 3
        return score

    def could_match(self, text: str) -> bool:
        """廉价预筛选：文本含赋值分隔符 ``=`` 或 ``:`` 即可能命中。"""
        if not isinstance(text, str) or not text:
            return False
        return bool(self._HINT_RE.search(text))

    def scan(self, text: str) -> list[Finding]:
        if not self.could_match(text):
            return []

        findings: list[Finding] = []
        for match in self._KEY_VALUE_RE.finditer(text):
            key, value = match.group(1), match.group(2)
            if not value:
                continue

            normalized = _normalize_field_name(key)
            # 负例排除集先于评分短路（T-06-14）
            if normalized in self._EXCLUDED_FIELD_NAMES:
                continue

            # 值之后 64 字符作为变量引用判定上下文（应对 `${X}` / `os.getenv(` 被值边界截断的情形）；
            # context 非空即拼接 —— 拼接起点受 _VAR_REF_RE 的 ^ 锚定保护，不会伪造变量引用形状
            context = text[match.end(2) : match.end(2) + self._VAR_REF_CONTEXT]

            # 占位符短路：值本身是「未填 / 已遮蔽」标记时，无论 key 多像凭据都不替换。
            # 放在 strict 判定**之前**，因为 strict 是「命中即脱敏」，不经过评分，
            # 故减分项（-3 变量引用）对路径 A 无效 —— 占位符必须在此显式豁免。
            # 单条覆盖：`password=null` / `password=<REDACTED>` / `password=!vault` / `password={{ vault_db_password }}`
            if is_placeholder_value(value):
                continue

            if self._is_strict_field(normalized):
                # 路径 A：严格字段，但变量引用豁免（源码配置模板不可被破坏）。
                # 定长 hex 形状豁免**不适用于 strict 路径**：password=01234567 这类是高置信字段的
                # 真实凭据，形状豁免会把它们整体漏掉（实测 APP_PASSWORD=0123456789abcdef 原样泄露）。
                # 纯 hex 形状豁免保留在歧义路径（_score_ambiguous 的 -4），
                # 那里字段名证据弱、GPG key ID / fingerprint 是主要误报面。
                if self._is_variable_reference(value, context):
                    continue
                # f-string 截断豁免：值恰为 `f` / `F` 且其后紧跟（可选引号 +）`{` 时，
                # 这是 Python f-string 前缀 `f"{x}"` 被 `{` 边界截断的产物，不是凭据。
                if self._is_fstring_prefix(value, context):
                    continue
                # header 结构豁免：`Authorization: Basic ...` 的值是 scheme，由 headers detector 负责真正的凭据；
                # assignment 不应抢答（否则会把 header 名 `Authorization` 本身替换掉）。
                # 只列 `authorization`：`Proxy-Authorization` 归一化后**不在** _NORMALIZED_STRICT，
                # 本分支对其永不可达（原先元组里的第二个 arm 因此是死代码，已删除）。
                # 该 header 由 HeadersDetector._HEADER_NAMES 处理（authorization_header, priority 90 > assignment 70）。
                # 不可把 proxy 形态加进 _STRICT_FIELD_NAMES —— 那会让 assignment 与 headers 抢答，
                # 且 `Proxy-Authorization: Bearer xxx` 的值是 scheme，会把 header 名本身替换掉。
                if normalized == "authorization" and value.lower() in self._HEADER_SCHEMES:
                    continue
                kind = "credential"
            elif (
                normalized.endswith(self._AMBIGUOUS_SUFFIXES)
                and self._score_ambiguous(key, value, context) >= self._SCORE_THRESHOLD
            ):
                # 路径 B：歧义字段，评分达标才触发；kind 取归一化字段名（如 gpg_key）
                kind = normalized or "credential"
            else:
                continue

            findings.append(
                Finding(
                    start=match.start(2),
                    end=match.end(2),
                    rule_id=f"assignment.{normalized}",
                    kind=kind,
                    confidence="medium",
                    priority=self._ASSIGNMENT_PRIORITY,
                )
            )
        return findings


class CookieDetector:
    """Cookie / Set-Cookie 敏感名检测器（只替换敏感 cookie 的值）

    匹配 Cookie: / Set-Cookie: 头（大小写不敏感），按 `;` 切 pair，只对 cookie 名归一化后落在敏感集内的 pair 替换其值
    属性 pair（Secure / HttpOnly / SameSite / Path / Domain / Max-Age / Expires）一律不替换且保真。

    关键：按 `;` 切分而非按 `,`**:
        Set-Cookie 的 `Expires=Wed, 21 Oct 2026 07:28:00 GMT` 里含逗号
        若按 `,` 切会把它拆成两个半截 pair，破坏解析, 故 `Expires` 必须作为完整的一个属性 pair 处理。

    finding span 只覆盖 cookie 值本体（不含名、不含 `=`），替换后 ``session=[REDACTED:cookie]`` 保留 cookie 名。

    `kind` = `cookie`，`confidence="high"`，`priority=85`
    """

    rule_id: str = "cookie"

    # cookie 证据强度与 url 同级（85）：结构化但弱于 header/dsn 的完整协议形态
    _COOKIE_PRIORITY: ClassVar[int] = 85

    # 敏感 cookie 名（归一化后匹配）
    _SENSITIVE_NAMES: ClassVar[frozenset[str]] = frozenset(
        _normalize_field_name(name)
        for name in (
            "session",
            "sessionid",
            "session_id",
            "sid",
            "auth",
            "auth_token",
            "authtoken",
            "token",
            "access_token",
            "jwt",
            "csrf",
            "csrftoken",
            "xsrf",
            "xsrf_token",
        )
    )

    # 匹配 `Cookie:` / `Set-Cookie:` 到行尾（按 `;` 切分在代码中进行，
    # 避免 `Expires` 的逗号破坏解析）。
    #
    # 头名前缀边界为「行首 或 非标识符字符」：必须排除「字母 / 数字 / 下划线 / 连字符」，
    # 使 `mycookie` / `sessionCookie` 这类更长标识符不被误判为头名（负例），
    # 同时让序列化形态的定界符（引号 `"` `'`、方括号 `[`、花括号 `{`、尖括号 `<`、
    # 括号 `(`、等号 `=`、冒号 `:`、逗号 `,`、竖线 `|`）都能作为合法前缀 ——
    # 原先的 `(?:^|[\s;])` 只认空白与分号，导致 `"Cookie: ...` / `[Cookie: ...` /
    # `foo=Cookie: ...` 等形态静默漏报（安全缺陷）。
    # 注意：value 组仍为 `[^\r\n]+`（取到行尾），`Expires=Wed, 21 Oct ...` 依赖它不被逗号截断。
    _COOKIE_HEADER_RE: ClassVar[re.Pattern] = re.compile(
        r"(?i)(?:^|[^\w-])\s*Set-Cookie\s*:\s*([^\r\n]+)|(?:^|[^\w-])\s*Cookie\s*:\s*([^\r\n]+)"
    )

    # 单个 pair：`name=value`，**行首锚定**，值在「空白 / 分号 / 尾随定界符」处终止。
    #
    # 与旧的 `^\s*(name)\s*=\s*(value)\s*$`（要求整段恰好是一个 pair）的关键差别：
    # 旧式遇到尾随文本就整段不匹配，导致真实文本里的合法 cookie 被静默漏报：
    #   `Cookie: session=abc123 Cookie: token=xyz`   （同行第二个头）
    #   `Cookie: session=abc123\tCookie: token=xyz`  （制表符分隔）
    #   `Cookie: sid=abc123, token=xyz`              （逗号分隔）
    #   `curl -H Cookie: session=abc123 https://x`   （payload 之后的尾随文本）
    # 新式只要求 **段首** 是 `name=value`，值读到哪里由终止规则决定。
    #
    # 终止规则（RFC 6265 §4.1.1：cookie-value 不得含空白、双引号、逗号、分号）：
    # - 空白 / 分号 → 终止（故 `session=abc 123` 只取 `abc`）
    # - 逗号与 `"` `'` `` ` `` `>` `)` `]` `}` → 终止（尾随定界符不属于值）
    # - 引号包裹的值（`"v"` / `'v'`）按对解析，**span 只覆盖内层 v**，引号保真
    #
    # 注意 value 组用命名组：在 `(?:...|...)` 内 `\1` 会指回外层捕获组（name），
    # 并非引号本身 —— 必须用 `(?P=q)` 命名反向引用，否则引号分支永不匹配。
    _PAIR_RE: ClassVar[re.Pattern] = re.compile(
        r"""^\s*(?P<name>[^=;\s]+)\s*=\s*
            (?:
                (?P<q>["'])(?P<qv>[^;\s]*)(?P=q)      # 引号包裹：span 只取内层
              | (?P<bv>[^;\s"'`,>)\]}]+)              # 裸值：遇空白/分号/尾随定界符终止
            )""",
        re.VERBOSE,
    )

    def could_match(self, text: str) -> bool:
        """廉价预筛选：文本含 ``cookie``（大小写不敏感）。"""
        if not isinstance(text, str) or not text:
            return False
        return "cookie" in text.lower()

    def scan(self, text: str) -> list[Finding]:
        if not self.could_match(text):
            return []

        findings: list[Finding] = []
        for header in self._COOKIE_HEADER_RE.finditer(text):
            payload = header.group(1) if header.group(1) is not None else header.group(2)
            if not payload:
                continue
            base = header.start(1) if header.group(1) is not None else header.start(2)
            findings.extend(self._scan_pairs(payload, base))

        return findings

    def _scan_pairs(self, payload: str, base: int) -> list[Finding]:
        """按 ``;`` 切 pair，只对敏感 cookie 名的值产出 finding。

        Args:
            payload: header 值部分（``Cookie:`` 之后的整段）。
            base: ``payload`` 在原文本中的起始偏移。
        """
        findings: list[Finding] = []
        # 记录每个 pair 在 payload 内的偏移，用于精确 span
        offset = 0
        for segment in payload.split(";"):
            segment_start = offset
            offset += len(segment) + 1  # +1 为分号

            pair = self._PAIR_RE.match(segment)
            if pair is None:
                continue
            name = pair.group("name")
            # 引号包裹取内层（qv），裸值取 bv；两者恰好一个非 None
            quoted_value = pair.group("qv")
            value = quoted_value if quoted_value is not None else pair.group("bv")
            if not value:
                continue
            if _normalize_field_name(name) not in self._SENSITIVE_NAMES:
                continue

            # span 只覆盖值本体：引号包裹时跳过开引号（qv 的起点），引号保真。
            value_group = "qv" if quoted_value is not None else "bv"
            value_start = base + segment_start + pair.start(value_group)
            findings.append(
                Finding(
                    start=value_start,
                    end=value_start + len(value),
                    rule_id=self.rule_id,
                    kind="cookie",
                    confidence="high",
                    priority=self._COOKIE_PRIORITY,
                )
            )
        return findings


class DsnDetector:
    """DSN 连接串 password 检测器（只替换密码段，连接串结构保真）。

    DSN 连接串检测器（解 T-06-11 / 缺陷 D9）。

    覆盖 ``scheme://[user[:password]@]host[:port][/db]`` 形态：
    ``postgresql`` / ``postgres`` / ``mysql`` / ``mariadb`` / ``mongodb`` / ``mongodb+srv`` /
    ``redis`` / ``rediss`` / ``amqp`` / ``amqps``。``redis://:pw@host/0`` 这种**无 user**
    的形态（userinfo 直接以冒号开头）也覆盖。

    finding span **只覆盖 password 段** —— scheme / user / host / port / db 全部保真，
    故替换后连接串仍可用（预签名 / 运维命令场景不被破坏）。

    **源码模板例外（T-06-17）**：password 为 ``${VAR}`` / ``$VAR`` / ``{var}`` 形状时不命中，
    避免把配置模板当成真实 secret 破坏。

    **JDBC 属性串不在本 detector**：``jdbc:sqlserver://h;Password=x`` 这类形态
    既无 ``user:pass@`` userinfo 也无受支持 scheme，由 :class:`DsnJdbcDetector` 单独覆盖
    （须``jdbc:`` 前缀作为上下文，T-06-17 的同类要求）。

    **ReDoS 防护（T-06-12）**：正则从**强制** ``://`` 边界起匹配，
    password 段用**有界**量词（``[^@\\s/]{1,512}``），
    **禁止**惰性通配（lazy wildcard）与无界回溯 ——
    ref.md §4.6 记录过 320KB 连续字母数字输入下 55 秒的真实事故。

    ``kind`` = ``dsn_password``，``confidence="high"``，``priority=90``。
    """

    rule_id: str = "dsn"

    # DSN 结构证据强于厂商前缀（vendor=80）
    _DSN_PRIORITY: ClassVar[int] = 90

    # 支持的 scheme（强制出现在 `://` 之前）
    _SCHEMES: ClassVar[tuple[str, ...]] = (
        "postgresql",
        "postgres",
        "mysql",
        "mariadb",
        "mongodb+srv",
        "mongodb",
        "rediss",
        "redis",
        "amqps",
        "amqp",
    )

    # userinfo 形态：`user:password@` 或 `:password@`（无 user）。password 用有界量词（T-06-12）。
    # 注意：scheme 用 `re.escape` 保证 `mongodb+srv` 的 `+` 是字面量而非量词。
    _DSN_RE: ClassVar[re.Pattern] = re.compile(
        r"(?i)(?<!\w)(" + "|".join(re.escape(s) for s in _SCHEMES) + r")://([^:@/\s]{0,128}):([^@\s/]{1,512})@",
    )

    # 变量引用形状：`${VAR}` / `$VAR` / `{var}`（源码模板例外）
    _VAR_REF_RE: ClassVar[re.Pattern] = re.compile(r"^\$\{?[A-Za-z_][A-Za-z0-9_]*\}?$|^\{[A-Za-z_][A-Za-z0-9_]*\}$")

    # 廉价预筛选：含 `://` 且含某个 scheme 字面量
    _HINT_RE: ClassVar[re.Pattern] = re.compile(r"://", re.IGNORECASE)

    # 已删除 `_JDBC_PASSWORD_RE` / `_JDBC_HINT_RE`（原 `(?i)\bPassword\s*=\s*([^\s;\"']{1,512})`）：
    # 该正则**不含任何 JDBC 上下文**（无 `jdbc:`、无分号属性串要求），
    # 实际等价于「`Password=` 后跟任意非空白」—— 与普通配置赋值完全同形，
    # 因而把 `password=null` / `********` / `<REDACTED>` / `!vault` 等占位符
    # 一并当密码脱敏（S106/S107/S109/S111）。且其 priority=90 高于 assignment 的 70，
    # 会**抢答**并把 kind 标成 `dsn_password`，让「DSN 检测在工作」成为假象。
    #
    # 删除依据（2026-09-15 实测）：全集 128 条中，本正则命中的 4 条正例
    # （S090/S092/S095/S128）**全部**是裸 `password=`，已被 ``AssignmentDetector``
    # 的 strict 路径覆盖 —— 删除后正例零损失；负例中 4 条输出变化（kind 回归
    # `credential`、S106 恢复原样）。真 JDBC 连接串（`jdbc:mysql://...`）仍由
    # 上方 ``_DSN_RE`` 按 scheme 覆盖。

    @staticmethod
    def _is_variable_reference(value: str) -> bool:
        """判断 DSN password 是否为源码变量引用（配置模板例外，T-06-17）。"""
        return bool(DsnDetector._VAR_REF_RE.match(value))

    def could_match(self, text: str) -> bool:
        """廉价预筛选：含 ``://`` 与某个 scheme 字面量。

        `password=` 不再参与预筛选 —— 它属于 ``AssignmentDetector`` 的职责，
        本 detector 只认带 scheme 的 DSN 形态。
        """
        if not isinstance(text, str) or not text:
            return False
        lowered = text.lower()
        return bool(self._HINT_RE.search(text) and any(scheme in lowered for scheme in self._SCHEMES))

    def scan(self, text: str) -> list[Finding]:
        # 预筛选所有权在本方法（T-vq0）：调用方无需（也不再）先行 could_match 判定，
        # 保证「新 detector 忘记接入预筛选」这一缺陷 3 的根因不再复现。
        if not self.could_match(text):
            return []

        findings: list[Finding] = []

        for match in self._DSN_RE.finditer(text):
            password = match.group(3)
            if not password or self._is_variable_reference(password) or is_placeholder_value(password):
                continue
            findings.append(
                Finding(
                    start=match.start(3),
                    end=match.end(3),
                    rule_id=self.rule_id,
                    kind="dsn_password",
                    confidence="high",
                    priority=self._DSN_PRIORITY,
                )
            )

        return findings


class DsnJdbcDetector(DsnDetector):
    """JDBC 连续属性串的 password 检测器，共用 DSN 的引用豁免与优先级。

    从大小写不敏感的 ``jdbc:`` 起点，先读取连接地址，再逐段读取 ``;key=value``。
    属性名允许 ``User Id`` 等水平空格；正文、引号、换行或非属性内容结束当前串，
    不会把同一行中无关的 ``Password=`` 误认成 JDBC 属性。

    值仍为单 token，密码 span 最多 512 字符，不解析引号或大括号的转义语法。
    ``${VAR}`` / ``$VAR`` / ``{var}`` 和占位符不命中（T-06-17）。
    游标始终前移，不为每个密码回扫或复制 JDBC 前缀（T-06-12）。
    """

    rule_id: str = "dsn.jdbc"

    _HINT_RE: ClassVar[re.Pattern] = re.compile(r"(?i)(?<!\w)jdbc:")
    _BASE_RE: ClassVar[re.Pattern] = re.compile(r"[^\s;\"']+")
    # 只在游标处读取分号属性；空属性也消费分号，避免停滞。
    _ATTR_RE: ClassVar[re.Pattern] = re.compile(r"[ \t]*;[ \t]*(?:([A-Za-z_][A-Za-z0-9_. \t-]*)=[ \t]*([^\s;\"']*))?")

    def could_match(self, text: str) -> bool:
        """廉价预筛选：文本含独立的 ``jdbc:`` 起点。"""
        if not isinstance(text, str) or not text:
            return False
        return bool(self._HINT_RE.search(text))

    def scan(self, text: str) -> list[Finding]:
        if not self.could_match(text):
            return []

        findings: list[Finding] = []
        cursor = 0
        while marker := self._HINT_RE.search(text, cursor):
            cursor = marker.end()
            base = self._BASE_RE.match(text, cursor)
            if base is None:
                continue
            cursor = base.end()
            while attr := self._ATTR_RE.match(text, cursor):
                cursor = attr.end()
                key = attr.group(1)
                if key is None or key.strip().lower() != "password":
                    continue
                start = attr.start(2)
                end = min(attr.end(2), start + 512)
                password = text[start:end]
                if not password or self._is_variable_reference(password) or is_placeholder_value(password):
                    continue
                findings.append(
                    Finding(
                        start=start,
                        end=end,
                        rule_id=self.rule_id,
                        kind="dsn_password",
                        confidence="high",
                        priority=self._DSN_PRIORITY,
                    )
                )
        return findings


@dataclass(frozen=True)
class EntropyDetector:
    """裸高熵兜底（最低优先级，仅在无结构化证据时启用）。

    Args:
        min_length: 候选最小长度（默认 32，来自 SecurityRedactionSettings）。
        alnum_threshold: alnum/Base64URL 阈值（默认 4.2）。
        base64_threshold: 标准 Base64 阈值（固定 4.5）。
    """

    # --- 类常量（ClassVar 强制：frozen dataclass 中「有注解无 ClassVar」会静默变成字段）
    # ---裸熵是最后兜底 —— 全 detector 最低优先级（registered 100 > pem 95 > ... > assignment 70）
    _ENTROPY_PRIORITY: ClassVar[int] = 50

    # 默认参数（与 SecurityRedactionSettings 默认值对齐；调用方可覆盖）
    _DEFAULT_MIN_LENGTH: ClassVar[int] = 32
    _DEFAULT_ALNUM_THRESHOLD: ClassVar[float] = 4.2
    # 标准 Base64 字符集更大（64 符号 vs 62），同长度下熵更高，故阈值更高（DESIGN D-09）
    _DEFAULT_BASE64_THRESHOLD: ClassVar[float] = 4.5

    # 候选提取：连续 base64/alnum/symbol 字符段，长度有界（T-06-21：无嵌套量词 / 无无界 * +）。
    # ``=`` 仅允许作为**尾部 padding**（base64 语义）—— 不允许出现在中部，
    # 否则``GPG_KEY=<value>`` 里的字段名会被 `=` 粘进候选，导致整个段落进 "other" 字符集而漏报。
    #
    # **扩展字符集（口令符号）**：原字符集仅 ``[A-Za-z0-9+/_-]``，导致含常见口令符号的
    # 真实口令被**切碎**成多个 < min_length 的片段 —— 每个片段都过不了长度判据，
    # 于是整条口令零命中（S054/S065 类）。密码学意义上「高熵」并不要求取值落在 base64 字母表内，
    # 把符号排除在外只是漏报来源，不是精度来源。
    #
    # 加入的是**口令常见且不与结构化文本冲突**的符号（``!$%^&*()?~``` 等）；
    # 仍为**单一字符类**（无嵌套量词），O(n) 线性性质不变。
    #
    # 两条边界（各由一次回归钉住，勿再放宽）：
    #
    # 1. **必须白名单，不能用 ``[^\s…]`` 取反**（S124 回归）：取反会把 CJK 散文整段吞成候选
    #    —— 中文句子无空白、长度 > 32、字符类达标，于是「用户名林知遥，手机…」被判为
    #    bare_secret 整段替换。秘密值是 ASCII 编码产物，白名单天然把非 ASCII 排除在外，
    #    既修召回也不伤中文正文。
    # 2. **不得纳入 ``:`` ``/`` ``@`` ``#`` 等 URL/结构字符**（DSN 保真回归）：
    #    一旦纳入，``postgresql://app:S3cr3tPw@db.internal:5432/prod`` 会被熵检测器
    #    整串吞下，其 span 覆盖并**吞掉** ``dsn`` detector 的细粒度命中
    #    （合并后只留一个粗粒度 cluster），URL 的 host / port / dbname 全部丢失。
    #    结构性字符必须留给协议 detector 处理，熵兜底只认「值本体」。
    #    ``@`` 会把 ``password@host`` 粘成候选；命中后的 union 还可能使短密码的
    #    掩码区间达到 partial_min_len，触发 PARTIAL 而暴露本应整体遮蔽的密码前缀。
    #
    # 尾部 ``=`` 仍只允许 padding（base64 语义）；中部 ``=`` 是分隔符，故不进字符类。
    # 引号 / 逗号 / 分号 / 花括号 / 尖括号 / 竖线 / 反斜杠 / 空白同样是结构分隔符，
    # 计入会让候选跨越多个无关 token，把「值」与「邻近文本」粘成假候选。
    _CANDIDATE_RE: ClassVar[re.Pattern] = re.compile(
        r"""[A-Za-z0-9!$%^&*()_+\-\[\]?.~`]{32,4096}={0,2}""",
    )

    # 命中元数据
    _KIND: ClassVar[str] = "bare_secret"
    _CONFIDENCE: ClassVar[str] = "heuristic"
    # base64url 归入 base64 族（同一 rule_id 命名空间）
    _ALPHABET_BASE64_FAMILY: ClassVar[str] = "base64"

    # --- 以下 4 组私有常量自持（T-vq0）：原定义在 ``redaction.entropy``（该模块已于``260915-0dr`` 并入本文件），
    # 随本类独有的 4 个判据一并移入（值逐字复制）。
    # 共享统计 helper 的常量（_HEX_EXCLUDE_LENGTHS / _UUID_RE / _ULID_RE / _KSUID_RE）
    # 仍留在本文件上方的「共享统计工具」段。字符集分类标签（classify_alphabet 返回值）
    _ALPHABET_ALNUM: ClassVar[str] = "alnum"
    _ALPHABET_BASE64: ClassVar[str] = "base64"
    _ALPHABET_BASE64URL: ClassVar[str] = "base64url"
    # 口令符号族：候选含 base64 / base64url 字母表之外的符号（``!$%^&*`` 等）。
    # 归入 alnum 熵阈值（4.2）—— 其字母表大于 alnum 但小于标准 base64，
    # 且实测同长度下熵介于两者之间（S054 口令 ent=4.6757），4.2 判据即可覆盖。
    _ALPHABET_PASSWORD: ClassVar[str] = "password"
    _ALPHABET_OTHER: ClassVar[str] = "other"

    # 字符集成员判定
    _ALNUM_RE: ClassVar[re.Pattern] = re.compile(r"^[A-Za-z0-9]+$")
    # 标准 Base64：含 + / 或 padding =，其余为 base64 字符
    _BASE64_RE: ClassVar[re.Pattern] = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
    # Base64URL：含 - 或 _，其余为 base64url 字符
    _BASE64URL_CHARS_RE: ClassVar[re.Pattern] = re.compile(r"^[A-Za-z0-9_-]+$")
    # 口令符号族：至少含一个 alnum，且余下字符全部落在候选字母表内。
    # 要求含 alnum 是为了排除纯符号串（``!!!!…`` / ``-----`` 分隔线）——
    # 那不是口令，且其熵/字符类判据本就可疑。
    # 字母表与 :data:`_CANDIDATE_RE` 保持一致（同一次放宽的两个消费点，不可漂移）。
    _PASSWORD_CHARS_RE: ClassVar[re.Pattern] = re.compile(
        r"""^(?=.*[A-Za-z0-9])[A-Za-z0-9!$%^&*()_+\-\[\]?.~`]+$""",
    )

    # base64 容器前缀（D-08 硬排除）：命中区间落在这些前缀之后则跳过
    _BASE64_CONTAINERS: ClassVar[tuple[str, ...]] = ("data:", ";base64,")
    # 容器前缀与命中区间之间若出现「空白 / 引号」，
    # 说明命中是独立 token 而非载荷（data URI 的 MIME 段 `text/plain;base64,` 里的 `;` `/` `,` 是 URI 语法，不算分隔）
    _CONTAINER_GAP_RE: ClassVar[re.Pattern] = re.compile(r"[\s\"'`]")

    # 重复串判据：去重后字符数不超过此值即视为重复
    _REPETITION_UNIQUE_MAX: ClassVar[int] = 2

    min_length: int = _DEFAULT_MIN_LENGTH
    alnum_threshold: float = _DEFAULT_ALNUM_THRESHOLD
    base64_threshold: float = _DEFAULT_BASE64_THRESHOLD
    rule_id: str = "entropy"

    @staticmethod
    def _classify_alphabet(value: str) -> str:
        """判断候选值的字符集归属。

        Args:
            value: 待分类字符串。

        Returns:
            ``"alnum"``（仅 ``[A-Za-z0-9]``）/ ``"base64"``（含 ``+`` ``/`` 或 padding ``=``）/
            ``"base64url"``（含 ``-`` 或 ``_``）/ ``"password"``（含上述字母表之外的符号，
            但至少含一个 alnum）/ ``"other"``（不符合上述任一，如纯符号 / 空串）。
        """
        if not value:
            return EntropyDetector._ALPHABET_OTHER
        if EntropyDetector._ALNUM_RE.match(value):
            return EntropyDetector._ALPHABET_ALNUM
        if EntropyDetector._BASE64_RE.match(value) and ("+" in value or "/" in value or "=" in value):
            return EntropyDetector._ALPHABET_BASE64
        if EntropyDetector._BASE64URL_CHARS_RE.match(value) and ("-" in value or "_" in value):
            return EntropyDetector._ALPHABET_BASE64URL
        if EntropyDetector._PASSWORD_CHARS_RE.match(value):
            return EntropyDetector._ALPHABET_PASSWORD
        return EntropyDetector._ALPHABET_OTHER

    @staticmethod
    def _is_monotonic_sequence(value: str) -> bool:
        """判断是否为连续递增 / 递减序列（``abcdefg…`` / ``123456…`` / 反向）。

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

    @staticmethod
    def _is_repetition(value: str) -> bool:
        """判断是否为重复串（同一字符反复，或去重后字符极少）。

        Args:
            value: 待判断字符串。

        Returns:
            True 表示去重后字符数 <= 2（如 ``aaaa…`` / ``ababab…``）。
        """
        if len(value) < 4:
            return False
        return len(set(value)) <= EntropyDetector._REPETITION_UNIQUE_MAX

    @staticmethod
    def _is_base64_container_span(text: str, start: int, end: int) -> bool:
        """D-08 硬排除：命中区间是否落在 ``data:`` / ``;base64,`` 容器载荷内。

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
        for marker in EntropyDetector._BASE64_CONTAINERS:
            idx = text.rfind(marker, 0, start)
            if idx == -1:
                continue
            # 命中区间须在该前缀之后
            if idx + len(marker) > start:
                continue
            gap = text[idx + len(marker) : start]
            if not EntropyDetector._CONTAINER_GAP_RE.search(gap):
                return True
        return False

    def could_match(self, text: str) -> bool:
        """廉价预筛选：文本含长度 >= min_length 的 alnum/base64 段。"""
        if not isinstance(text, str):
            return False
        return bool(self._CANDIDATE_RE.search(text))

    def scan(self, text: str) -> list[Finding]:
        # 预筛选所有权在本方法（T-vq0）：调用方无需（也不再）先行 could_match 判定，
        # 保证「新 detector 忘记接入预筛选」这一缺陷 3 的根因不再复现。
        if not self.could_match(text):
            return []

        findings: list[Finding] = []
        for match in self._CANDIDATE_RE.finditer(text):
            candidate = match.group(0)
            # 占位符短路：与 assignment 共用同一判据（单条定义，两处消费）。
            # 例：`changeme`×多字符 / `IMPORTANT_PLACEHOLDER` 这类长串字符类与熵都可能达标；
            # 值本身是「未填」标记时不该被当秘密（也保证二次脱敏幂等）。
            if is_placeholder_value(candidate):
                continue
            alphabet = self._classify_if_secret(candidate, text, match.start())
            if alphabet is None:
                continue
            rule_family = self._ALPHABET_BASE64_FAMILY if alphabet == self._ALPHABET_BASE64_FAMILY else alphabet
            findings.append(
                Finding(
                    start=match.start(),
                    end=match.end(),
                    rule_id=f"entropy.bare_{rule_family}",
                    kind=self._KIND,
                    confidence=self._CONFIDENCE,
                    priority=self._ENTROPY_PRIORITY,
                )
            )
        return findings

    def _classify_if_secret(self, candidate: str, text: str, start: int) -> str | None:
        """判据（短路顺序即判据顺序）；命中返回 alphabet，否则返回 None。"""
        # 1. 长度
        if len(candidate) < self.min_length:
            return None
        # 2. 字符集：候选正则已限定「非空白 + 非结构分隔符」，故此处恒为已知字母表之一。
        #    ``"other"`` 分支保留为防御（正则与分类表若日后失配，宁可漏报不误报）。
        alphabet = self._classify_alphabet(candidate)
        if alphabet == self._ALPHABET_OTHER:
            return None
        # 3. 形状排除（形状判据，不依赖熵）
        if (
            is_uuid_like(candidate)
            or is_fixed_hex(candidate)
            or self._is_monotonic_sequence(candidate)
            or self._is_repetition(candidate)
        ):
            return None
        # 4. 字符类别
        # **已知限制（2026-09-17）**：纯 base64 行常只有 2 个字符类别（大写 + 小写，
        # ``+`` / ``/`` / ``=`` 未必出现），会被此判据拦下且**早于**熵阈值 —— 故裸熵
        # 对这类 body **不构成有效兜底**。PEM 语境下由 ``PemDetector`` 的未闭合私钥
        # 兜底负责（``iter_unterminated_secret_pem_spans``）；非 PEM 语境若出现纯
        # base64 秘密，本判据仍是漏报面（本次有意不动，避免全局召回/精度回归）。
        if char_class_count(candidate) < 3:
            return None
        # 5. 熵阈值（标准 Base64 更高）
        threshold = self.base64_threshold if alphabet == self._ALPHABET_BASE64_FAMILY else self.alnum_threshold
        if shannon_entropy(candidate) < threshold:
            return None
        # 6. data: / ;base64, 容器载荷硬排除（D-08）
        if self._is_base64_container_span(text, start, start + len(candidate)):
            return None
        # 7. PEM 非秘密块 body 硬排除（缺陷 4）：公钥 / 证书不是秘密。 PemDetector 已用 LABEL 白名单排除它们，但因其不产出 finding，
        #   裸熵兜底仍会遮掉 base64 body —— 此处以 span 位置谓词补齐（与 D-08 同构）。
        if is_pem_non_secret_span(text, start, start + len(candidate)):
            return None
        # 8. OpenSSH 公钥 body 硬排除（S035）：`ssh-ed25519 <base64>` 无 PEM 包装，
        #   第 7 步管不到，其 body 熵天然高（4.78）会被兜底遮掉 —— 公钥不是秘密。
        if is_public_key_span(text, start, start + len(candidate)):
            return None
        # 9. 公开密码学参数字段保留（S120/S121）：`nonce=` / `salt=` / `iv=` 的值
        #   与真实 token 在熵/形状上完全同形，只能靠紧邻字段名保留（用户已批准）。
        if is_non_secret_field_value(text, start):
            return None
        return alphabet


class HeadersDetector:
    """敏感 header 值检测器（覆盖 Basic 凭据，Bearer 不设最小长度）。

    敏感 header 检测器（解 T-06-10 / 缺陷 D10）。

    **关键差异（对比旧 ``redact.py:45``）**：
    1. **不设最小长度** —— ``Bearer`` 规则不再要求至少 20 个字符（RFC 6750 允许短 token）。
       旧实现只匹配 20 字符以上的 ``Bearer`` 值，短 token 完全漏检。
    2. **Basic 凭据被替换** —— 旧实现对 ``Authorization: Basic <base64>`` 无规则，
       只替换了格式名而**凭据原样泄露**。本 detector 覆盖 value 本体。
    3. **span 只覆盖 value 本体**（若存在 scheme 如 ``Bearer`` / ``Basic`` / ``Digest``，
       span 从 scheme 之后开始），替换后 ``Authorization: Bearer [REDACTED:x]``
       保留 header 名与 scheme —— 既不泄露凭据，也不破坏协议可读性。

    ``kind`` 固定 ``authorization_header``，``priority=90`` —— **高于** vendor 的 80：
    header 结构（``Name: Scheme value``）是比厂商前缀更强的证据。
    """

    rule_id: str = "headers"

    # header 结构证据强于厂商前缀（vendor=80），低于注册值精确匹配（registered=100）
    _HEADERS_PRIORITY: ClassVar[int] = 90

    # 敏感 header 名（大小写不敏感，`|` 连接）
    _HEADER_NAMES: ClassVar[tuple[str, ...]] = (
        "Authorization",
        "Proxy-Authorization",
        "X-API-Key",
        "X-Goog-API-Key",
        "API-Key",
        "X-API-Token",
        "X-Auth-Token",
        "X-Access-Token",
    )

    # 可选 scheme 仅消费同行空白，不能把当前值当 scheme 后吞入下一行 header。
    _SCHEME_RE: ClassVar[str] = r"(?:[A-Za-z][A-Za-z0-9_-]*[ \t]+)?"

    # 从行首 / 分隔符 / 引号边界起匹配；包装值的引号或尖括号不计入凭据 span。
    #
    # 前缀边界为「行首 或 非标识符字符」：必须排除「字母 / 数字 / 下划线 / 连字符」，
    # 使 `myAuthorization` / `pre-authorization` 这类更长标识符不被误判为头名（负例），
    # 同时让包装形态的定界符（左括号 `(`、方括号 `[`、花括号 `{`、尖括号 `<`、
    # 等号 `=`、竖线 `|`）都能作为合法前缀 ——
    # 原先的 `(?:^|[\s;,:\"'])` 不含 `(` 等包装字符，导致 `(Authorization: Bearer x)`
    # 这类形态静默漏报（安全缺陷）。
    _HEADER_RE: ClassVar[re.Pattern] = re.compile(
        r"(?i)(?:^|[^\w-])[ \t]*("
        + "|".join(_HEADER_NAMES)
        + r")[ \t]*:[ \t]*"
        + _SCHEME_RE
        + r"[\"'<]?([^\s\"'<>,;)]+)",
    )

    # 已知 scheme 名：用于区分裸 scheme 与同名凭据
    _KNOWN_SCHEMES: ClassVar[tuple[str, ...]] = ("Bearer", "Basic", "Digest")
    _KNOWN_SCHEMES_LOWER: ClassVar[frozenset[str]] = frozenset(s.lower() for s in _KNOWN_SCHEMES)

    # 廉价预筛选：含 `:` 且含任一 header 名片段
    _HINT_NAMES: ClassVar[tuple[str, ...]] = (
        "authorization",
        "api-key",
        "api_key",
        "x-api",
        "x-auth",
        "x-access",
        "x-goog",
    )

    def could_match(self, text: str) -> bool:
        """廉价预筛选：文本含 ``:`` 与任一敏感 header 名片段。"""
        if not isinstance(text, str) or not text:
            return False
        if ":" not in text:
            return False
        lowered = text.lower()
        return any(hint in lowered for hint in self._HINT_NAMES)

    def scan(self, text: str) -> list[Finding]:
        # 预筛选所有权在本方法（T-vq0）：调用方无需（也不再）先行 could_match 判定，
        # 保证「新 detector 忘记接入预筛选」这一缺陷 3 的根因不再复现。
        if not self.could_match(text):
            return []

        findings: list[Finding] = []
        for match in self._HEADER_RE.finditer(text):
            value = match.group(2)

            # 裸 scheme（如 `Authorization: Basic` 后即行尾）无凭据可遮，不产出 finding；
            # 但已有 `<scheme> ` 前缀时，其后同名值仍是凭据，由后续判断放行。
            if value.lower() in self._KNOWN_SCHEMES_LOWER:
                raw = text[match.start() : match.end()]
                if not any(f"{scheme} " in raw for scheme in self._KNOWN_SCHEMES):
                    continue

            findings.append(
                Finding(
                    start=match.start(2),
                    end=match.end(2),
                    rule_id=self.rule_id,
                    kind="authorization_header",
                    confidence="high",
                    priority=self._HEADERS_PRIORITY,
                )
            )
        return findings


class JwtDetector:
    """JWT 检测器（三段 JWS 与五段 JWE，均整体替换）
    根据 RFC 7516 的 Compact Serialization：
    第一段是：Protected Header
    base64url 编码以后通常：{"alg":... -> eyJ...
    JWE 第一段通常以 eyJ 开头（JSON Protected Header）, 这里仅检测 eyJ<seg> 类似的内容

    **必须整体替换**：
    只遮前三段等于泄露三段 JWS 的签名段、五段 JWE 的密文段与认证标签段都是敏感内容
    本 detector 显式枚举**三段**与**五段**两套模式，**两套都覆盖完整 token**

    新增能力（对比 vendor 的 ``eyJ...{8,}.x.x`` 三段正则）：
    - 覆盖**五段 JWE**（vendor 规则完全没有覆盖）；
    - 段用**有界**量词（``{8,4096}``），不使用模糊量词「``\\.`` 出现 2 到 4 次」（会让六段以上误命中且语义不清）

    段字符集 ``[A-Za-z0-9_-]``（base64url），段间**必须恰好**是 ``.``

    负例：单个 ``eyJ...`` 片段（无后续 ``.seg.seg``）不命中；
    普通文本中出现的 ``eyJ`` 前缀不命中

    ``kind`` = ``jwt``，``confidence="high"``，``priority=88``
    （**高于** vendor 的 80：本 detector 是结构化的、覆盖五段；vendor 的 JWT 规则只覆盖三段）。
    """

    rule_id: str = "jwt"

    # 结构化且覆盖五段 → 高于 vendor 的 JWT 规则（后者只有三段）
    _JWT_PRIORITY: ClassVar[int] = 88

    # 单段 base64url（有界量词，T-06-12）
    _SEGMENT: ClassVar[str] = r"[A-Za-z0-9_-]{8,4096}"

    # 三段 JWS：`eyJ<seg>.<seg>.<seg>`
    _JWS_RE: ClassVar[re.Pattern] = re.compile(r"eyJ" + _SEGMENT + r"\." + _SEGMENT + r"\." + _SEGMENT)

    # 五段 JWE：`eyJ<seg>.<seg>.<seg>.<seg>.<seg>`
    _JWE_RE: ClassVar[re.Pattern] = re.compile(
        r"eyJ" + _SEGMENT + r"\." + _SEGMENT + r"\." + _SEGMENT + r"\." + _SEGMENT + r"\." + _SEGMENT
    )

    def could_match(self, text: str) -> bool:
        """廉价预筛选：文本含 ``eyJ`` 即可能命中。"""
        if not isinstance(text, str) or not text:
            return False
        return "eyJ" in text

    def scan(self, text: str) -> list[Finding]:
        if not self.could_match(text):
            return []

        # 先扫五段（更长、更具体），再扫三段；两者覆盖范围由 merge_spans 处理
        findings: list[Finding] = []
        for match in self._JWE_RE.finditer(text):
            findings.append(
                Finding(
                    start=match.start(),
                    end=match.end(),
                    rule_id=f"{self.rule_id}.jwe",
                    kind="jwt",
                    confidence="high",
                    priority=self._JWT_PRIORITY,
                )
            )
        for match in self._JWS_RE.finditer(text):
            findings.append(
                Finding(
                    start=match.start(),
                    end=match.end(),
                    rule_id=f"{self.rule_id}.jws",
                    kind="jwt",
                    confidence="high",
                    priority=self._JWT_PRIORITY,
                )
            )
        return findings


class PemDetector:
    """PEM / PGP private key block 检测器（整块替换，只认 private 类 label）。

    PEM / PGP private key block 检测器。

    **整块替换**：finding span 覆盖 ``-----BEGIN ...-----`` 到 ``-----END ...-----`` 的完整 block（含 BEGIN/END 行）
    只遮 key body 等于泄露 header 信息, 只遮 header 等于泄露 key body。

    **LABEL 白名单**（必须命中）：``PRIVATE KEY`` / ``RSA PRIVATE KEY`` /
    ``EC PRIVATE KEY`` / ``OPENSSH PRIVATE KEY`` / ``ENCRYPTED PRIVATE KEY`` /
    ``PGP PRIVATE KEY BLOCK`` / ``SSH2 ENCRYPTED PRIVATE KEY``。

    **两套短横拼写均消费**：标准 5 短横 ``-----BEGIN X-----`` 与
    RFC 4716 §3 的 4 短横 ``---- BEGIN X ----``。二者共用同一
    ``iter_pem_blocks`` 解析源与 ``classify_pem_label`` 判据，
    故同 label 在两套拼写下结论一致（``scan`` 内即
    ``iter_pem_blocks(text, dash=5) + iter_pem_blocks(text, dash=4)``，
    与 ``is_pem_non_secret_span`` 逐字一致）。

    **负例显式排除**：``PUBLIC KEY`` / ``CERTIFICATE`` / ``PGP PUBLIC KEY BLOCK`` /
    ``SSH2 PUBLIC KEY`` —— 公钥与证书**不是秘密**，替换它们会破坏正常配置与信任链。
    实现方式是 **LABEL 白名单匹配**（而非「先匹配任意 BEGIN/END 再排除」），
    保证负例从一开始就不进入匹配。

    **BEGIN/END label 一致性**：用分组捕获 + **代码比对**实现，**不**使用正则 backreference。
    label 不一致（``BEGIN RSA PRIVATE KEY`` + ``END EC PRIVATE KEY``）不命中。

    **解析 / 分类定义在本模块上方**（原 ``redaction.pem``）：``iter_pem_blocks`` /
    ``classify_pem_label`` / ``normalize_label`` 的定义已随 ``260915-0dr``
    并入本文件（原为 detector 与熵侧共同依赖的干净叶子，仅 stdlib）。

    ``kind`` = ``private_key``，``confidence="high"``，``priority=95``（最高 —— private key 是不可逆泄露）。
    """

    rule_id: str = "pem"

    # private key 是不可逆泄露 → 最高优先级（高于 registered=100？否：registered 是精确值 100，
    # 此处 95 用于与其它结构 detector 区分：pem(95) > headers/dsn(90) > jwt(88) > cookie/url(85) > assignment(70)）
    _PEM_PRIORITY: ClassVar[int] = 95

    def could_match(self, text: str) -> bool:
        """廉价预筛选：文本含 ``-----BEGIN `` 或 RFC 4716 的 ``---- BEGIN ``。"""
        if not isinstance(text, str) or not text:
            return False
        return "-----BEGIN " in text or "---- BEGIN " in text

    def scan(self, text: str) -> list[Finding]:
        # 预筛选所有权在本方法（T-vq0）：调用方无需（也不再）先行 could_match 判定，
        # 保证「新 detector 忘记接入预筛选」这一缺陷 3 的根因不再复现。
        if not self.could_match(text):
            return []

        findings: list[Finding] = []
        # 共享解析源（缺陷 7）：5 短横（标准 PEM）与 4 短横（RFC 4716）两套拼写都要消费。
        # label 已在 iter_pem_blocks 内归一化，此处与熵侧共用 classify_pem_label 判定（缺陷 8）：
        # 只有 "secret" 才产 finding。``unknown`` 不产 finding —— 但**同样不会**被熵侧排除
        # （熵侧只放过 ``"non_secret"``），故 unknown 块 body 仍由裸熵兜底遮掉（fail-closed）。
        for block in iter_pem_blocks(text, dash=5) + iter_pem_blocks(text, dash=4):
            if classify_pem_label(block.label) != "secret":
                # non_secret（PUBLIC KEY / CERTIFICATE / CSR）与 unknown 均不在此产出；
                # 前者由熵侧排除保留，后者由熵侧兜底遮掉。
                continue
            # 空 body 豁免：只有 BEGIN/END 而无实质内容的「空壳」或教学省略
            # （``BEGIN X----- ... -----END X-----``）不是真实密钥，不该脱敏（S115/S116）。
            # **有**实质 body 的截断私钥仍照常整块脱敏（README 明确要求）。
            if not is_substantive_pem_body(text, block):
                continue
            findings.append(
                Finding(
                    start=block.start,
                    end=block.end,
                    rule_id=self.rule_id,
                    kind="private_key",
                    confidence="high",
                    priority=self._PEM_PRIORITY,
                )
            )

        # 未闭合私钥兜底（本次修复）：完整块之外，还要覆盖「有 BEGIN 但无**配对** END」的
        # secret 块 —— 否则纯 base64 body 会因 ``char_class_count < 3`` 躲过裸熵兜底
        # 而**明文泄露**（真实随机 RSA 私钥截断即复现）。
        # 区间右界止于下一个 BEGIN 或文末（未闭合时无法判定密钥真实边界，宁遮不漏）；
        # 元数据与上面的完整块路径**完全一致**，消费方无需区分两条路径。
        for span_start, span_end in iter_unterminated_secret_pem_spans(text):
            findings.append(
                Finding(
                    start=span_start,
                    end=span_end,
                    rule_id=self.rule_id,
                    kind="private_key",
                    confidence="high",
                    priority=self._PEM_PRIORITY,
                )
            )

        return findings


@dataclass(frozen=True)
class RegisteredValue:
    """一个显式注入的已知敏感值（**带 kind 元数据**，供 ``registered`` detector 定 rule_id）。

    此前名为 ``KnownValue``，与 :func:`redaction.operations.redact_known_values` 的
    ``Sequence[str]`` 入参**同名不同物**：本类携带 ``kind`` / ``secret_id`` 并参与
    detector span 合并，而后者是「裸值 → 单一占位符」的精确替换。改名以区分二者。

    Args:
        value: **仅驻留内存**，``repr()`` 不含该字段（``field(repr=False)`` —— T-06-02）。
        kind: 凭据类型标签，决定 finding 的 ``rule_id``（``registered:{kind}``）。
        secret_id: 非敏感内部 ID（可选，保留信息以备调用方按 id 去重）。
    """

    value: str = field(repr=False)
    kind: str = "known"
    secret_id: str = ""


@dataclass(frozen=True)
class RegisteredSecretDetector:
    """已知敏感值精确值匹配（priority=100，高于一切模式规则）。

    构造入口是 :meth:`from_values` —— 值**显式注入**，无模块级全局态。

    已知敏感值的精确匹配检测器（``priority=100``，高于一切模式规则）。

    按值的首字符分组做短路预筛选：文本中不含任何 group 首字符时直接跳过。
    组内按值长度降序，长值优先命中，避免短值先命中把长值切碎。

    **显式注入（T-urf-02）**：本 detector **不再读取任何模块级全局注册表** ——
    已知值由调用方经 :meth:`RegisteredSecretDetector.from_values` **每次构造显式传入**。
    这消除了旧的 ``redaction.registry`` 模块级可变状态（跨请求串扰面）
    并绕开平台配置路径的问题：配置 / backend 的解析留在调用方（core），
    redaction 只接收纯值列表。

    ``RegisteredValue.value`` 使用 ``field(repr=False)`` ——
    **值本身即 secret，绝不进入 ``repr()`` / 日志**
    （T-06-02 回归护栏，迁移自 TestRegisteredSecretRepr）。
    """

    # 已知值精确匹配的优先级（高于一切模式规则）
    _REGISTERED_PRIORITY: ClassVar[int] = 100

    _grouped: dict[str, tuple[RegisteredValue, ...]] = field(repr=False, default_factory=dict)
    rule_id: str = "registered"

    @classmethod
    def from_values(
        cls,
        values: Sequence[RegisteredValue | str],
        *,
        default_kind: str = "known",
    ) -> "RegisteredSecretDetector":
        """按值首字符分组构造；组内按值长度降序（长值优先命中）。

        Args:
            values: ``RegisteredValue`` 或裸 ``str`` 序列；裸 ``str`` 按 ``default_kind`` 归类。
            default_kind: 裸 ``str`` 入参使用的 kind。

        Returns:
            注入后的 detector（值序列为空 ⇒ 空 detector，``could_match`` 恒 False）。
        """
        grouped: dict[str, list[RegisteredValue]] = {}
        for item in values or ():
            entry = item if isinstance(item, RegisteredValue) else RegisteredValue(value=item, kind=default_kind)
            # 空值无法作为分组键，也无法被 ``str.find`` 有意义地定位 → 跳过（防御）。
            if not entry.value:
                continue
            grouped.setdefault(entry.value[0], []).append(entry)
        return cls(
            _grouped={
                key: tuple(sorted(items, key=lambda s: len(s.value), reverse=True)) for key, items in grouped.items()
            },
        )

    def could_match(self, text: str) -> bool:
        """任一 group 的首字符出现在文本中即 True。"""
        if not isinstance(text, str) or not text:
            return False
        return any(char in text for char in self._grouped)

    def scan(self, text: str) -> list[Finding]:
        """对每个 group 做 ``str.find`` 循环推进，产出精确命中。"""
        # 预筛选所有权在本方法（T-vq0）：调用方无需（也不再）先行 could_match 判定，
        # 保证「新 detector 忘记接入预筛选」这一缺陷 3 的根因不再复现。
        if not self.could_match(text):
            return []

        findings: list[Finding] = []
        for items in self._grouped.values():
            for item in items:
                value = item.value
                offset = 0
                while (index := text.find(value, offset)) != -1:
                    findings.append(
                        Finding(
                            start=index,
                            end=index + len(value),
                            rule_id=f"registered:{item.kind}",
                            kind="registered_secret",
                            confidence="exact",
                            priority=self._REGISTERED_PRIORITY,
                        )
                    )
                    offset = index + len(value)
        return findings


class UrlDetector:
    """URL query / form-urlencoded 凭据检测器（只替换敏感值，不重新序列化）。

    URL query 与 form-urlencoded 凭据检测器（解 T-06-13）。

    **绝不重新序列化（T-06-13）**：本检测器**禁止**引入任何 URL 解析库 —— 不拆解再 ``urlencode`` 重组。
    只用正则定位 span，替换走统一 span 机制，参数顺序 / 编码 / 非敏感参数**自然保真**。
    重新序列化会破坏 OAuth callback、magic link、预签名 URL（参数顺序与编码有签名语义）。

    两条路径：
    1. **URL query**：``[?&](key)=(value)``，value 终止于 ``&`` / ``#`` / 空白 /
       ``"`` / ``'`` / ``<`` / ``>`` / ``;``。
    2. **form-urlencoded**：先确认整体或局部是 ``k=v(&k=v)+`` 形状（**先判形状再拆**），
       再按 ``&`` 拆 pair —— 不把任意 ``a=b`` 都当 form。

    敏感 key 集（大小写不敏感）：``access_token`` / ``token`` / ``refresh_token`` /
    ``api_key`` / ``apikey`` / ``secret`` / ``client_secret`` / ``password`` /
    ``signature`` / ``code`` / ``x-amz-signature`` / ``x-amz-credential`` /
    ``x-amz-security-token``。
    **``code`` 与 ``signature`` 只在此上下文敏感** —— ``status.code`` / ``error.code``
    不能当 OAuth code（ref.md §10.3）；HTTP 状态码文本 ``status code 200`` 不命中。

    **key 先归一化再比对（percent-decode 绕过防护）**：query key 在 RFC 3986 里
    允许 percent-encoding，``access%5Ftoken`` / ``%74oken`` / ``X-Amz-Security%2DToken``
    与明文 key 语义等价。只比对字面量会让攻击者用编码形式绕过检测，
    故 :meth:`_normalize_key` 先 ``unquote`` 再小写比对。
    注意归一化**只用于判定**，finding 的 span 仍落在**原文**上 —— 不重新序列化。

    同理，**值**也先 unquote 再判变量引用（``%24%7BTOKEN%7D`` → ``${TOKEN}``）：
    变量引用例外是「值本就是模板引用」的语义判定，不应因编码形式而失效。

    ``kind`` = ``url_credential``，``confidence="high"``，``priority=85``。
    """

    rule_id: str = "url"

    # url 结构化证据强度：与 cookie 同级（85），弱于 header/dsn 的完整协议形态
    _URL_PRIORITY: ClassVar[int] = 85

    # URL query 敏感 key（大小写不敏感）
    _SENSITIVE_QUERY_KEYS: ClassVar[frozenset[str]] = frozenset(
        {
            "access_token",
            "token",
            "refresh_token",
            "api_key",
            "apikey",
            "secret",
            "client_secret",
            "password",
            "signature",
            "code",
            "x-amz-signature",
            "x-amz-credential",
            "x-amz-security-token",
        }
    )

    # query key 字面量（廉价预筛选用）
    _KEY_HINTS: ClassVar[tuple[str, ...]] = tuple(sorted(_SENSITIVE_QUERY_KEYS))

    # URL query：`?` 或 `&` 后的 key=value，value 终止于 `&` / `#` / 空白 / 引号 / `<>` / `;`
    # key 允许 `%` 与 `+`（percent-encoded key，如 `access%5Ftoken` / `X-Amz-Secret%2B`）——
    # 不含这两个字符会让编码 key 连「结构性命中」都拿不到，直接整条绕过检测。
    #
    # value 与 key 一样用**无界**量词：写 `{1,4096}` 看似「有界更安全」，实际是把长凭据**截断**成 4096 字符的 finding
    # 余下部分原样留在输出里（`?token=<5000 个 A>` 只遮前 4096，后 904 泄露）。
    # value 字符类是**取反**类，每步必定消耗一个字符、无重叠歧义，是线性匹配，不存在 ReDoS 面。
    _QUERY_RE: ClassVar[re.Pattern] = re.compile(r"[?&]([A-Za-z0-9_.%+\-]{1,64})=([^&#\s\"'<>;]+)")

    # form-urlencoded：整体为 `k=v` 且含至少一个 `&` 或 `;`（先判形状）
    _FORM_SHAPE_RE: ClassVar[re.Pattern] = re.compile(r"^[^\s]*[A-Za-z0-9_.%+\-]{1,64}=[^&\s]*[&;][^\s]+$")

    # form pair 拆解。value 终止符含 `;`：与 _QUERY_RE 同口径，否则 `a=1; token=X` 的 value 会一路吞到行尾（`1;token=X`），把后续非敏感 pair 一起删掉。
    _FORM_PAIR_RE: ClassVar[re.Pattern] = re.compile(r"([A-Za-z0-9_.%+\-]{1,64})=([^&#\s;]+)")

    # `;` 分隔的 query pair：value 终止符与 _QUERY_RE 一致（含 `;` 自身）。
    # 只匹配 `;` 之后的 pair（`;token=` / 行首 `token=`）
    # 不能把 `?` / `&` 也收进分隔符类：那样 `?a=1&token=X` 会被本正则与 _QUERY_RE 各命中一次，同一 span 产出两个 finding
    # （unique_findings 合并成 1，但 raw_rule_hits 会虚高，且单测里 `len(findings) == 1` 直接失败）。
    # 行首 alternative 覆盖 `;token=` 的裸形态
    _SEMICOLON_PAIR_RE: ClassVar[re.Pattern] = re.compile(r"(?:\A|;)([A-Za-z0-9_.%+\-]{1,64})=([^&#\s\"'<>;]+)")

    # 单参数 form：整串恰为一个 `key=value`。
    # key 前**不得**紧跟标识符字符（`(?<![A-Za-z0-9_])`），且 key 内不得含 `.` / `-`
    # 否则 `status.code=200` / `x-amz-security-token=` 这类复合前缀会被当成单参数 form。
    # value 另须**长于 8 字符**：本路径没有 `?` / `&` 这类「这确实是一条 query」的外部证据，只有形状本身。
    # 而 `code` 是**上下文敏感** key（docstring：`code` 仅在 URL 上下文敏感），`code=200` / `code=500` 是 HTTP 状态码而非值。
    # 凭据值实际不会只有 ≤8 字符，故长度下限把上下文敏感的短值挡在外面，同时不放过任何真实凭据形态。
    _MIN_FORM_VALUE: ClassVar[int] = 8

    _SINGLE_PAIR_RE: ClassVar[re.Pattern] = re.compile(
        r"(?<![A-Za-z0-9_])([A-Za-z0-9_]{1,64})=([^&#\s\"'<>;]{1,4096})\Z"
    )

    # 变量引用值：`$X` / `${X}` / `{x}` / `os.getenv(...)` / `process.env.X` —— 源码模板例外（T-06-17）
    #
    # 与 ``AssignmentDetector._VAR_REF_RE`` 的 alternative 集合**保持同构**：两条路径面对的是同一种「值本就是引用」的语义
    # 口径不一致会让同一段文本在 `?a=1&` 有无前缀时脱敏结果不同。全部 alternative 锚定在值起始处（缺陷 2 的定论）。
    _VAR_REF_RE: ClassVar[re.Pattern] = re.compile(
        r"^\$\{?[A-Za-z_][A-Za-z0-9_]*\}?"
        r"|^\{[A-Za-z_][A-Za-z0-9_.]*\}"
        r"|^os\.getenv\s*\("
        r"|^os\.environ\s*\["
        r"|^process\.env\."
    )

    @staticmethod
    def _is_variable_reference(value: str) -> bool:
        """判断 query 值是否为源码变量引用（配置模板例外，T-06-17）。

        值可能被 percent-encoded（``%24%7BTOKEN%7D`` ↔ ``${TOKEN}``）。
        **不 try/except**：``unquote`` 对畸形 ``%`` 序列是原样保留而非抛错（``unquote("%zz") == "%zz"``）
        且本函数是 fail-closed 方向上的「跳过脱敏」闸门 —— 加 except 反而会在异常路径上放过真实 secret
        """
        return bool(UrlDetector._VAR_REF_RE.match(unquote(value)))

    @staticmethod
    def _normalize_key(key: str) -> str:
        """query key 归一化：percent-decode 后小写。

        ``access%5Ftoken`` / ``%74oken`` 与 ``access_token`` / ``token`` 语义等价，
        只在明文上比对等于给攻击者留了编码绕过口子。归一化仅用于**判定**，finding 的 span 始终落在原文（不重新序列化）。
        """
        return unquote(key).lower()

    def _is_sensitive(self, key: str) -> bool:
        return self._normalize_key(key) in self._SENSITIVE_QUERY_KEYS

    def _value_finding(self, match: re.Match, value_index: int = 2) -> Finding:
        """按匹配中的 value 组构造 finding（四条路径共用，保证 kind/priority 一致）。"""
        return Finding(
            start=match.start(value_index),
            end=match.end(value_index),
            rule_id=self.rule_id,
            kind="url_credential",
            confidence="high",
            priority=self._URL_PRIORITY,
        )

    def _is_skippable_value(self, value: str) -> bool:
        """值级护栏：空值 / 变量引用一律不产 finding（四条路径共用同一口径）。"""
        return not value or self._is_variable_reference(value)

    def could_match(self, text: str) -> bool:
        """廉价预筛选：含 ``=`` 且至少有一个 query/form 结构夹带敏感 key。

        两个子判据缺一不可，否则会引入误报：

        - **敏感 key 字面量**：靠 ``_KEY_HINTS`` 廉价命中。
          注意 ``token=${TOKEN}`` 这类「key 明文中、值是变量引用」的文本也满足本判据
          由 ``scan`` 的值级护栏（非秘密值一律不进 finding）兜住，预筛选**不必**（也不能）预判。
          只看字面量会漏掉**编码 key**（``?%74oken=`` 里没有子串 ``token``），
          故带 ``%`` 时须解码后再比一次；无 ``%`` 时不做 ``unquote``（省一次拷贝）。
        - **结构**：``?`` / ``&`` / ``;`` 之一或 form 形状。

        为什么必须有结构判据：只有 key 字面量时，``token=$TOKEN`` / ``code=200`` 这类**非 URL 字段文本**会一路进昂贵扫描，
        虽最终被值级护栏挡下，却让单测里 patch ``could_match`` 的「昂贵路径」判据失去区分度。

        为什么必须有 key 判据：只有结构时，``?a=1`` / ``k=v&x=y`` 这类无敏感 key的文本会进昂贵扫描 —— 那只是白费，但会让预筛选形同虚设。

        另：Python 3.10 起 ``urllib.parse.parse_qsl`` 默认 ``separator="&"``（``;`` 仅传 ``separator=";"`` 时不拆）。
        本判据比 ``query.count("=")==1``更严，是**有意**的 —— 结构判据若用「恰好一个 ``=``」，会被 value 里含 ``=``（base64 padding）的正常 query 绕过。
        """
        if not isinstance(text, str) or not text:
            return False
        if "=" not in text:
            return False
        lowered = text.lower()
        if not any(key in lowered for key in self._KEY_HINTS) and not any(
            key in unquote(lowered) for key in self._KEY_HINTS
        ):
            return False
        if "?" in text or "&" in text or ";" in text:
            return True
        # 形状判据按**行**判定（理由同 ``scan``：锚定正则在多行文本上会因前导 `\n` 失配）。
        return any(self._FORM_SHAPE_RE.match(line) or self._SINGLE_PAIR_RE.match(line) for line in text.split("\n"))

    def scan(self, text: str) -> list[Finding]:
        if not self.could_match(text):
            return []

        findings: list[Finding] = []
        findings.extend(self._scan_url_query(text))

        # query 亦可由 `;` 分隔（``?a=1;token=SECRET``）。
        # 默认 regex 不把 `;` 当分隔符，只认 `?` / `&` 会把 `;` 之后的敏感 pair 整段漏掉；显式再扫一遍。
        if ";" in text:
            findings.extend(self._scan_semicolon_query(text))

        # form-urlencoded：按**行**判定形状与 URL 性（缺陷修复）。
        #
        # 两条都必须是**按行**的，否则多行文本会整片漏报：
        #
        # 1. 形状判据 `_FORM_SHAPE_RE` / `_SINGLE_PAIR_RE` 是**行首锚定**的
        #    （`^...$` / `...\Z`），且 form value 字符集不含 `\s`。
        #    对整段文本 `.match()` 时，只要该 form 不在第 1 行（前面有 `\n`，
        #    典型场景是 `provider.read_file` 把整个文件 join 后一次性脱敏），
        #    锚点落在 `\n` 上即失配 → 整条漏报。
        # 2. `?` / `://` 的「非 URL」判据原先是**整段**的：文件里任意一处出现
        #    `?` 或 `://`，就会关掉**所有行**的 form 扫描。
        #    真实文件（如 url.md）几乎必然含 `?`，故 form 形状的凭据会**全部漏报**。
        #
        # 按行后语义与单行调用完全一致，且 URL 行仍由 `_scan_url_query` 负责，不重复计数。
        findings.extend(self._scan_form_lines(text))

        return findings

    def _scan_form_lines(self, text: str) -> list[Finding]:
        """逐行判定 form 形状并扫描，把行内偏移换算回整段偏移。

        每行独立做「非 URL + form 形状」判定，使「第 N 行（N > 1）的 form 凭据」
        与第 1 行同等对待，且不受文本其它位置的 `?` / `://` 影响。
        """
        findings: list[Finding] = []
        offset = 0
        for line in text.split("\n"):
            # 含 `?` / `://` 的行是 URL，其 `&` 分隔的 pair 已由 _scan_url_query 覆盖
            if "?" not in line and "://" not in line:
                if self._FORM_SHAPE_RE.match(line):
                    for finding in self._scan_form(line):
                        findings.append(replace(finding, start=finding.start + offset, end=finding.end + offset))
                elif self._SINGLE_PAIR_RE.match(line):
                    for finding in self._scan_single_pair(line):
                        findings.append(replace(finding, start=finding.start + offset, end=finding.end + offset))
            offset += len(line) + 1  # +1 为换行符
        return findings

    def _scan_single_pair(self, text: str) -> list[Finding]:
        """扫描单参数 form 形状（``key=value``，整个文本恰为一个 pair）。

        单参数 form（``access_token=SECRET``）：无分隔符，``_FORM_SHAPE_RE`` 有意不覆盖
        （「任意 a=b 都当 form」会误伤赋值语句）。但**整体恰为一个 pair 且 key 敏感**的形状
        （key 前无标识符字符、无 ``.`` / ``-`` 复合前缀）是 form body 的确凿形状 ——
        此时是 ``AssignmentDetector`` 的严格字段同款判据，故按 form 处理。
        不带 rule_id 后缀：与 query 路径同 rule，替换后 sentinel 一致
        （``AssignmentDetector`` 产出的是 ``[REDACTED:credential]``，见 TAG 命名分工）。
        """
        match = self._SINGLE_PAIR_RE.match(text)
        if match is None:  # pragma: no cover - 调用方已用同一正则判形状
            return []
        if not self._is_sensitive(match.group(1)):
            return []
        value = match.group(2)
        if self._is_skippable_value(value) or len(value) <= self._MIN_FORM_VALUE:
            return []
        # 占位符 / 已脱敏标记保留（与 AssignmentDetector 同一判据）：
        # 本路径没有 `?` / `&` 的外部结构证据，`token=[REDACTED_SECRET]` 会被形状判据当成 form pair
        # 不加此护栏就会把已经脱敏的文本二次污染，破坏 README 的「二次脱敏结果应不变」。
        if is_placeholder_value(unquote(value)):
            return []
        return [self._value_finding(match)]

    def _scan_url_query(self, text: str) -> list[Finding]:
        """扫描 URL query 形态（``?k=v`` / ``&k=v``）。"""
        findings: list[Finding] = []
        for match in self._QUERY_RE.finditer(text):
            if self._is_sensitive(match.group(1)) and not self._is_skippable_value(match.group(2)):
                findings.append(self._value_finding(match))
        return findings

    def _scan_semicolon_query(self, text: str) -> list[Finding]:
        """扫描以 ``;`` 分隔的 query（``?a=1;token=SECRET`` / ``;access_token=v``）

        与 ``_scan_url_query`` 同构：同样的 value 终止符集合（含 ``;``）
        同样的敏感 key 归一化，同样的变量引用护栏
        ``;`` 前的 pair 由本方法负责， ``?`` / ``&`` 前的 pair 由 ``_scan_url_query`` 负责，两者 span 不重叠
        """
        findings: list[Finding] = []
        for match in self._SEMICOLON_PAIR_RE.finditer(text):
            if self._is_sensitive(match.group(1)) and not self._is_skippable_value(match.group(2)):
                findings.append(self._value_finding(match))
        return findings

    def _scan_form(self, text: str) -> list[Finding]:
        """扫描 form-urlencoded 形态（已确认形状，按 ``&`` / ``;`` 拆 pair）。"""
        findings: list[Finding] = []
        for match in self._FORM_PAIR_RE.finditer(text):
            if self._is_sensitive(match.group(1)) and not self._is_skippable_value(match.group(2)):
                finding = self._value_finding(match)
                # form 路径单独标 `url.form`，便于在 raw_rule_hits 里区分形态来源
                findings.append(replace(finding, rule_id=f"{self.rule_id}.form"))
        return findings


class VendorTokenDetector:
    """厂商前缀 Token 检测器（多规则，无单一 rule_id）。

    厂商 Token 前缀检测器。

    每条规则带 ``kind``（用于 typed sentinel）与 ``hints``（厂商前缀字面量，用于廉价预筛选）。
    规则只匹配高置信度的结构化 Token，避免误伤普通业务文本。

    **前缀字面量随规则同处声明（单一真源）**：``hints`` 不再是一张与 ``_VENDOR_RULES``
    平行维护的全局表 —— 新增 / 改动规则时若忘记同步 hint，会静默让该规则在 ``could_match`` 阶段被整体跳过（检测漏报且无报错）。
    """

    rule_id: str = ""

    # 厂商规则优先级（低于 registered 的 100，高于裸熵兜底）
    _VENDOR_PRIORITY: ClassVar[int] = 80

    _VENDOR_RULES: ClassVar[tuple[DetectorRule, ...]] = (
        DetectorRule(
            rule_id="vendor.openai",
            kind="openai_key",
            regex=re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
            priority=_VENDOR_PRIORITY,
            hints=("sk-",),
        ),  # OpenAI / 通用 sk-
        DetectorRule(
            rule_id="vendor.github",
            kind="github_token",
            regex=re.compile(r"gh[pousr]_[A-Za-z0-9]{36}"),
            priority=_VENDOR_PRIORITY,
            hints=("ghp_", "gho_", "ghu_", "ghs_", "ghr_"),
        ),  # GitHub PAT / OAuth / app / server / refresh（classic 系）
        DetectorRule(
            rule_id="vendor.github_fine_grained",
            kind="github_token",
            regex=re.compile(r"github_pat_[A-Za-z0-9_]{22,}"),
            priority=_VENDOR_PRIORITY,
            hints=("github_pat_",),
        ),  # GitHub PAT (fine-grained)
        DetectorRule(
            rule_id="vendor.slack",
            kind="slack_token",
            # workflow token 的前缀是 `xwfp-`（**不是** `x[wa]fp-`）：
            # 原正则写成 `x[wa]fp-`（字符类 = w 或 a），比 `hints` 宽，
            # 于是 `xafp-…` 只在**同文本别处出现过 Slack hint**时才会被遮 ——
            # 因为 `could_match` 是整段的 OR，hints 命中后正则对全文生效，
            # `xafp-` 就被顺手匹配并遮掉。表现为**同一 token 独立出现不遮、
            # 与其它 Slack token 同文件出现时被遮**（非确定性，危险且难排查）。
            # 收紧为 `xwfp-` 与 hints / 文档口径（vendor.md S036、S106）一致。
            regex=re.compile(r"(?:xox[baprs]-[A-Za-z0-9-]{10,}|xwfp-[A-Za-z0-9-]{10,}|xapp-[A-Za-z0-9-]{10,})"),
            priority=_VENDOR_PRIORITY,
            hints=("xox", "xwfp-", "xapp-"),
        ),  # Slack（user/bot/app/refresh + workflow token + app-level token）
        DetectorRule(
            rule_id="vendor.aws",
            kind="aws_access_key_id",
            regex=re.compile(r"AKIA[0-9A-Z]{16}"),
            priority=_VENDOR_PRIORITY,
            hints=("AKIA",),
        ),  # AWS Access Key
        DetectorRule(
            rule_id="vendor.aws_temp",
            kind="aws_access_key_id",
            regex=re.compile(r"ASIA[0-9A-Z]{16}"),
            priority=_VENDOR_PRIORITY,
            hints=("ASIA",),
        ),  # AWS Temporary Access Key
        DetectorRule(
            rule_id="vendor.gitlab",
            kind="gitlab_token",
            regex=re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
            priority=_VENDOR_PRIORITY,
            hints=("glpat-",),
        ),  # GitLab PAT
        DetectorRule(
            rule_id="vendor.xai",
            kind="xai_key",
            regex=re.compile(r"xai-[A-Za-z0-9]{20,}"),
            priority=_VENDOR_PRIORITY,
            hints=("xai-",),
        ),  # xAI
        DetectorRule(
            rule_id="vendor.google_api_key",
            kind="google_token",
            regex=re.compile(r"AIza[0-9A-Za-z_-]{35}"),
            priority=_VENDOR_PRIORITY,
            hints=("AIza",),
        ),  # Google API Key
        DetectorRule(
            rule_id="vendor.google_oauth",
            kind="google_token",
            regex=re.compile(r"ya29\.[0-9A-Za-z_-]+"),
            priority=_VENDOR_PRIORITY,
            hints=("ya29.",),
        ),  # Google OAuth access token
        DetectorRule(
            rule_id="vendor.tencent",
            kind="tencent_secret_id",
            regex=re.compile(r"\bAKID[0-9A-Za-z]{13,}"),
            priority=_VENDOR_PRIORITY,
            hints=("AKID",),
        ),  # 腾讯云 SecretId
        DetectorRule(
            rule_id="vendor.aliyun",
            kind="aliyun_access_key",
            regex=re.compile(r"\bLTAI[0-9A-Za-z]{17,}"),
            priority=_VENDOR_PRIORITY,
            hints=("LTAI",),
        ),  # 阿里云 AccessKeyId
        DetectorRule(
            rule_id="vendor.jwt",
            kind="jwt",
            regex=re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
            priority=_VENDOR_PRIORITY,
            hints=("eyJ",),
        ),  # JWT
        DetectorRule(
            rule_id="vendor.bearer",
            kind="bearer",
            regex=re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}"),
            priority=_VENDOR_PRIORITY,
            hints=("Bearer",),
        ),  # Bearer Token
    )

    def could_match(self, text: str) -> bool:
        # 前缀字面量的唯一真源是各规则的 ``hints``（不再单独维护一份全局前缀表）：
        # 新增 / 改动规则时 hint 与 regex 同行，遗漏风险被结构性消除。
        if not isinstance(text, str) or not text:
            return False
        return any(hint in text for rule in self._VENDOR_RULES for hint in rule.hints)

    def scan(self, text: str) -> list[Finding]:
        # 预筛选所有权在本方法（T-vq0）：调用方无需（也不再）先行 could_match 判定，
        # 保证「新 detector 忘记接入预筛选」这一缺陷 3 的根因不再复现。
        if not self.could_match(text):
            return []

        findings: list[Finding] = []
        for rule in self._VENDOR_RULES:
            for match in rule.regex.finditer(text):
                findings.append(
                    Finding(
                        start=match.start(),
                        end=match.end(),
                        rule_id=rule.rule_id,
                        kind=rule.kind,
                        confidence="high",
                        priority=rule.priority,
                    )
                )
        return findings
