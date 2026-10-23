# -*- coding: utf-8 -*-
# ============================================================================
# 眼健康自查助手 · 后端模块 · 辨证报告引擎（第三步 + 第四步）
# @author  杨博 (yangbo621@163.com)
# @license Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
#          https://creativecommons.org/licenses/by-nc/4.0/
# （详见随包 LICENSE.txt / NOTICE.md；商业使用需另行获得书面授权）
# ============================================================================

"""
辨证报告引擎（第三步 + 第四步）

流程严格遵循中医眼科技能的辨证七步骤与安全边界：
  0 红线优先（红线命中 → 急诊指路，终止辨证）
  1 抓主症 → 病种候选（04）；年龄区间作为病种候选的弱权重补充
  2 五轮定位（01）
  3 八纲定性（寒热/虚实），舌象权重最高
  4 落证 → 证型（03 / 00）
  5 方证双向核对：证型 → 治法 → 代表方（00 索引三 / 06）
  6 涉药四关：性能 / 配伍 / 人群 / 剂量炮制 → 安全表
  7 输出 A/B/C 分级 + 每条结论的可追溯依据（本地库 文件+章节+行号）

说明：全部依据均来自本地中医眼科知识库，本引擎不联网检索。
"""

from question_bank import QUESTIONS, SYND_FORMULA, WHEEL_MAP, CONTRAIND_MAP
from tcm_lib import LIB
from daily_care import build_daily_care
from citations import enrich_all, build_bibliography, extract_books

# 中医病种 → 西医对应名（用于联网补全现代医学信息）
DZ_WESTERN = {
    "视瞻有色": "中心性浆液性脉络膜视网膜病变(中浆)",
    "视瞻昏渺": "黄斑病变(老年性黄斑变性/中心性渗出性)",
    "白涩症": "干眼症/慢性结膜炎",
    "暴风客热": "急性卡他性结膜炎",
    "天行赤眼": "流行性出血性结膜炎",
    "针眼": "麦粒肿(睑腺炎)",
    "胞生痰核": "霰粒肿(睑板腺囊肿)",
    "睑弦赤烂": "睑缘炎",
    "时复目痒": "春季卡他性结膜炎",
    "火疳": "巩膜炎",
    "聚星障": "病毒性角膜炎",
    "凝脂翳": "细菌性角膜炎",
    "宿翳": "角膜瘢痕",
    "瞳神紧小": "虹膜睫状体炎",
    "绿风内障": "急性闭角型青光眼",
    "青风内障": "慢性开角型青光眼",
    "圆翳内障": "年龄相关性白内障",
    "云雾移睛": "玻璃体混浊(飞蚊症)",
    "青盲": "视神经萎缩",
    "高风内障": "视网膜色素变性",
    "暴盲": "突发性视力丧失",
    "能近怯远": "近视",
    "能远怯近": "远视/老视",
    "疳积上目": "维生素A缺乏/角膜软化症",
    "消渴目病": "糖尿病视网膜病变",
    "高血压眼底": "高血压视网膜病变",
    "流泪症": "溢泪(迎风流泪)",
    "漏睛": "慢性泪囊炎",
    "撞击伤目": "眼眶挫伤",
    "目系暴盲": "视神经炎",
    "络阻暴盲": "视网膜中央动脉阻塞",
    "真睛破损": "眼球穿通伤/破裂伤",
    "异物入目": "角膜/结膜异物（眼内异物）",
    "化学伤": "眼部酸碱化学烧伤",
}

# 红线 → 急诊指引（源自安全边界第 2 条）
RED_GUIDE = {
    "绿风内障": "立即眼科急诊：降眼压急救（可致不可逆失明），中医不可替代急救",
    "暴盲": "立即眼科急诊：视网膜中央动脉阻塞数小时即可致盲，争分夺秒",
    "络阻暴盲": "立即眼科急诊：视网膜中央动脉阻塞，争分夺秒",
    "目系暴盲": "立即眼科急诊：视神经炎，需激素等西医方案",
    "真睛破损": "立即眼科急诊：眼球穿通伤，勿压迫眼球",
    "异物入目": "立即眼科急诊：异物嵌顿勿自取",
    "化学伤": "立即就地把清水冲洗后送医：酸碱化学伤争分夺秒",
    "撞击伤目": "眼科急诊：排查前房积血、眼压升高、视网膜震荡",
    "疳积上目": "儿科+眼科急诊：补维生素A，延误致盲不可逆",
}


