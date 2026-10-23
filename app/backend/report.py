# -*- coding: utf-8 -*-
# ============================================================================
# 眼健康自查助手 · 后端模块 · 报告渲染与落盘（第四步：格式化结果 + 列出每个结论的依据/参考资料）
# @author  杨博 (yangbo621@163.com)
# @license Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
#          https://creativecommons.org/licenses/by-nc/4.0/
# （详见随包 LICENSE.txt / NOTICE.md；商业使用需另行获得书面授权）
# ============================================================================

"""
报告渲染与落盘（第四步：格式化结果 + 列出每个结论的依据/参考资料）
产出：Markdown 与 HTML 两份文件，保存到 reports/ 目录
"""

import os
import re
import threading
from datetime import datetime
from pathlib import Path

REPORT_DIR = Path(os.environ.get("EYE_REPORT_DIR", "").strip() or
                  (Path(__file__).resolve().parent.parent / "reports"))
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# 多人并发时 protect：文件名分配与写入都在这把锁内串行，避免同秒撞名、内容交错写坏
_REPORT_LOCK = threading.Lock()


def _atomic_write(path: Path, text: str):
    """先写临时文件再原子替换：并发下载不会读到写了一半的报告"""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass

LEVEL_LABEL = {"A": "A 级 · 可直接执行", "B": "B 级 · 须医师把关", "C": "C 级 · 医疗升级/转诊"}
LEVEL_ICON = {"A": "✅", "B": "⚠️", "C": "🏥"}


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ev_cls(e):
    """经典原文（古籍条文）用独立样式突出"""
    return "ev evc" if e.get("is_classic") else "ev"


def _ev_tag(e):
    """依据的出处标签：📜 经典原文 + 【类别】书名/文献名"""
    if not e.get("cite_label"):
        return ""
    mark = "📜 " if e.get("is_classic") else ""
    return f"{mark}【{e.get('src_kind','')}】{e.get('cite_label')}"


def _ev_loc(e, with_kind=True):
    """依据的出处行：古籍/文献名 + 文件·章节·行号"""
    src = f"`{e.get('file','')}`" + (f" · {e.get('section')}" if e.get("section") else "") \
          + (f" · 第{e.get('line')}行" if e.get("line") else "")
    if not with_kind:
        return src
    kind = e.get("src_kind", "")
    mark = "📜 " if e.get("is_classic") else ""
    return f"**{mark}【{kind}】{e.get('cite_label','')}** — {src}"


def _render_care_md(care: dict) -> list:
    if not care:
        return []
    out = ["<details open>\n<summary>日常调理建议（A 级 · 可直接执行）　—　已展开 · 点击收起</summary>\n"]
    for b in care.get("blocks", []):
        out.append(f"### {b.get('icon','')} {b['title']}　`{LEVEL_LABEL.get(b.get('level','A'))}`\n")
        for it in b.get("items", []):
            out.append(f"- {it['text']}")
            if it.get("note"):
                out.append(f"  - 备注：{it['note']}")
            for e in (it.get("evidence") or []):
                out.append(f"  - 依据 {_ev_loc(e)}：{_esc(e.get('text','')).replace(chr(10),' ')[:180]}")
        if b.get("note"):
            out.append(f"\n> {b['note']}\n")
    r = care.get("reminder", {})
    if r:
        out.append("\n### ⏰ 用眼节律与随访打卡\n")
        out.append(f"- **用眼节律**：每 {r.get('work_minutes')} 分钟工作 → 休息 {r.get('rest_minutes')} 分钟\n")
        for i, s in enumerate(r.get("rest_steps", []), 1):
            out.append(f"  {i}. （{s['t']}秒）{s['text']}")
        out.append("\n**每日打卡清单**\n")
        out.append("| 时段 | 事项 | 说明 |")
        out.append("|---|---|---|")
        for c in r.get("daily_checklist", []):
            out.append(f"| {c['time']} | {c['task']} | {c.get('note','')} |")
        out.append("\n**复查随访**\n")
        for f in r.get("followups", []):
            out.append(f"- {f['name']}：{f['cycle']}（{f.get('note','')}）")
        out.append("")
    out.append("</details>\n")
    return out


