# -*- coding: utf-8 -*-
# ============================================================================
# 眼健康自查助手 · 后端模块 · 出处溯源层：为报告中的每一条依据标注「出自哪部古籍 / 哪份文献」。
# @author  杨博 (yangbo621@163.com)
# @license Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
#          https://creativecommons.org/licenses/by-nc/4.0/
# （详见随包 LICENSE.txt / NOTICE.md；商业使用需另行获得书面授权）
# ============================================================================

"""
出处溯源层：为报告中的每一条依据标注「出自哪部古籍 / 哪份文献」。

设计原则（与技能一致）：不凭记忆编出处——
  ① 文件级：库内每个 md 文件对应一部/一组确定的文献来源（FILE_SOURCE）；
  ② 行内级：证据原文里出现的书名号《…》会被抽取出来，作为该条依据真正引用的古籍；
  ③ 汇总级：整份报告自动汇总出「引用古籍与文献一览」，含书名、朝代作者、性质、命中次数与示例出处位置。
"""

import re
from collections import OrderedDict

# ---------- ① 文件级来源 ----------
FILE_SOURCE = {
    "08-眼科经典条文.md": {
        "kind": "古籍", "name": "《黄帝内经》《银海精微》《原机启微》《审视瑶函》等眼科古籍原文",
        "note": "条文取自本技能内置 sources/ 原文文本（黄帝内经素问·灵枢、银海精微、原机启微、审视瑶函）"},
    "04-眼科病证分证论治.md": {
        "kind": "教材", "name": "《中医眼科学》各论 · 病证分证论治",
        "note": "按五轮 + 内障外障分七类，每病含定义/五轮归属/鉴别/分证论治/红线/调护"},
    "06-眼科常用方剂.md": {
        "kind": "方书", "name": "《方剂学》（七版）+《中医眼科学》专科方 + 古籍原书方论（三书）",
        "note": "含原机启微附方、审视瑶函重点方、银海精微代表方"},
    "05-眼科常用中药.md": {
        "kind": "教材", "name": "《中药学》/《中医眼科学》眼科常用中药",
        "note": "性味归经、明目退翳功效、用法用量与安全注意"},
    "01-眼科基础与五轮八廓.md": {
        "kind": "教材", "name": "《中医眼科学》基础理论 · 五轮八廓",
        "note": "五轮八廓学说及眼与脏腑经络关系"},
    "02-眼科病因病机与诊断.md": {
        "kind": "教材", "name": "《中医眼科学》病因病机与眼科诊断", "note": ""},
    "03-眼科辨证.md": {
        "kind": "教材", "name": "《中医眼科学》辨证纲领（五轮/八廓/内外障/脏腑）", "note": ""},
    "07-眼科针灸与外治.md": {
        "kind": "教材", "name": "《针灸学》/《中医眼科学》眼科针灸与外治", "note": ""},
    "00-眼科证治总索引.md": {
        "kind": "专科资料", "name": "本技能眼科证治总索引（跨文件路由层）",
        "note": "路由层，不含细节；细节回 01/03/04/05/06/07/08"},
    "09-现代眼科共识与筛查要点.md": {
        "kind": "现代文献", "name": "现代眼科专家共识（西医）三篇",
        "note": "仅作知识溯源、筛查预警与转诊指路，不作西医诊断"},
    "安全-眼科用药与外治安全.md": {
        "kind": "安全表", "name": "本技能眼科用药与外治安全表（源自《药典》、教材禁忌与配伍妊娠禁忌）",
        "note": "红线：扩瞳药禁用于青光眼、点眼药禁自制、危险穴禁按压等"},
}

GENERIC_SOURCE = {
    "kind": "教材", "name": "通用中医基础教材（《中医基础理论》《中药学》《方剂学》等）", "note": ""
}

# 09 号文件的现代文献明细（原文落盘于 sources/现代文献/）
MODERN_REFS = [
    "《高度近视防控专家共识（2023）》——中华医学会眼科学分会眼视光学组等，"
    "《中华眼视光学与视觉科学杂志》2023,25(6):401-407",
    "《眼轴长度在近视防控管理中的应用专家共识（2023）》——何鲜桂、许迅等，"
    "《中华实验眼科杂志》2023",
    "《面向基层的人工智能眼底彩色照相黄斑区域病变体征筛查》——"
    "中华医学会眼科学分会眼底病学组等，《中华眼底病杂志》2022,38(9):711-727",
]

