# -*- coding: utf-8 -*-
# ============================================================================
# 眼健康自查助手 · 病情采集问卷（11 题：年龄 + 主症 + 十问要点）
# @author  杨博 (yangbo621@163.com)
# @license Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
#          https://creativecommons.org/licenses/by-nc/4.0/
# （详见随包 LICENSE.txt / NOTICE.md；商业使用需另行获得书面授权）
# ============================================================================

"""
眼健康自查助手 · 病情采集问卷（11 题：年龄 + 主症 + 十问要点）

设计依据（来自中医眼科技能库）：
- 问诊十问（04 总说 / 02 眼科问诊十问）
- 辨证七步骤（03）：病史 → 求因 → 五轮定位 → 病机 → 八纲定性 → 病势 → 证名
- 红线优先级（安全边界第 2 条）：红线征象立即急诊，不进辨证
- 涉药四关（人群关 / 配伍关 / 剂量关 / 性能关）

每个选项携带 tags 供规则引擎路由：
  dz        病种候选键（对应 04 病种节标题，用于检索本地库）
  wheel     五轮定位（spleen 肉轮 / heart 血轮 / lung 气轮 / liver 风轮 / kidney 水轮）
  synd      证候倾向（对应 00 索引三「证型→治法→代表方」）
  onset     起病程（sudden 急骤 / subacute 数天 / chronic 缓慢 / recurrent 反复）
  red       是否红线征象
  contraind 禁忌/人群标记（glaucoma 青光眼 / pregnancy 孕妇 / child 小儿 / elderly 老年
                          diabetes 糖尿病 / hypertension 高血压 / steroid 激素 / immuno 免疫病）
  age       年龄区间（u20 / 20_40 / 40_60 / 60_80 / 80p）
  age_dz    该年龄段常见眼病（弱权重，仅作病种候选补充）
"""