def _render_care_html(care: dict) -> list:
    if not care:
        return []
    out = ["<details class='sec' open><summary>日常调理建议（A 级 · 可直接执行）"
           "<span class='cnt'>已展开 · 点击收起</span></summary><div class='sec-body'>"]
    for b in care.get("blocks", []):
        lv = b.get("level", "A")
        out.append(f"<div class='card'><h3>{b.get('icon','')} {_esc(b['title'])}"
                   f"<span class='badge {lv}'>{LEVEL_LABEL.get(lv, lv)}</span></h3><ul>")
        for it in b.get("items", []):
            out.append(f"<li>{_esc(it['text'])}")
            if it.get("note"):
                out.append(f"<div class='src'>备注：{_esc(it['note'])}</div>")
            for e in (it.get("evidence") or []):
                loc = f"{e.get('file','')}" + (f" · {e.get('section','')}" if e.get("section") else "") \
                      + (f" · 第{e.get('line')}行" if e.get("line") else "")
                tag = _ev_tag(e)
                out.append(f"<div class='{_ev_cls(e)}'><b>{_esc(tag)}</b><div class='src'>{_esc(loc)}</div>"
                           f"<div class='src'>{_esc(e.get('text',''))[:220]}</div></div>")
            out.append("</li>")
        out.append("</ul>")
        if b.get("note"):
            out.append(f"<p class='src'>{_esc(b['note'])}</p>")
        out.append("</div>")
    r = care.get("reminder", {})
    if r:
        out.append("<h2>⏰ 用眼节律与随访打卡</h2>")
        out.append(f"<div class='card'><h3>用眼节律：每 {r.get('work_minutes')} 分钟 → 休息 "
                   f"{r.get('rest_minutes')} 分钟</h3><ol>")
        for s in r.get("rest_steps", []):
            out.append(f"<li>（{s['t']} 秒）{_esc(s['text'])}</li>")
        out.append("</ol></div>")
        out.append("<div class='card'><h3>每日打卡清单</h3><table>"
                   "<tr><th>时段</th><th>事项</th><th>说明</th></tr>")
        for c in r.get("daily_checklist", []):
            out.append(f"<tr><td>{_esc(c['time'])}</td><td>{_esc(c['task'])}</td>"
                       f"<td>{_esc(c.get('note',''))}</td></tr>")
        out.append("</table></div>")
        out.append("<div class='card'><h3>复查随访</h3><ul>")
        for f in r.get("followups", []):
            out.append(f"<li><b>{_esc(f['name'])}</b>：{_esc(f['cycle'])}"
                       f"<div class='src'>{_esc(f.get('note',''))}</div></li>")
        out.append("</ul></div>")
    out.append("</div></details>")
    return out


def _render_bib_md(bib: list) -> list:
    if not bib:
        return []
    out = ["<details>\n<summary>引用古籍与文献一览　—　共 %d 条 · 点击展开 / 收起</summary>\n" % len(bib),
           "> 本节自动汇总本报告各条结论实际引用到的古籍与现代文献"
           "（含朝代作者、性质、命中次数与示例出处位置），便于核对与进一步查阅。\n"]
    out.append("| 类别 | 古籍 / 文献 | 朝代·作者 | 被引 | 出处示例 |")
    out.append("|---|---|---|---|---|")
    for b in bib:
        locs = "；".join(f"`{l}`" for l in b.get("locs", [])[:2])
        desc = b.get("desc") or ""
        out.append(f"| {b['kind']} | **{b['name']}** | {b.get('author','') or '—'} | "
                   f"{b['count']} 处 | {locs}")
        if desc:
            out.append(f"| | ↳ {desc} | | | |")
    out.append("")
    out.append("</details>\n")
    return out