# ===== 古籍条文挂接：把 08 经典原文挂到每条核心结论的依据里 =====
# 说明：古籍条文层（08）多按「理论/病机/歌括」编排，正文不一定复述现代病名，
# 因此按「五轮 + 证型 + 病种」派生检索键，去 08 取最贴近的经典原文。
WHEEL_CLASSIC_KEYS = {
    "肉轮": ["肉轮", "脾", "胞睑", "脾胃"],
    "血轮": ["血轮", "心", "眦", "血"],
    "气轮": ["气轮", "肺", "白睛", "白仁"],
    "风轮": ["风轮", "肝", "乌睛", "翳"],
    "水轮": ["水轮", "肾", "瞳神", "瞳仁"],
}

SYND_CLASSIC_KEYS = {
    "wind_heat": ["风热", "风", "热", "翳"],
    "liver_fire": ["火", "肝", "热", "赤"],
    "lung_dry": ["肺", "燥", "气轮", "津液"],
    "liver_kidney_yin_def": ["肝肾", "肾", "目昏", "虚"],
    "qi_blood_def": ["血", "气", "目不明", "虚"],
    "yang_def": ["虚", "肾", "冷", "寒"],
    "phlegm_damp": ["湿", "痰", "脾胃", "水"],
    "spleen_def_damp": ["脾", "湿", "肉轮", "痰"],
    "damp_heat": ["湿热", "脾胃", "热", "湿"],
    "blood_stasis": ["血", "瘀", "络", "滞"],
    "liver_yang": ["肝", "阳", "风", "眩"],
}

DZ_CLASSIC_KEYS = {
    "视瞻有色": ["瞳神", "内障", "目昏", "水轮"],
    "视瞻昏渺": ["瞳神", "内障", "目昏", "肾"],
    "云雾移睛": ["内障", "瞳神", "肾", "虚"],
    "圆翳内障": ["内障", "瞳神", "肾", "翳"],
    "青风内障": ["内障", "瞳神", "头风", "痛"],
    "绿风内障": ["内障", "瞳神", "头风", "痛"],
    "青盲": ["青盲", "目系", "肝肾", "虚"],
    "暴盲": ["暴盲", "目系", "血", "络"],
    "目系暴盲": ["目系", "暴盲", "肝", "络"],
    "络阻暴盲": ["络", "暴盲", "血", "滞"],
    "能近怯远": ["目", "远视", "肝肾", "目昏"],
    "能远怯近": ["目", "老视", "肾", "虚"],
    "白涩症": ["泪", "燥", "肺", "目干"],
    "流泪症": ["泪", "肝", "冷泪", "虚"],
    "漏睛": ["泪", "眦", "热", "漏"],
    "针眼": ["胞睑", "脾胃", "热", "肿"],
    "睑弦赤烂": ["胞睑", "脾", "湿", "痒"],
    "胞生痰核": ["胞睑", "痰", "脾", "核"],
    "暴风客热": ["热", "赤", "风", "肿"],
    "天行赤眼": ["热", "赤", "疫", "传染"],
    "时复目痒": ["痒", "风", "虚", "时复"],
    "聚星障": ["翳", "风轮", "肝", "星"],
    "凝脂翳": ["翳", "热", "肝", "陷"],
    "宿翳": ["翳", "退翳", "肝", "宿"],
    "瞳神紧小": ["瞳神", "紧小", "肝", "痛"],
    "高风内障": ["雀目", "夜盲", "肾", "虚"],
    "疳积上目": ["疳", "脾", "小儿", "虚"],
    "消渴目病": ["消渴", "肾", "血", "络"],
    "高血压眼底": ["肝", "阳", "血", "络"],
    "撞击伤目": ["外伤", "血", "肿", "痛"],
    "火疳": ["火", "热", "白睛", "结"],
}