QUESTIONS = [
    {
        "id": "q0",
        "step": "基本信息·年龄",
        "title": "您的年龄区间是？",
        "hint": "不同年龄段的眼病谱与筛查、用药策略不同：青少年重近视防控，中老年重内障与眼底筛查",
        "type": "single",
        "options": [
            {"value": "u20", "label": "20 岁以下", "tags": {
                "age": "u20", "age_dz": ["能近怯远", "时复目痒", "疳积上目"],
                "contraind": ["teen"]}},
            {"value": "20_40", "label": "20～40 岁", "tags": {
                "age": "20_40", "age_dz": ["视瞻有色", "白涩症", "能近怯远"]}},
            {"value": "40_60", "label": "40～60 岁", "tags": {
                "age": "40_60", "age_dz": ["视瞻有色", "青风内障", "圆翳内障"]}},
            {"value": "60_80", "label": "60～80 岁", "tags": {
                "age": "60_80", "age_dz": ["圆翳内障", "视瞻昏渺", "青盲"],
                "contraind": ["elderly"]}},
            {"value": "80p", "label": "80 岁以上", "tags": {
                "age": "80p", "age_dz": ["圆翳内障", "视瞻昏渺"],
                "contraind": ["elderly"]}},
        ],
    },
    {
        "id": "q1",
        "step": "主症定位",
        "title": "您目前最主要、最困扰的眼部不适是什么？",
        "hint": "选最突出的一个症状（决定五轮定位与病种方向）",
        "type": "single",
        "options": [
            {"value": "red_pain", "label": "目赤肿痛、眼屎多、怕光流泪", "tags": {
                "dz": ["暴风客热", "天行赤眼", "聚星障"], "wheel": ["lung", "liver"],
                "synd": ["wind_heat"]}},
            {"value": "dry", "label": "眼干涩、异物感、少泪、易疲劳", "tags": {
                "dz": ["白涩症"], "wheel": ["lung"],
                "synd": ["lung_dry"]}},
            {"value": "blurred", "label": "视物昏花、模糊、看久易疲", "tags": {
                "dz": ["视瞻昏渺", "圆翳内障", "能近怯远"], "wheel": ["kidney"],
                "synd": ["liver_kidney_yin_def"]}},
            {"value": "floaters", "label": "眼前黑影飘动、随眼球转动", "tags": {
                "dz": ["云雾移睛"], "wheel": ["kidney"],
                "synd": ["liver_kidney_yin_def"]}},
            {"value": "metamorph", "label": "视物变形、变色、中心暗影、视物变小", "tags": {
                "dz": ["视瞻有色", "视瞻昏渺"], "wheel": ["kidney"],
                "synd": ["phlegm_damp"]}},
            {"value": "vision_loss", "label": "视力渐进下降（不伴剧痛）", "tags": {
                "dz": ["圆翳内障", "青盲"], "wheel": ["kidney"],
                "synd": ["liver_kidney_yin_def"]}},
            {"value": "itch_tear", "label": "眼痒阵作、流泪（季节性反复）", "tags": {
                "dz": ["时复目痒", "流泪症"], "wheel": ["lung", "liver"],
                "synd": ["wind_heat"]}},
            {"value": "lid_lump", "label": "眼睑红肿痛或有硬结（麦粒肿/霰粒肿）", "tags": {
                "dz": ["针眼", "胞生痰核"], "wheel": ["spleen"],
                "synd": ["damp_heat"]}},
            {"value": "night_blind", "label": "夜盲、暗处看不清、视野变窄", "tags": {
                "dz": ["高风内障", "疳积上目"], "wheel": ["kidney", "spleen"],
                "synd": ["yang_def"]}},
            {"value": "cornea_spot", "label": "黑睛星点翳障、畏光刺痛", "tags": {
                "dz": ["聚星障", "凝脂翳", "宿翳"], "wheel": ["liver"],
                "synd": ["wind_heat", "liver_fire"]}},
        ],
    },
    {
        "id": "q2",
        "step": "起病与病程",
        "title": "这个情况是何时、怎样发生的？",
        "hint": "急骤多为外邪/外伤/急症，缓慢多为虚损/内障",
        "type": "single",
        "options": [
            {"value": "sudden", "label": "突然发生（数小时~1天内）", "tags": {"onset": "sudden"}},
            {"value": "subacute", "label": "数天内逐渐加重", "tags": {"onset": "subacute"}},
            {"value": "chronic", "label": "缓慢起病，已数周或数月以上", "tags": {"onset": "chronic"}},
            {"value": "recurrent", "label": "反复发作，时好时坏", "tags": {"onset": "recurrent"}},
        ],
    },
    {
        "id": "q3",
        "step": "病位侧别",
        "title": "症状发生在一只眼还是两只眼？",
        "hint": "单眼多见于中浆、视网膜/视神经病；双眼多见于全身病、虚证、传染性红眼",
        "type": "single",
        "options": [
            {"value": "one", "label": "单眼", "tags": {"laterality": "one"}},
            {"value": "both", "label": "双眼", "tags": {"laterality": "both"}},
            {"value": "alternate", "label": "双眼先后/交替出现", "tags": {"laterality": "alternate"}},
        ],
    },
    {
        "id": "q4",
        "step": "红线排查·视力",
        "title": "视力有没有下降？程度如何？",
        "hint": "视力骤降属致盲红线，须立即眼科急诊",
        "type": "single",
        "options": [
            {"value": "none", "label": "没有明显下降", "tags": {}},
            {"value": "mild", "label": "轻度模糊，但不影响生活", "tags": {}},
            {"value": "obvious", "label": "明显下降，影响阅读/驾驶", "tags": {"red_partial": True}},
            {"value": "sudden_loss", "label": "突然骤降甚至看不见", "tags": {
                "red": True, "dz": ["暴盲"]}},
        ],
    },
    {
        "id": "q5",
        "step": "红线排查·急症",
        "title": "是否伴有以下情况？（可多选）",
        "hint": "眼胀痛伴头痛呕吐、虹视——警惕急性闭角型青光眼（绿风内障），可致不可逆失明",
        "type": "multi",
        "options": [
            {"value": "none", "label": "都没有", "tags": {}},
            {"value": "glaucoma_triad", "label": "眼胀痛伴头痛、恶心呕吐", "tags": {
                "red": True, "dz": ["绿风内障"], "synd": ["liver_yang", "liver_fire"]}},
            {"value": "halo", "label": "看灯光有彩虹圈（虹视）", "tags": {
                "red": True, "dz": ["绿风内障"]}},
            {"value": "mydriasis", "label": "瞳孔散大、对光反应迟钝", "tags": {
                "red": True, "dz": ["绿风内障"]}},
            {"value": "trauma", "label": "眼部外伤、化学溅入、异物入目", "tags": {
                "red": True, "dz": ["撞击伤目", "真睛破损", "异物入目", "化学伤"]}},
            {"value": "child_leukocoria", "label": "小儿瞳孔区发白、夜盲、畏光揉眼", "tags": {
                "red": True, "dz": ["疳积上目"], "contraind": ["child"]}},
        ],
    },
    {
        "id": "q6",
        "step": "全身兼症（定性关键）",
        "title": "除眼部外，还有哪些全身表现？（可多选）",
        "hint": "用于八纲定性：辨寒热、虚实、气血津液",
        "type": "multi",
        "options": [
            {"value": "none", "label": "无明显全身不适", "tags": {}},
            {"value": "liver_fire", "label": "口苦、咽干、易怒、胁胀、便秘尿黄", "tags": {
                "synd": ["liver_fire"]}},
            {"value": "yin_def", "label": "头晕耳鸣、腰膝酸软、失眠多梦、五心烦热", "tags": {
                "synd": ["liver_kidney_yin_def"]}},
            {"value": "qi_blood_def", "label": "倦怠乏力、面色无华、心悸气短、视久易疲", "tags": {
                "synd": ["qi_blood_def"]}},
            {"value": "damp", "label": "头昏胸闷、身体困重、口黏、痰多", "tags": {
                "synd": ["phlegm_damp"]}},
            {"value": "yang_def", "label": "畏寒肢冷、形寒、夜尿多、五更泻", "tags": {
                "synd": ["yang_def"]}},
            {"value": "stasis", "label": "刺痛固定、唇暗、肢体麻木、术后/外伤后", "tags": {
                "synd": ["blood_stasis"]}},
        ],
    },
    {
        "id": "q7",
        "step": "舌象（定性关键）",
        "title": "您的舌象大致是哪种？",
        "hint": "自然光下对镜观察，晨起未进食最准；舌象是虚实用药的关键依据",
        "type": "single",
        "options": [
            {"value": "red_yellow", "label": "舌红、苔黄（或黄腻）", "tags": {
                "synd": ["liver_fire", "damp_heat"], "tongue": "红/黄"}},
            {"value": "red_less", "label": "舌红、少苔或无苔", "tags": {
                "synd": ["liver_kidney_yin_def", "lung_dry"], "tongue": "红/少苔"}},
            {"value": "pale_white", "label": "舌淡、苔白", "tags": {
                "synd": ["qi_blood_def", "yang_def"], "tongue": "淡/白"}},
            {"value": "dark_stasis", "label": "舌暗、有瘀点瘀斑", "tags": {
                "synd": ["blood_stasis"], "tongue": "暗/瘀点"}},
            {"value": "swollen_greasy", "label": "舌体胖大、边有齿痕、苔腻", "tags": {
                "synd": ["phlegm_damp", "spleen_def_damp"], "tongue": "胖/腻"}},
            {"value": "unknown", "label": "不清楚", "tags": {"tongue": "未提供"}},
        ],
    },
    {
        "id": "q8",
        "step": "诱因审求",
        "title": "可能的诱发或加重因素是什么？",
        "hint": "审证求因：外感、劳倦、情志、外伤、全身病",
        "type": "multi",
        "options": [
            {"value": "none", "label": "无明显诱因", "tags": {}},
            {"value": "exogenous", "label": "感冒/受风热之后出现", "tags": {
                "synd": ["wind_heat"]}},
            {"value": "overuse", "label": "熬夜、长时间看屏幕、用眼过度", "tags": {
                "synd": ["liver_kidney_yin_def", "qi_blood_def"]}},
            {"value": "emotion", "label": "情绪波动、郁怒、压力大", "tags": {
                "synd": ["liver_fire", "liver_yang"]}},
            {"value": "trauma_hx", "label": "眼部外伤或手术后", "tags": {
                "synd": ["blood_stasis"]}},
            {"value": "seasonal", "label": "特定季节/花粉粉尘环境发作", "tags": {
                "synd": ["wind_heat"], "dz": ["时复目痒"]}},
        ],
    },
    {
        "id": "q9",
        "step": "既往病史（用药禁忌）",
        "title": "您有以下哪些病史？（可多选）",
        "hint": "直接决定用药红线，尤其青光眼禁用扩瞳类中药",
        "type": "multi",
        "options": [
            {"value": "none", "label": "都没有", "tags": {}},
            {"value": "glaucoma", "label": "青光眼 / 高眼压", "tags": {
                "contraind": ["glaucoma"]}},
            {"value": "diabetes", "label": "糖尿病", "tags": {
                "contraind": ["diabetes"], "dz": ["消渴目病"]}},
            {"value": "hypertension", "label": "高血压", "tags": {
                "contraind": ["hypertension"], "dz": ["高血压眼底"]}},
            {"value": "immuno", "label": "自身免疫病（干燥综合征、类风湿、白塞等）", "tags": {
                "contraind": ["immuno"]}},
            {"value": "thyroid", "label": "甲状腺疾病", "tags": {
                "contraind": ["immuno"]}},
        ],
    },
    {
        "id": "q10",
        "step": "人群与在用药物",
        "title": "您属于以下哪类人群 / 正在用哪些药？（可多选）",
        "hint": "妊娠分级与西药冲突是硬约束，须医师把关",
        "type": "multi",
        "options": [
            {"value": "none", "label": "无特殊", "tags": {}},
            {"value": "pregnancy", "label": "孕妇 / 备孕 / 哺乳期", "tags": {
                "contraind": ["pregnancy"]}},
            {"value": "child", "label": "12 岁以下儿童", "tags": {
                "contraind": ["child"]}},
            {"value": "elderly", "label": "65 岁以上老人", "tags": {
                "contraind": ["elderly"]}},
            {"value": "steroid", "label": "正在使用激素类眼药水 / 口服或注射激素", "tags": {
                "contraind": ["steroid"]}},
            {"value": "iop_drug", "label": "正在使用降眼压药", "tags": {
                "contraind": ["glaucoma"]}},
            {"value": "anticoag", "label": "正在使用抗凝/抗血小板药（阿司匹林、华法林等）", "tags": {
                "contraind": ["bleeding"]}},
        ],
    },
]