# ---------- ② 古籍元数据：书名 → (规范名, 朝代·作者, 性质, 说明) ----------
CLASSIC_META = {
    "黄帝内经": ("《黄帝内经》", "先秦—汉", "中医理论之源；五轮学说、肝开窍于目之经典根据"),
    "内经": ("《黄帝内经》", "先秦—汉", "中医理论之源；五轮学说、肝开窍于目之经典根据"),
    "素问": ("《黄帝内经·素问》", "先秦—汉", "目论诸篇：五脏生成、金匮真言论、宣明五气等"),
    "灵枢": ("《黄帝内经·灵枢》", "先秦—汉", "目论诸篇：大惑论、脉度等"),
    "银海精微": ("《银海精微》", "唐·孙思邈", "现存最早眼科专著之一，五轮八廓与七十二证"),
    "原机启微": ("《原机启微》", "元·倪维德", "首立眼科病因病机十八论，附方论"),
    "审视瑶函": ("《审视瑶函》", "明·傅仁宇", "眼科集大成：方论、金玉赋、内障外障辨"),
    "秘传眼科龙木论": ("《秘传眼科龙木论》", "宋元·葆光道人", "内障（金针拨障）与七十二证方论"),
    "眼科龙木论": ("《秘传眼科龙木论》", "宋元·葆光道人", "内障（金针拨障）与七十二证方论"),
    "目经大成": ("《目经大成》", "清·黄庭镜", "眼科辨证、八廓与内外障辨"),
    "一草亭目科全书": ("《一草亭目科全书》", "清·邓苑", "眼目论、内障外障辨"),
    "银海指南": ("《银海指南》", "清·顾锡", "眼科证治方论"),
    "医级": ("《医级》", "清·魏之琇", "杞菊地黄丸出处"),
    "温病条辨": ("《温病条辨》", "清·吴瑭", "桑菊饮等出处"),
    "脾胃论": ("《脾胃论》", "金·李杲", "补中益气汤等出处"),
    "医林改错": ("《医林改错》", "清·王清任", "血府逐瘀汤等活血方出处"),
    "眼科奇书": ("《眼科奇书》", "清·佚名", "眼科方论"),
    "眼科大成": ("《眼科大成》", "清·佚名", "眼科方论"),
    "中医眼科学": ("《中医眼科学》", "现代教材", "中医院校规划教材（本技能主要骨架）"),
    "中医眼科": ("《中医眼科学》", "现代教材", "中医院校规划教材（本技能主要骨架）"),
    "方剂学": ("《方剂学》", "现代教材", "方剂组成、功用与类方鉴别"),
    "中药学": ("《中药学》", "现代教材", "中药性味归经与用法用量"),
    "针灸学": ("《针灸学》", "现代教材", "腧穴定位与针刺禁忌"),
}

CITE_RE = re.compile(r"《([^《》]{2,40})》")

# 现代论文/文献标题（书名号内但属现代文献，需强制归类，避免误作古籍）
MODERN_TITLES = {
    "面向基层的人工智能眼底彩色照相黄斑区域病变体征筛查": (
        "现代文献", "中华医学会眼科学分会眼底病学组等",
        "《中华眼底病杂志》2022,38(9):711-727"),
}

# 现代文献标志（期刊、共识、指南）——避免把期刊名误归为古籍
MODERN_MARKERS = ("杂志", "学报", "共识", "指南", "期刊", "综述", "Meta", "JAMA",
                  "Ophthalmology", "中华医学", "中华眼底病", "中华实验眼科")


def _kind_of(key, author=""):
    """判断一本书/文献的性质：古籍 / 教材 / 现代文献"""
    if key in MODERN_TITLES:
        return MODERN_TITLES[key][0]
    if any(m in key for m in MODERN_MARKERS):
        return "现代文献"
    if author == "现代教材":
        return "教材"
    return "古籍"


def _key_of_name(name):
    """名称归一（用于去重）：去书名号、全角括号转半角、去空格"""
    s = name.replace("《", "").replace("》", "")
    s = s.replace("（", "(").replace("）", ")").replace(" ", "")
    return s.strip()


def _norm_book(raw):
    """《素问·五脏生成》 → 素问；《审视瑶函》 → 审视瑶函"""
    name = raw.split("·")[0].strip()
    return name


def extract_books(text, book_hint=""):
    """抽取证据原文中出现的书名号，归一化为规范古籍/文献名

    book_hint：段落所属书目（由 md 一/二级标题推断，如「银海精微」）。
    古籍条文常只在章节标题写书名、正文不再重复，故正文抽不到时用 book_hint 兜底，
    保证「出自哪部古籍」一定能落到具体书名，而不是泛泛的一串书名。
    """
    out = []
    seen = set()

    def add(key):
        if not key or key in seen:
            return
        seen.add(key)
        mt = MODERN_TITLES.get(key)
        if mt:
            out.append({"key": key, "name": f"《{key}》", "author": mt[1],
                        "desc": mt[2], "kind": mt[0]})
            return
        meta = CLASSIC_META.get(key)
        if meta:
            out.append({"key": key, "name": meta[0], "author": meta[1],
                        "desc": meta[2], "kind": _kind_of(key, meta[1])})
        else:
            out.append({"key": key, "name": f"《{key}》", "author": "",
                        "desc": "", "kind": _kind_of(key)})

    for raw in CITE_RE.findall(text or ""):
        add(_norm_book(raw))
    if not out and book_hint:
        add(_norm_book(book_hint))
    # 同一本书的不同写法（如「眼科龙木论」与「秘传眼科龙木论」）按规范名去重
    uniq, names = [], set()
    for c in out:
        if c["name"] in names:
            continue
        names.add(c["name"])
        uniq.append(c)
    return uniq