CLASSIC_FALLBACK_KEYS = ["目", "五轮", "内障"]


def _classic_keys(*groups):
    """合并多组检索键并去重（保持顺序）"""
    out = []
    for g in groups:
        for k in g or []:
            if k and k not in out:
                out.append(k)
    return out or list(CLASSIC_FALLBACK_KEYS)


def _pick_classic(keys, top_k, used):
    """从古籍条文层取 top_k 条未被使用过的原文，并打上 is_classic 标记"""
    got = []
    for e in LIB.search_classic(keys, top_k=top_k + 6):
        key = (e.get("file"), e.get("line"))
        if key in used:
            continue
        used.add(key)
        d = dict(e)
        d["is_classic"] = True
        got.append(d)
        if len(got) >= top_k:
            break
    if not got:  # 兜底：理论总纲级条文
        for e in LIB.search_classic(CLASSIC_FALLBACK_KEYS, top_k=top_k + 6):
            key = (e.get("file"), e.get("line"))
            if key in used:
                continue
            used.add(key)
            d = dict(e)
            d["is_classic"] = True
            got.append(d)
            if len(got) >= top_k:
                break
    return got


def attach_classic(concl, keys, used, top_k=2):
    """把经典原文追加到该结论的依据列表（置于最前，保证「查看依据」一眼可见古籍）"""
    evs = _pick_classic(keys, top_k, used)
    if not evs:
        return concl
    concl["evidence"] = evs + list(concl.get("evidence") or [])
    concl["has_classic"] = True
    return concl


# 年龄区间 → 眼病谱 / 调护侧重 / 筛查节奏 / 用药注意（均本库可溯）
AGE_INFO = {
    "u20": {
        "label": "20 岁以下",
        "spectrum": "近视（能近怯远）、春季结膜炎（时复目痒）、小儿疳积上目；青少年以屈光与行为问题为主",
        "focus": "以验光配镜 + 行为干预为要：户外光照（目浴阳光）、远眺运目、节制持续近距离用眼；"
                 "中医辅助养肝血、补肾精，不夸大『治愈近视』（宣称可逆转真性近视为误导）",
        "screen": "儿童青少年建立屈光档案，每年 2 次眼健康检查；低龄/高风险可缩短至每 3 个月 1 次；"
                  "低中度近视期每 6 个月 1 次专科",
        "med": "小儿用药按年龄体重折算剂量，须医师核定；扩瞳类中药（如青葙子）尤须谨慎；"
               "出现瞳孔区发白、夜盲、畏光揉眼须立即就医（疳积上目）",
        "keys": ["能近怯远", "户外活动", "筛查与随访频率", "疳积上目"],
    },
    "20_40": {
        "label": "20～40 岁",
        "spectrum": "视疲劳与干眼（白涩症）、中浆（视瞻有色）、近视进展；与熬夜过劳、精神应激关系密切",
        "focus": "久视伤血为第一戒：少屏久视、远眺运目、保证睡眠；中浆患者须减压、忌酒、忌熬夜",
        "screen": "有中浆/黄斑症状者须眼科 OCT 与造影评估；高度近视每 6 个月 1 次眼底随访",
        "med": "青壮年常自行购药点眼，点眼药/眼用散剂严禁自制，须医师开具正规制剂",
        "keys": ["白涩症", "视瞻有色", "久视伤血", "少屏久视"],
    },
    "40_60": {
        "label": "40～60 岁",
        "spectrum": "老视（能远怯近）、早期白内障（圆翳内障）、青光眼（青风内障）、中浆与慢病眼底",
        "focus": "老视以配镜为主、中医补肾益精辅助；此阶段开始重视青光眼与眼底病筛查",
        "screen": "建议纳入常规眼科检查（视力、眼压、眼底）；糖尿病/高血压者按医嘱定期眼底筛查；"
                  "高度近视每 6 个月 1 次",
        "med": "慢病用药（降压、降糖、抗凝）与中药同服须告知医师，避免相互作用",
        "keys": ["能远怯近", "圆翳内障", "青风内障", "消渴目病"],
    },
    "60_80": {
        "label": "60～80 岁",
        "spectrum": "年龄相关性白内障（圆翳内障）、老年黄斑变性（视瞻昏渺）、青光眼、视神经萎缩",
        "focus": "内障以扶正为主（补肝肾、益气血）；老年黄斑变性以西医为主、中医辅助；"
                 "控血压血糖、忌烟酒、强光下戴镜防晒",
        "screen": "视力下降影响生活时评估白内障手术时机；黄斑病变按医嘱定期眼底照相 + OCT；"
                  "高度近视每 6 个月 1 次眼底",
        "med": "老年常多重用药，中药须由医师酌减剂量并核对手肾功能与相互作用；"
               "家居照明与防跌倒（视力障碍者）",
        "keys": ["圆翳内障", "视瞻昏渺", "青风内障", "老年"],
    },
    "80p": {
        "label": "80 岁以上",
        "spectrum": "白内障、老年黄斑变性、青光眼与视神经病变为主要致盲原因；常合并多种全身病",
        "focus": "以保存有用视力与生活能力为目标：充足照明、防跌倒、大字读物与助视器；"
                 "中医调护以补肝肾益气血、改善生存质量为度，不追求『退翳复明』",
        "screen": "定期眼科随访（视力、眼压、眼底）；白内障手术须由眼科评估全身耐受",
        "med": "高龄多重用药与肝肾功能减退，任何内服中药必须经医师面诊，剂量宜小、疗程宜短；"
               "手术与有创操作须综合评估",
        "keys": ["圆翳内障", "视瞻昏渺", "青盲", "老年"],
    },
}