# 证型 → 治法 → 代表方 → 药群（源自 00-眼科证治总索引 第三节，确保查表不凭记忆）
SYND_FORMULA = {
    "wind_heat": {
        "name": "风热犯目",
        "method": "疏风清热",
        "formulas": ["银翘散", "桑菊饮", "新制柴连汤"],
        "herbs": ["桑叶", "菊花", "薄荷", "蝉蜕", "木贼", "谷精草"],
        "nature": "实·热",
    },
    "liver_fire": {
        "name": "肝胆实火 / 肝火上炎",
        "method": "清肝泻火",
        "formulas": ["龙胆泻肝汤", "泻青丸", "石决明散"],
        "herbs": ["龙胆草", "栀子", "黄芩", "夏枯草", "决明子", "密蒙花"],
        "nature": "实·热",
    },
    "lung_dry": {
        "name": "肺经燥热 / 肺阴不足",
        "method": "润燥清肺",
        "formulas": ["桑杏汤", "养阴清肺汤", "桑白皮汤"],
        "herbs": ["沙参", "麦冬", "玄参", "生地", "桑叶"],
        "nature": "虚·燥",
    },
    "liver_kidney_yin_def": {
        "name": "肝肾阴虚",
        "method": "滋补肝肾明目",
        "formulas": ["杞菊地黄丸", "明目地黄丸", "石斛夜光丸", "驻景丸"],
        "herbs": ["枸杞", "菊花", "熟地", "石斛", "菟丝子", "女贞子"],
        "nature": "虚",
    },
    "qi_blood_def": {
        "name": "气血两虚",
        "method": "益气养血明目",
        "formulas": ["八珍汤", "归脾汤", "益气聪明汤"],
        "herbs": ["党参", "黄芪", "当归", "白芍"],
        "nature": "虚",
    },
    "yang_def": {
        "name": "脾肾阳虚",
        "method": "温补脾肾",
        "formulas": ["右归丸", "金匮肾气丸"],
        "herbs": ["熟地", "山萸肉", "肉桂", "附子", "夜明砂"],
        "nature": "虚·寒",
    },
    "phlegm_damp": {
        "name": "痰湿 / 水湿内停",
        "method": "利水渗湿化痰",
        "formulas": ["猪苓散", "温胆汤"],
        "herbs": ["茯苓", "泽泻", "半夏", "陈皮", "车前子"],
        "nature": "实·湿",
    },
    "spleen_def_damp": {
        "name": "脾虚湿困",
        "method": "健脾利湿",
        "formulas": ["六君子汤", "参苓白术散"],
        "herbs": ["党参", "白术", "茯苓", "陈皮", "山药"],
        "nature": "虚·湿",
    },
    "damp_heat": {
        "name": "脾胃 / 肝胆湿热",
        "method": "清热除湿",
        "formulas": ["除湿汤", "龙胆泻肝汤"],
        "herbs": ["黄芩", "黄连", "龙胆草", "茵陈"],
        "nature": "实·湿热",
    },
    "blood_stasis": {
        "name": "血瘀阻络",
        "method": "活血化瘀通窍",
        "formulas": ["桃红四物汤", "血府逐瘀汤", "通窍活血汤", "除风益损汤"],
        "herbs": ["丹参", "红花", "桃仁", "牛膝", "茺蔚子", "三七"],
        "nature": "实·瘀",
    },
    "liver_yang": {
        "name": "肝阳上亢",
        "method": "平肝潜阳",
        "formulas": ["天麻钩藤饮"],
        "herbs": ["石决明", "牡蛎", "天麻", "钩藤"],
        "nature": "本虚标实",
    },
}