def _render_bib_html(bib: list) -> list:
    if not bib:
        return []
    out = ["<details class='sec'><summary>引用古籍与文献一览"
           "<span class='cnt'>共 %d 条 · 点击展开 / 收起</span></summary><div class='sec-body'>" % len(bib),
           "<p class='src' style='margin:-6px 0 14px'>自动汇总本报告各条结论实际引用到的古籍与现代文献，"
           "含朝代作者、性质、被引次数与出处示例。</p>",
           "<table><tr><th>类别</th><th>古籍 / 文献</th><th>朝代·作者</th><th>被引</th><th>出处示例</th></tr>"]
    for b in bib:
        locs = "<br>".join(_esc(l) for l in b.get("locs", [])[:2])
        desc = (f"<div class='src'>{_esc(b['desc'])}</div>" if b.get("desc") else "")
        out.append(f"<tr><td>{_esc(b['kind'])}</td><td><b>{_esc(b['name'])}</b>{desc}</td>"
                   f"<td>{_esc(b.get('author','') or '—')}</td><td>{b['count']} 处</td>"
                   f"<td class='src'>{locs}</td></tr>")
    out.append("</table></div></details>")
    return out


def render_markdown(result: dict) -> str:
    s = result.get("summary", {})
    lines = []
    lines.append("# 眼健康自查助手 · 辨证咨询报告\n")
    lines.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    if result.get("record_kind") == "ip":
        lines.append("档案：未建档，本次报告不可查询\n")
    elif result.get("phone_masked"):
        lines.append(f"档案手机号：{result['phone_masked']}（凭此号可在生成报告的本机查询历史报告）\n")

    if result.get("red_flag"):
        lines.append("## ⛔ 红线预警\n")
        for c in result["conclusions"]:
            lines.append(f"### {c['title']}\n")
            lines.append(f"{c['body']}\n")
            if c.get("evidence"):
                lines.append("**依据 / 参考资料（含古籍、文献出处）：**\n")
                for e in c["evidence"]:
                    lines.append(f"- {_ev_loc(e)}\n")
                    lines.append(f"  > {_esc(e.get('text', '')).replace(chr(10), ' ')[:400]}")
                lines.append("")
        lines.extend(_render_bib_md(result.get("bibliography") or []))
        lines.extend(_render_care_md(result.get("daily_care")))
        lines.append("\n---\n")
        lines.append(f"> {result['disclaimer']}\n")
        return "\n".join(lines)

    lines.append("## 辨证摘要\n")
    lines.append(f"- **中医病种**：{s.get('dz')}　|　**西医对应**：{s.get('dz_western')}")
    cand = s.get("dz_candidates_detail") or []
    cand_txt = "；".join(f"{c['dz']}（{c['western']}）" for c in cand) \
        or "、".join(s.get("dz_candidates", []))
    lines.append(f"- **鉴别候选（含西医对应）**：{cand_txt}")
    lines.append(f"- **五轮定位**：{s.get('wheel')}（{s.get('zang')}）")
    lines.append(f"- **证型**：{s.get('syndrome')}（{s.get('nature')}）")
    lines.append(f"- **治法**：{s.get('method')}")
    lines.append(f"- **候选方（B级）**：{'、'.join(s.get('formulas', []))}")
    lines.append(f"- **关键药群**：{'、'.join(s.get('herbs', []))}")
    if s.get("contraindications"):
        lines.append(f"- **禁忌提示**：{'、'.join(s.get('contraindications'))}")
    lines.append(f"- **年龄区间**：{s.get('age_label') or '未提供'}")
    lines.append(f"- **舌象/起病/侧别**：{s.get('tongue') or '未提供'} / {s.get('onset') or '未明确'} / {s.get('laterality') or '未明确'}\n")

    lines.append("## 证型得分排序\n")
    for i, r in enumerate(s.get("synd_ranking", []), 1):
        lines.append(f"{i}. {r['name']} — 得分 {r['score']}")
    lines.append("")

    lines.append("<details>\n<summary>结论与依据（逐条溯源）　—　点击展开 / 收起</summary>\n")
    lines.append("> **分级说明：** "
                 "**A 级 · 可直接执行** — 起居、食疗、用眼节律等自我调护，可自行照做；"
                 "**B 级 · 须医师把关** — 辨证、方药、点眼制剂，须执业中医师面诊确认后使用；"
                 "**C 级 · 医疗升级/转诊** — 疑似急症红线，须立即就医或转眼科急诊。\n")
    for i, c in enumerate(result["conclusions"], 1):
        lines.append(f"### {i}. {c['title']}　`{LEVEL_LABEL.get(c['level'], c['level'])}`\n")
        lines.append(f"{c['body']}\n")
        if c.get("evidence"):
            lines.append("**依据 / 参考资料（含古籍、文献出处）：**\n")
            for e in c["evidence"]:
                lines.append(f"- {_ev_loc(e)}\n")
                lines.append(f"  > {_esc(e.get('text', '')).replace(chr(10), ' ')[:400]}")
            lines.append("")
        if c.get("source") == "web" and c.get("evidence"):
            lines.append("")
    lines.append("</details>\n")

    lines.extend(_render_bib_md(result.get("bibliography") or []))
    lines.extend(_render_care_md(result.get("daily_care")))

    lines.append("## 采集到的病情信息\n")
    for a in result.get("answers", []):
        lines.append(f"- **{a['title']}**：{a['label']}")
    lines.append("")
    lines.append("---\n")
    lines.append(f"> {result['disclaimer']}\n")
    return "\n".join(lines)