def file_source(fname):
    """文件 → 来源描述"""
    if fname in FILE_SOURCE:
        return FILE_SOURCE[fname]
    if fname.startswith("通用中医/") or fname.startswith("通用中医"):
        return dict(GENERIC_SOURCE, name=f"{GENERIC_SOURCE['name']}（{fname}）")
    return {"kind": "专科资料", "name": fname, "note": ""}


# 类别显示优先级：一条依据同时有「古籍引用」与「教材文件」时，按此顺序取最靠前者
KIND_PRIORITY = ["古籍", "方书", "现代文献", "教材", "专科资料", "安全表"]


def _pick_kind(cited, fallback):
    """依据的类别 = 其实际引用书目的类别（古籍优先），无引用时回落文件类别"""
    kinds = [c.get("kind") for c in cited or [] if c.get("kind")]
    for k in KIND_PRIORITY:
        if k in kinds:
            return k
    return fallback


def enrich_evidence(ev):
    """给单条依据补上：文件级来源 + 行内/章节归属的古籍"""
    if not ev:
        return ev
    fname = ev.get("file", "")
    fs = file_source(fname)
    cited = extract_books(ev.get("text", ""), ev.get("book", ""))
    e = dict(ev)
    e["src_file_kind"] = fs["kind"]          # 文件级类别（保留备查）
    e["src_kind"] = _pick_kind(cited, fs["kind"])   # 展示类别：引用优先（古籍 > 教材）
    e["src_name"] = fs["name"]
    e["src_note"] = fs.get("note", "")
    e["cited"] = cited
    e["classic_names"] = [c["name"] for c in cited if c.get("kind") == "古籍"]
    # 展示用：优先显示行内引用的古籍，其次文件级文献
    if cited:
        e["cite_label"] = "、".join(c["name"] for c in cited[:3])
    else:
        e["cite_label"] = fs["name"]
    return e


def enrich_all(conclusions, daily_care=None):
    """就地给所有结论（含调理条目）的依据补出处"""
    for c in conclusions or []:
        c["evidence"] = [enrich_evidence(e) for e in (c.get("evidence") or [])]
    for b in (daily_care or {}).get("blocks", []):
        for it in b.get("items", []):
            it["evidence"] = [enrich_evidence(e) for e in (it.get("evidence") or [])]
    return conclusions


KIND_ORDER = ["古籍", "方书", "教材", "现代文献", "专科资料", "安全表"]


def build_bibliography(result):
    """汇总整份报告引用到的古籍与文献（含命中次数与示例出处）"""
    bucket = OrderedDict()
    modern_loc = ""

    def put(name, kind, author, desc, loc, nkey=None):
        k = nkey or _key_of_name(name)
        if k not in bucket:
            bucket[k] = {"kind": kind, "name": name, "author": author or "",
                         "desc": desc or "", "count": 0, "locs": []}
        bucket[k]["count"] += 1
        if loc and loc not in bucket[k]["locs"] and len(bucket[k]["locs"]) < 4:
            bucket[k]["locs"].append(loc)

    def walk(evs):
        nonlocal modern_loc
        for e in evs or []:
            fname = e.get("file", "")
            fs = file_source(fname)
            line = e.get("line", 0)
            loc = f"{fname}" + (f" · {e.get('section')}" if e.get("section") else "") \
                  + (f" · 第{line}行" if line else "")
            cited = e.get("cited") or []
            if cited:
                for c in cited:
                    put(c["name"], c.get("kind") or _kind_of(c["key"]),
                        c.get("author", ""), c.get("desc", ""), loc,
                        nkey=_key_of_name(c["name"]))
            elif fs["kind"] == "现代文献":
                # 09 号文件的三篇共识由下方 MODERN_REFS 明细统一列出，此处不重复
                modern_loc = modern_loc or loc
            else:
                put(fs["name"], fs["kind"], "", fs.get("note", ""), loc,
                    nkey=fs["name"])

    for c in result.get("conclusions") or []:
        walk(c.get("evidence"))
    for b in (result.get("daily_care") or {}).get("blocks", []):
        for it in b.get("items", []):
            walk(it.get("evidence"))

    # 引用到 09 现代共识时，补上三篇文献明细（全角/半角统一去重）
    if modern_loc:
        for ref in MODERN_REFS:
            name = ref.split("——")[0].strip()
            put(name, "现代文献", "", ref, modern_loc)

    items = sorted(bucket.values(),
                   key=lambda v: (KIND_ORDER.index(v["kind"]) if v["kind"] in KIND_ORDER else 99,
                                  -v["count"], v["name"]))
    return items