# 五轮 → 脏腑 → 常见病（源自 01 五轮学说）
WHEEL_MAP = {
    "spleen": {"wheel": "肉轮", "zang": "脾（胃）", "disease": "针眼、胞生痰核、睑弦赤烂、上胞下垂"},
    "heart": {"wheel": "血轮", "zang": "心（小肠）", "disease": "赤脉传睛、漏睛、流泪症"},
    "lung": {"wheel": "气轮", "zang": "肺（大肠）", "disease": "暴风客热、天行赤眼、白涩症、时复目痒、火疳"},
    "liver": {"wheel": "风轮", "zang": "肝（胆）", "disease": "聚星障、凝脂翳、花翳白陷、宿翳"},
    "kidney": {"wheel": "水轮", "zang": "肾（命门）", "disease": "绿风/青风内障、圆翳内障、云雾移睛、视瞻有色、视瞻昏渺、青盲、高风内障"},
}

# 禁忌标记 → 安全提示（源自 安全-眼科用药与外治安全）
CONTRAIND_MAP = {
    "glaucoma": {
        "title": "青光眼 / 高眼压",
        "alert": "绝对禁用一切扩瞳倾向药：青葙子、洋金花（曼陀罗）；含青葙子成方（石决明散、石斛夜光丸）一律回避",
        "ref": "安全-眼科用药与外治安全.md 一·1",
    },
    "pregnancy": {
        "title": "孕妇 / 备孕 / 哺乳期",
        "alert": "活血破瘀药（桃仁、红花、牛膝、三棱莪术）禁用；辛温走窜（细辛）、重镇药慎用；合谷穴不宜按压",
        "ref": "安全-眼科用药与外治安全.md 二",
    },
    "teen": {
        "title": "20 岁以下（儿童青少年）",
        "alert": "剂量按年龄体重折算，须儿科/眼科医师定夺；扩瞳类中药（如青葙子）尤须谨慎；"
                 "近视以验光配镜与行为干预为主，不夸大『治愈近视』",
        "ref": "04 九·能近怯远 / 安全-眼科用药与外治安全 人群关",
    },
    "child": {
        "title": "12 岁以下儿童",
        "alert": "疳积上目须同时补维生素A并按急症处理；剂量按年龄体重折算，须儿科/眼科医师定夺",
        "ref": "04 七·33 疳积上目",
    },
    "elderly": {
        "title": "65 岁以上",
        "alert": "内障虚证方长期服须脾胃耐受（熟地滋腻、金石贝壳碍胃），宜佐健脾；金石类（朱砂、磁石）不宜久服",
        "ref": "06 眼科使用注意铁律 1/3",
    },
    "diabetes": {
        "title": "糖尿病",
        "alert": "警惕消渴目病（糖尿病视网膜病变）；西医眼底激光/抗VEGF为要，中医辅助控糖护网",
        "ref": "04 七·34 消渴目病",
    },
    "hypertension": {
        "title": "高血压",
        "alert": "重在控血压，西药不可擅停；补阳还五汤等升提活血方慎用（脑充血/高血压慎用）",
        "ref": "04 七·35 / 06 四",
    },
    "steroid": {
        "title": "正在使用激素",
        "alert": "激素可诱发或加重中心性浆液性脉络膜视网膜病变（中浆）并升高眼压；务必告知开方医师，切勿自行停药",
        "ref": "安全-眼科用药与外治安全（就医沟通单·用药史）",
    },
    "immuno": {
        "title": "自身免疫病",
        "alert": "顽固干眼/巩膜炎须排查干燥综合征、白塞等结缔组织病；火疳反复须查风湿免疫",
        "ref": "04 三·15 火疳 / 八·41 神水将枯",
    },
    "bleeding": {
        "title": "使用抗凝/抗血小板药",
        "alert": "活血破瘀方（通窍活血汤、桃红四物汤重剂）有出血倾向者慎用，须与医师确认相互作用",
        "ref": "06 眼科使用注意铁律 4",
    },
}