def render_html(result: dict) -> str:
    s = result.get("summary", {})
    parts = []
    parts.append(f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>眼健康自查助手 · 辨证咨询报告</title><style>
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;max-width:900px;margin:0 auto;padding:32px;line-height:1.75;color:#22303f;background:#fbfaf7}}
h1{{color:#1f5f4f;border-bottom:3px solid #1f5f4f;padding-bottom:12px}}
h2{{color:#1f5f4f;margin-top:36px;border-left:5px solid #1f5f4f;padding-left:10px}}
h3{{color:#2c3e50;margin-top:24px}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;margin-left:8px;vertical-align:middle}}
.badge.A{{background:#e6f4ea;color:#1e7e34}} .badge.B{{background:#fff4e5;color:#b45309}} .badge.C{{background:#fdecea;color:#b3261e}}
.lvnote{{font-size:12.5px;color:#5b6b64;line-height:2.1;margin:0 0 14px;padding:9px 12px;
  background:#f6f8f6;border:1px dashed #d8e2dd;border-radius:8px}}
.lvnote .badge{{margin:0 5px 0 0}}
.card{{background:#fff;border:1px solid #e6e2d8;border-radius:10px;padding:18px 20px;margin:14px 0;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.ev{{background:#f6f8f6;border-left:3px solid #8fb9a8;padding:8px 12px;margin:8px 0;font-size:13px;color:#4a5b50;border-radius:0 6px 6px 0}}
.ev b{{color:#1f5f4f}}
.ev.evc{{background:#fdf8ef;border-left-color:#c9973f}}
.ev.evc b{{color:#8a5a1f}}
.src{{font-size:12px;color:#7a8b82;margin-top:2px}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}
td,th{{border:1px solid #e6e2d8;padding:8px 10px;text-align:left}}
th{{background:#f0f4f1}}
.disc{{background:#fff8e1;border:1px solid #f0d9a0;padding:14px 16px;border-radius:8px;font-size:13px;color:#7a5c00}}
details.sec{{margin:26px 0 0}}
details.sec>summary{{list-style:none;cursor:pointer;user-select:none;display:flex;align-items:center;gap:9px;
  color:#1f5f4f;font-size:18px;font-weight:600;margin:0 0 12px;padding:11px 15px;
  background:#fff;border:1px solid #e6e2d8;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
details.sec>summary::-webkit-details-marker{{display:none}}
details.sec>summary::before{{content:"▸";font-size:14px;color:#2e7d68}}
details.sec[open]>summary::before{{content:"▾"}}
details.sec>summary:hover{{background:#f2f7f4}}
details.sec>summary .cnt{{font-size:12.5px;color:#7a8b82;font-weight:400}}
details.sec .sec-body{{padding:2px 0 8px}}
.red{{background:#fdecea;border:1px solid #f5c6c2;padding:16px;border-radius:8px;color:#8b1f16}}
</style></head><body>""")
    parts.append("<h1>眼健康自查助手 · 辨证咨询报告</h1>")
    if result.get("record_kind") == "ip":
        acct = "档案：未建档，本次报告不可查询"
    elif result.get("phone_masked"):
        acct = (f"档案手机号：<b>{_esc(result['phone_masked'])}</b>"
                "（凭此号可在生成报告的本机查询历史报告）")
    else:
        acct = ""
    parts.append(f"<p style='color:#7a8b82'>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                 + (f"　·　{acct}" if acct else "") + "</p>")

    if result.get("red_flag"):
        for c in result["conclusions"]:
            parts.append(f"<div class='red'><h3>{_esc(c['title'])}</h3><p>{_esc(c['body'])}</p>")
            if c.get("evidence"):
                parts.append("<div style='margin-top:10px'><b>依据 / 参考资料（含古籍、文献出处）：</b></div>")
                for e in c["evidence"]:
                    loc = f"{e.get('file','')}" + (f" · {e.get('section','')}" if e.get("section") else "") \
                          + (f" · 第{e.get('line')}行" if e.get("line") else "")
                    tag = _ev_tag(e)
                    parts.append(f"<div class='{_ev_cls(e)}'><b>{_esc(tag)}</b><div class='src'>{_esc(loc)}</div>"
                                 f"<div class='src'>{_esc(e.get('text',''))[:400]}</div></div>")
            parts.append("</div>")
        parts.extend(_render_bib_html(result.get("bibliography") or []))
        parts.extend(_render_care_html(result.get("daily_care")))
        parts.append(f"<div class='disc'>{_esc(result['disclaimer'])}</div>")
        parts.append("</body></html>")
        return "\n".join(parts)

    parts.append("<h2>辨证摘要</h2><table>")
    cand = s.get("dz_candidates_detail") or []
    cand_txt = "；".join(f"{c['dz']}（{c['western']}）" for c in cand) \
        or "、".join(s.get("dz_candidates", []))
    rows = [
        ("中医病种 / 西医对应", f"{s.get('dz')}　|　{s.get('dz_western')}"),
        ("鉴别候选（含西医对应）", cand_txt),
        ("五轮定位", f"{s.get('wheel')}（{s.get('zang')}）"),
        ("证型", f"{s.get('syndrome')}（{s.get('nature')}）"),
        ("治法", s.get('method')),
        ("候选方（B 级）", '、'.join(s.get('formulas', []))),
        ("关键药群", '、'.join(s.get('herbs', []))),
        ("禁忌提示", '、'.join(s.get('contraindications', [])) or "无"),
        ("年龄区间", s.get('age_label') or "未提供"),
    ]
    for k, v in rows:
        parts.append(f"<tr><th>{k}</th><td>{_esc(v)}</td></tr>")
    parts.append("</table>")

    parts.append("<details class='sec'><summary>结论与依据（逐条溯源）"
                 "<span class='cnt'>点击展开 / 收起</span></summary><div class='sec-body'>")
    parts.append("<div class='lvnote'>"
                 "<span class='badge A'>A 级 · 可直接执行</span>"
                 "起居、食疗、用眼节律等自我调护，可自行照做；"
                 "<span class='badge B'>B 级 · 须医师把关</span>"
                 "辨证、方药、点眼制剂，须执业中医师面诊确认后使用；"
                 "<span class='badge C'>C 级 · 医疗升级/转诊</span>"
                 "疑似急症红线，须立即就医或转眼科急诊。</div>")
    for i, c in enumerate(result["conclusions"], 1):
        lv = c.get("level", "B")
        parts.append(f"<div class='card'><h3>{i}. {_esc(c['title'])}"
                     f"<span class='badge {lv}'>{LEVEL_LABEL.get(lv, lv)}</span></h3>")
        parts.append(f"<p>{_esc(c['body']).replace(chr(10), '<br>')}</p>")
        if c.get("evidence"):
            parts.append("<div style='margin-top:10px'><b>依据 / 参考资料（含古籍、文献出处）：</b></div>")
            for e in c["evidence"]:
                loc = f"{e.get('file','')}" + (f" · {e.get('section','')}" if e.get("section") else "") \
                      + (f" · 第{e.get('line')}行" if e.get("line") else "")
                tag = _ev_tag(e)
                parts.append(f"<div class='{_ev_cls(e)}'><b>{_esc(tag)}</b><div class='src'>{_esc(loc)}</div>"
                             f"<div class='src'>{_esc(e.get('text',''))[:400]}</div></div>")
        parts.append("</div>")
    parts.append("</div></details>")

    parts.extend(_render_bib_html(result.get("bibliography") or []))
    parts.extend(_render_care_html(result.get("daily_care")))

    parts.append("<h2>采集到的病情信息</h2><ul>")
    for a in result.get("answers", []):
        parts.append(f"<li><b>{_esc(a['title'])}</b>：{_esc(a['label'])}</li>")
    parts.append("</ul>")
    parts.append(f"<div class='disc'>{_esc(result['disclaimer'])}</div>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _try_exclusive(path: Path) -> bool:
    """独占创建占位文件：成功返回 True（名字归本进程），已存在返回 False。

    用 O_EXCL 而非 exists() 判断 —— 多 worker / 多进程下 exists() 检查与写入之间
    存在竞态，O_EXCL 由内核保证原子，跨进程也不会撞名。
    """
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception:
        return False


def _alloc_pair(directory: Path, base: str):
    """成对分配 md/html 文件名（配对同序号），失败时递增序号重试"""
    n = 2
    while True:
        cand = base if n == 2 else f"{base}_{n}"
        md_path, html_path = directory / f"{cand}.md", directory / f"{cand}.html"
        if _try_exclusive(md_path):
            if _try_exclusive(html_path):
                return md_path, html_path
            try:                       # html 被占，回滚 md 占位
                md_path.unlink()
            except Exception:
                pass
        n += 1
        if n > 200:                    # 兜底，正常不会触发
            raise RuntimeError("报告文件名分配失败")


def save_report(result: dict, phone: str = ""):
    """落盘报告。多人同时咨询时必须保证文件名唯一：
       时间戳只到秒 → 同秒提交会撞名 → 后写的覆盖（甚至并发写坏）先写的，
       因此文件名加入手机号尾号，并在锁内用 O_EXCL 独占分配 + 冲突递增。"""
    tail = phone[-4:] if (phone and phone.isdigit() and len(phone) >= 4) else ""
    ts = _stamp()
    base = f"眼科辨证报告_{ts}" + (f"_{tail}" if tail else "")
    with _REPORT_LOCK:
        md_path, html_path = _alloc_pair(REPORT_DIR, base)
    try:
        _atomic_write(md_path, render_markdown(result))
        _atomic_write(html_path, render_html(result))
    except Exception:
        for p in (md_path, html_path):
            try:
                p.unlink()
            except Exception:
                pass
        raise
    return {"md": str(md_path), "html": str(html_path),
            "md_name": md_path.name, "html_name": html_path.name}