# ---------- 工具 ----------
def _collect(answers: dict):
    """把 {qid: value|list} 汇总为 tags 包"""
    bag = {"dz": [], "wheel": [], "synd": [], "contraind": [],
           "onset": [], "red": [], "red_partial": False, "age": None, "age_dz": [],
           "laterality": None, "tongue": None, "answers": []}
    qmap = {q["id"]: q for q in QUESTIONS}
    for qid, val in (answers or {}).items():
        q = qmap.get(qid)
        if not q:
            continue
        vals = val if isinstance(val, list) else [val]
        for v in vals:
            opt = next((o for o in q["options"] if o["value"] == v), None)
            if not opt:
                continue
            t = opt.get("tags", {})
            bag["answers"].append({"q": qid, "title": q["title"],
                                   "label": opt["label"], "tags": t})
            for k in ("dz", "wheel", "synd", "contraind"):
                for item in t.get(k, []) or []:
                    if item and item not in bag[k]:
                        bag[k].append(item)
            for item in t.get("age_dz", []) or []:
                if item and item not in bag["age_dz"]:
                    bag["age_dz"].append(item)
            if t.get("age"):
                bag["age"] = t["age"]
            if t.get("onset"):
                bag["onset"].append(t["onset"])
            if t.get("red"):
                bag["red"].append(opt["label"])
            if t.get("red_partial"):
                bag["red_partial"] = True
            if t.get("laterality"):
                bag["laterality"] = t["laterality"]
            if t.get("tongue"):
                bag["tongue"] = t["tongue"]
    return bag


def _west(dz):
    """中医病种 → 西医对应名（未收录时返回原病种名并标注待核）"""
    return DZ_WESTERN.get(dz, f"{dz}（西医对应名待专科确认）")


def _vote(items):
    """计数投票，返回 [(key, count)] 降序"""
    c = {}
    for it in items:
        c[it] = c.get(it, 0) + 1
    return sorted(c.items(), key=lambda x: -x[1])


# ---------- 主引擎 ----------
def analyze(answers: dict):
    bag = _collect(answers)
    conclusions = []
    used_classic = set()   # 已被引用的古籍条文（避免多条结论重复引用同一段）

    # ===== 第 0 步：红线优先 =====
    if bag["red"]:
        dz_red = [d for d in bag["dz"] if d in RED_GUIDE] or ["暴盲"]
        guide = RED_GUIDE.get(dz_red[0], "立即眼科急诊")
        west_red = _west(dz_red[0])
        ev = LIB.search([dz_red[0]], top_k=2) if dz_red else []
        conclusions.append({
            "title": f"⛔ 红线预警：须立即就医，终止辨证（疑似：{dz_red[0]} / 西医：{west_red}）",
            "level": "C",
            "body": (f"您选择的「{' / '.join(bag['red'])}」属于中医眼科红线征象。"
                     f"疑似：{dz_red[0]}（西医对应：{west_red}）。"
                     f"处置：{guide}。中医辨证不作急救替代，请先到眼科急诊。"),
            "evidence": ev,
            "source": "local",
        })
        # 红线状态下仍给出通用 A 级调护与提醒（不涉药、不替代急救）
        care_red = build_daily_care({"dz": "", "syndrome": ""}, bag)
        care_red["blocks"].insert(0, {
            "id": "emergency", "icon": "🚨", "level": "C",
            "title": "先急诊，调护从缓",
            "items": [{"text": guide + "；在就医前后避免揉眼、压迫眼球、自行点眼药与热敷。",
                       "note": "", "evidence": []}],
        })
        enrich_all(conclusions, care_red)
        return {"red_flag": True,
                "summary": {"dz": dz_red[0], "dz_western": west_red,
                            "dz_candidates": dz_red[:3], "dz_candidates_detail": [],
                            "age_label": AGE_INFO.get(bag["age"], {}).get("label", "未提供")},
                "conclusions": conclusions,
                "daily_care": care_red,
                "bibliography": build_bibliography(
                    {"conclusions": conclusions, "daily_care": care_red}),
                "answers": bag["answers"],
                "disclaimer": DISCLAIMER}

    # ===== 第 1 步：主症 → 病种候选（年龄区间作弱权重补充，追加在末位以免影响主症排序）=====
    for d in bag.get("age_dz", []):
        if d not in bag["dz"]:
            bag["dz"].append(d)
    dz_vote = _vote(bag["dz"])
    # 同分时，优先该年龄段的常见眼病（年龄只作平局裁决，不压过主症）
    age_dz = bag.get("age_dz", [])
    dz_vote = sorted(dz_vote, key=lambda kv: (-kv[1], 0 if kv[0] in age_dz else 1))
    dz_main = dz_vote[0][0] if dz_vote else "视瞻昏渺"
    dz_candidates = [d for d, _ in dz_vote[:3]]
    # 鉴别候选同时给出西医对应，便于与西医病名对照就诊
    dz_candidates_detail = [
        {"dz": d, "western": _west(d), "score": s} for d, s in dz_vote[:3]
    ]
    cand_txt = "；".join(f"{d}（{_west(d)}）" for d in dz_candidates)
    west = _west(dz_main)
    blk = LIB.get_disease_block(dz_main)
    ev_dz = LIB.search([dz_main], top_k=2)
    if blk:
        ev_dz.insert(0, {"file": blk["file"], "section": dz_main,
                         "line": blk["line"], "text": blk["text"][:420], "score": 99})
    # ② 五轮先算出来，供古籍条文挂接使用
    wheel_key = bag["wheel"][0] if bag["wheel"] else "kidney"
    w = WHEEL_MAP.get(wheel_key, WHEEL_MAP["kidney"])
    conclusions.append({
        "title": f"① 病种方向：{dz_main}（西医对应：{west}）",
        "level": "B",
        "body": f"依据主症与病程，最贴近的中医眼科病种为「{dz_main}」（西医对应：{west}）。"
                f"鉴别候选（含西医对应）：{cand_txt}。"
                f"以上为中医病种层面的鉴别方向，具体诊断须由眼科专科检查"
                f"（视力、眼压、裂隙灯、眼底/OCT）确认，两个体系病名并非一一对应。",
        "evidence": ev_dz,
        "source": "local",
    })
    attach_classic(conclusions[-1],
                   _classic_keys(DZ_CLASSIC_KEYS.get(dz_main),
                                 WHEEL_CLASSIC_KEYS.get(w["wheel"])),
                   used_classic, top_k=2)

    # ===== 第 2 步：五轮定位 =====
    ev_w = LIB.search(["五轮", w["wheel"]], top_k=2)
    conclusions.append({
        "title": f"② 五轮定位：{w['wheel']}（属{w['zang']}）",
        "level": "B",
        "body": f"病位在{w['wheel']}，脏腑责之于{w['zang']}。{w['wheel']}常见病：{w['disease']}。"
                f"五轮辨证先定位、再定脏腑虚实寒热。",
        "evidence": ev_w,
        "source": "local",
    })
    attach_classic(conclusions[-1],
                   _classic_keys(WHEEL_CLASSIC_KEYS.get(w["wheel"]), ["五轮"]),
                   used_classic, top_k=2)

    # ===== 第 3~4 步：八纲定性 + 落证（舌象权重最高）=====
    score = {}
    def add(k, w_):
        score[k] = score.get(k, 0) + w_
    # 主症证候 权重2；全身症权重3；舌象权重4；诱因权重2；起病权重1
    for a in bag["answers"]:
        t = a["tags"]
        if not t.get("synd"):
            continue
        # 主症（局部病机）与舌象同级，并额外 +0.5 保证同分时以主症为准
        if a["q"] == "q1":
            wt = 4.0
        elif a["q"] == "q6":
            wt = 3
        elif a["q"] == "q7":
            wt = 4
        elif a["q"] == "q8":
            wt = 2
        else:
            wt = 1
        for s in t["synd"]:
            add(s, wt)
            if a["q"] == "q1":
                add(s, 0.5)
    # 起病缓急：急骤偏实，缓慢偏虚
    onset = bag["onset"][0] if bag["onset"] else None
    if onset == "sudden":
        for s in ("wind_heat", "liver_fire", "blood_stasis"):
            if s in score:
                add(s, 1)
    elif onset == "chronic":
        for s in ("liver_kidney_yin_def", "qi_blood_def", "yang_def"):
            if s in score:
                add(s, 1)
    if not score:
        score["liver_kidney_yin_def"] = 1  # 缺省：内障最常见
    ranked = sorted(score.items(), key=lambda x: -x[1])
    synd_key = ranked[0][0]
    synd = SYND_FORMULA[synd_key]
    bag["synd_key"] = synd_key
    ev_s = LIB.search([synd["name"], "内障辨证"], top_k=2)
    tongue_txt = f"舌象：{bag['tongue']}；" if bag["tongue"] else ""
    onset_txt = {"sudden": "急骤", "subacute": "数天加重",
                 "chronic": "缓慢", "recurrent": "反复发作"}.get(onset, "未明确")
    conclusions.append({
        "title": f"③ 证型判断：{synd['name']}（{synd['nature']}）",
        "level": "B",
        "body": f"{tongue_txt}起病：{onset_txt}；{'单眼' if bag['laterality']=='one' else '双眼' if bag['laterality']=='both' else '侧别' + (bag['laterality'] or '未明确')}。"
                f"按八纲定性为「{synd['nature']}」。次选证型："
                f"{'、'.join(SYND_FORMULA[k]['name'] for k, _ in ranked[1:3]) or '无'}。"
                f"证名须由医师结合舌脉与专科检查最终确定。",
        "evidence": ev_s,
        "source": "local",
    })
    attach_classic(conclusions[-1],
                   _classic_keys(SYND_CLASSIC_KEYS.get(synd_key),
                                 WHEEL_CLASSIC_KEYS.get(w["wheel"])),
                   used_classic, top_k=2)

    # ===== 第 5 步：立法 → 候选方（B 级）=====
    ev_f = LIB.search(synd["formulas"][:2], top_k=2)
    conclusions.append({
        "title": f"④ 治法方向：{synd['method']}",
        "level": "B",
        "body": f"代表方（须医师面诊定夺，非自行处方）：{'、'.join(synd['formulas'])}。"
                f"关键药群：{'、'.join(synd['herbs'])}。同类方取舍以辨证要点为准。",
        "evidence": ev_f,
        "source": "local",
    })
    attach_classic(conclusions[-1],
                   _classic_keys(SYND_CLASSIC_KEYS.get(synd_key),
                                 ["治", "药", "补泻", "君臣佐使"]),
                   used_classic, top_k=1)

    # ===== 第 6 步：涉药四关 / 安全警示 =====
    if bag["contraind"]:
        for ckey in bag["contraind"]:
            c = CONTRAIND_MAP.get(ckey)
            if not c:
                continue
            ev_c = LIB.search([c["ref"].split(" ")[0], ckey if ckey == "青光眼" else c["title"]], top_k=1)
            conclusions.append({
                "title": f"⑤ 用药安全警示：{c['title']}",
                "level": "B",
                "body": c["alert"] + f"（依据：{c['ref']}）",
                "evidence": ev_c or [{"file": c["ref"], "section": "安全表", "line": 0,
                                      "text": c["alert"], "score": 0}],
                "source": "local",
            })
    # 通用红线（点眼药禁自制 / 有创外治禁自行）
    ev_safe = LIB.search(["点眼药", "严禁指导自制", "有创外治", "绝对禁自行"], top_k=2)
    conclusions.append({
        "title": "⑤ 通用安全红线",
        "level": "B",
        "body": "点眼药/眼用散剂（炉甘石、硼砂、冰片类）严禁自制，只可由医师开具正规制剂；"
                "针刺、穴位注射、针拨内障等有创外治绝对禁自行；"
                "眼区危险穴（睛明、承泣、球后）家庭不按压、禁灸。",
        "evidence": ev_safe,
        "source": "local",
    })

    # ===== A 级日常调理 + 定时提醒（模块化，每条建议均带依据）=====
    care = build_daily_care(
        {"dz": dz_main, "dz_western": west, "syndrome": synd["name"],
         "synd_key": synd_key, "wheel": w["wheel"]}, bag)
    ev_care = []
    for b in care["blocks"][:3]:
        for it in b["items"][:1]:
            for e in it.get("evidence", []):
                if e not in ev_care:
                    ev_care.append(e)
    if not ev_care:
        ev_care = LIB.search(["调护", "远眺运目", "忌口", "眼保健操"], top_k=2)
    n_items = sum(len(b["items"]) for b in care["blocks"])
    conclusions.append({
        "title": f"⑥ 日常调理建议（A 级可执行清单 · 共 {n_items} 条）",
        "level": "A",
        "body": ("按本次证型与病种生成的日常调理清单详见下方「日常调理建议」专区："
                 "用眼节律、穴位保健、饮食食疗、起居情志、外治热敷、病种专属调护。"
                 f"核心节律——每连续用眼 {care['work_minutes']} 分钟，起身休息 "
                 f"{care['reminder']['rest_minutes']} 分钟（闭目 1 分钟 → 远眺 6 米外 3~5 分钟 → 运目 → 熨目）。"
                 "可在本页开启护眼定时器自动提醒。"),
        "evidence": ev_care[:4],
        "source": "local",
    })

    # ===== 年龄区间相关提示（眼病谱 / 筛查节奏 / 用药注意）=====
    if bag["age"]:
        ai = AGE_INFO.get(bag["age"])
        if ai:
            ev_a = LIB.search(ai["keys"][:2], top_k=2)
            conclusions.append({
                "title": f"⑦ 年龄相关提示：{ai['label']}",
                "level": "A",
                "body": (f"该年龄段常见眼病：{ai['spectrum']}。"
                         f"调护侧重：{ai['focus']}。"
                         f"筛查节奏：{ai['screen']}。"
                         f"用药注意：{ai['med']}"),
                "evidence": ev_a,
                "source": "local",
            })

    # ===== 就医建议 =====
    conclusions.append({
        "title": "⑧ 就医与升级信号",
        "level": "C",
        "body": (f"建议携带本次报告至眼科/中医眼科就诊，重点确认：{west}的专科检查与分期。"
                 "出现以下任一情况立即急诊：视力骤降或丧失；眼胀痛伴头痛呕吐、虹视、瞳神散大；"
                 "眼外伤/化学伤；黑影骤增伴闪光感（疑视网膜脱离）；小儿瞳神发白夜盲。"
                 "已确诊者中医辨证仅作辅助，不得据此停用西药（尤其降眼压药、激素眼液、降糖降压药）。"),
        "evidence": LIB.search(["红线总览", "立即眼科急诊"], top_k=1),
        "source": "local",
    })

    # ===== 古籍经典佐证（专查 08 条文层：内经 / 银海精微 / 原机启微 / 审视瑶函 等）=====
    # 注意：此处 enrich_all 尚未执行，cited 字段还不存在，
    # 因此直接用 extract_books（正文书名号 + 章节归属书名）抽取真实书名。
    hits = LIB.search_classic([dz_main, synd["name"], w["wheel"]], top_k=8) \
        or LIB.search_classic(CLASSIC_FALLBACK_KEYS, top_k=8)
    # 优先取尚未被前面结论引用的条文，不足时再补已用过的（⑨ 是经典佐证专区，允许重引）
    fresh = [e for e in hits if (e.get("file"), e.get("line")) not in used_classic]
    ev_cls = (fresh + [e for e in hits if (e.get("file"), e.get("line")) in used_classic])[:3]
    for e in ev_cls:
        used_classic.add((e.get("file"), e.get("line")))
        e["is_classic"] = True
    if ev_cls:
        cls_names, cls_src = [], []
        for e in ev_cls:
            # 书名：正文书名号优先，其次该段落所属章节的书目（08 的章节标题均带书名号）
            books = extract_books(e.get("text", ""), e.get("book", ""))
            for b in books:
                if b.get("kind") == "古籍":
                    cls_names.append(b["name"])
                    cls_src.append(f"{b['name']}（{e.get('section') or '眼科经典条文'}）")
            e["cited_pre"] = books
        cls_names = list(dict.fromkeys(cls_names))
        cls_src = list(dict.fromkeys(cls_src))[:4]
        conclusions.append({
            "title": "⑨ 古籍经典佐证",
            "level": "A",
            "body": (f"下列条文出自中医眼科经典"
                     f"（{'、'.join(cls_names) if cls_names else '《黄帝内经》《银海精微》《原机启微》《审视瑶函》等'}），"
                     f"为本次「{dz_main} · {synd['name']}」的病机与治则提供经典依据。"
                     + (f"具体出处：{'；'.join(cls_src)}。" if cls_src else "")
                     + "古籍条文仅作理论溯源，古代剂量与配伍不作为用药依据。"),
            "evidence": ev_cls,
            "source": "classic",
        })

    # ===== 为每条依据标注出处（古籍 / 文献 / 教材），并汇总引用书目 =====
    enrich_all(conclusions, care)

    return {
        "red_flag": False,
        "summary": {
            "dz": dz_main, "dz_western": west, "dz_candidates": dz_candidates,
            "dz_candidates_detail": dz_candidates_detail,
            "wheel": w["wheel"], "zang": w["zang"],
            "syndrome": synd["name"], "nature": synd["nature"],
            "method": synd["method"], "formulas": synd["formulas"], "herbs": synd["herbs"],
            "synd_ranking": [{"name": SYND_FORMULA[k]["name"], "score": s} for k, s in ranked[:4]],
            "synd_key": synd_key,
            "contraindications": [CONTRAIND_MAP[c]["title"] for c in bag["contraind"] if c in CONTRAIND_MAP],
            "tongue": bag["tongue"], "onset": onset, "laterality": bag["laterality"],
            "age": bag["age"], "age_label": AGE_INFO.get(bag["age"], {}).get("label", "未提供"),
        },
        "conclusions": conclusions,
        "daily_care": care,
        "bibliography": build_bibliography(
            {"conclusions": conclusions, "daily_care": care}),
        "answers": bag["answers"],
        "disclaimer": DISCLAIMER,
    }


DISCLAIMER = (
    "本报告由「眼健康自查助手」基于中医眼科知识库生成，属学习参考与就医准备材料，不构成诊断或处方。"
    "证型分析与治法方向须经执业中医师/中医眼科医师面诊（含舌脉与专科检查）确认；"
    "所有内服方药与点眼制剂均为 B 级（须医师把关），请勿自行用药。"
    "中药材剂量为教材参考值，未经《药典》校准。"
)
