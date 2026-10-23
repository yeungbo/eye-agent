# -*- coding: utf-8 -*-
# ============================================================================
# 眼健康自查助手 · 后端模块 · 本地中医眼科知识库检索器
# @author  杨博 (yangbo621@163.com)
# @license Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
#          https://creativecommons.org/licenses/by-nc/4.0/
# （详见随包 LICENSE.txt / NOTICE.md；商业使用需另行获得书面授权）
# ============================================================================

"""
本地中医眼科知识库检索器

数据源：/Users/bo/.workbuddy/skills/中医眼科/references/（含 00~09、安全表、通用中医/）
职责：
  1. 建立「文件 → 章节标题 → 行号 → 正文」的段落索引
  2. 按检索键（病种名/证型名/方剂名/药名/禁忌名）做子串加权检索
  3. 返回带完整出处的证据片段（文件名 + 章节 + 行号 + 原文），供报告引用

设计原则：查表而非凭记忆 —— 报告中的每一条结论都必须能回溯到库内具体文件的具体行。
"""

import os
import re
import threading
from pathlib import Path

def _resolve_lib_dir() -> Path:
    """知识库目录解析顺序（保证本地开发与 Linux 部署都能开箱即用）：
       1) 环境变量 EYE_LIB_DIR
       2) 程序包内自带 references/（安装版：/opt/eye-agent/references）
       3) 开发者本机的 skill 目录（macOS 开发态）
    """
    env = os.environ.get("EYE_LIB_DIR", "").strip()
    if env:
        return Path(env)
    base = Path(__file__).resolve().parent.parent
    for cand in (base / "references", base.parent / "references"):
        if cand.is_dir():
            return cand
    return Path.home() / ".workbuddy" / "skills" / "中医眼科" / "references"


LIB_DIR = _resolve_lib_dir()

# 参与检索的核心文件（优先眼科专科，其次通用中医）
PRIORITY_FILES = [
    "04-眼科病证分证论治.md",
    "00-眼科证治总索引.md",
    "03-眼科辨证.md",
    "06-眼科常用方剂.md",
    "05-眼科常用中药.md",
    "01-眼科基础与五轮八廓.md",
    "安全-眼科用药与外治安全.md",
    "07-眼科针灸与外治.md",
    "02-眼科病因病机与诊断.md",
    "08-眼科经典条文.md",
    "09-现代眼科共识与筛查要点.md",
]

GENERIC_DIR = "通用中医"

# 古籍条文层（经典依据专查此文件）
CLASSIC_FILE = "08-眼科经典条文.md"

# 文件权重：专科文件权重高
FILE_WEIGHT = {
    "04-眼科病证分证论治.md": 3.0,
    "00-眼科证治总索引.md": 2.6,
    "03-眼科辨证.md": 2.2,
    "06-眼科常用方剂.md": 2.4,
    "05-眼科常用中药.md": 2.2,
    "01-眼科基础与五轮八廓.md": 1.8,
    "安全-眼科用药与外治安全.md": 2.8,
    "07-眼科针灸与外治.md": 1.5,
    "02-眼科病因病机与诊断.md": 1.5,
    "08-眼科经典条文.md": 1.4,
    "09-现代眼科共识与筛查要点.md": 1.6,
}


class TcmLibrary:
    """中医眼科本地知识库（段落级索引 + 加权检索）

    索引为懒加载，且必须加锁：多人同时首次访问时，若不做 double-check，
    每个线程都会各自索引一遍 → 段落数成倍膨胀（实测 10 并发下 1700 → 17000）。
    """

    def __init__(self):
        self.paragraphs = []  # [{"file","section","line","text","weight"}]
        self._loaded = False
        self._lock = threading.Lock()

    def load(self):
        if self._loaded:
            return
        with self._lock:
            if self._loaded:          # double-check：并发下只索引一次
                return
            if not LIB_DIR.exists():
                self._loaded = True
                return
            # 先索引到临时缓冲，完成后再整体切换，避免其它线程读到半成品
            saved = self.paragraphs
            self.paragraphs = []
            try:
                for fname in PRIORITY_FILES:
                    fpath = LIB_DIR / fname
                    if fpath.exists():
                        self._index_file(fpath, fname, FILE_WEIGHT.get(fname, 1.0))
                gdir = LIB_DIR / GENERIC_DIR
                if gdir.exists():
                    for fpath in sorted(gdir.glob("*.md")):
                        self._index_file(fpath, f"{GENERIC_DIR}/{fpath.name}", 0.9)
                self._loaded = True
            except Exception:
                self.paragraphs = saved
                raise

    def _index_file(self, fpath: Path, display: str, weight: float):
        try:
            lines = fpath.read_text(encoding="utf-8").splitlines()
        except Exception:
            return
        cur_section = ""
        cur_book = ""      # 所属「书名」：从最近的一级/二级标题中的书名号推断
        buf = []
        buf_start = 0

        def flush():
            if not buf:
                return
            text = "\n".join(buf).strip()
            # 过滤纯分隔线 / 符号行（如 "---" "***" "==="），避免把分隔符当作条文引用
            if not text or not re.sub(r"[-*=~_·•\s]+", "", text):
                return
            self.paragraphs.append({
                "file": display, "section": cur_section,
                "book": cur_book, "line": buf_start,
                "text": text, "weight": weight,
            })

        for i, raw in enumerate(lines, start=1):
            line = raw.rstrip()
            # 识别标题（# / ## / ### / ####）
            m = re.match(r"^(#{1,6})\s+(.*)$", line)
            if m:
                # 先把缓冲区落盘
                flush()
                buf = []
                level = len(m.group(1))
                title = m.group(2).strip()
                # 「书名」锚点：一/二级标题里带书名号的，作为其后所有段落的归属书目
                if level <= 2:
                    cur_book = self._book_of_title(title) or cur_book
                # 只把 #/##/### 当作章节锚点
                if level <= 3:
                    cur_section = title
                buf_start = i
                continue
            if line.strip():
                if not buf:
                    buf_start = i
                buf.append(line)
            else:
                flush()
                buf = []
        flush()

    @staticmethod
    def _book_of_title(title: str) -> str:
        """从标题里抽取书名：'二、《银海精微》条文' → '银海精微'"""
        m = re.search(r"《([^《》]{2,40})》", title or "")
        if not m:
            return ""
        return m.group(1).split("·")[0].strip()

    # ---------- 检索 ----------
    def search(self, keys, top_k=3, max_chars=420, file_filter=None):
        """按检索键列表检索证据片段。keys: List[str]

        file_filter: 限定只在某个文件内检索（如 "08-眼科经典条文.md" 专查古籍条文）
        """
        self.load()
        if not self.paragraphs:
            return []
        results = []
        seen = set()
        for p in self.paragraphs:
            if file_filter and p["file"] != file_filter:
                continue
            hay = f"{p['section']}\n{p['text']}"
            score = 0.0
            hits = 0
            for k in keys:
                if not k:
                    continue
                k = k.strip()
                if len(k) < 2:
                    continue
                cnt = hay.count(k)
                if cnt:
                    hits += 1
                    score += cnt * 2.0 * (1 + min(len(k), 8) / 10.0)
                # 标题命中额外加权
                if k in (p["section"] or ""):
                    score += 12.0
            if hits == 0:
                continue
            score *= p["weight"]
            score += hits * 3.0  # 多键同时命中加分
            key = (p["file"], p["line"])
            if key in seen:
                continue
            seen.add(key)
            text = p["text"]
            if len(text) > max_chars:
                text = text[:max_chars] + "…"
            results.append({
                "file": p["file"],
                "section": p["section"],
                "book": p.get("book", ""),   # 段落所属书目（由一/二级标题推断）
                "line": p["line"],
                "text": text,
                "score": round(score, 2),
            })
        results.sort(key=lambda x: -x["score"])
        return results[:top_k]

    def search_classic(self, keys, top_k=3, max_chars=420):
        """只在古籍条文层（08）检索经典依据——《内经》《银海精微》《原机启微》《审视瑶函》等"""
        return self.search(keys, top_k=top_k, max_chars=max_chars,
                           file_filter=CLASSIC_FILE)

    def get_disease_block(self, dz_name: str):
        """取某病种在 04 文件中的完整条目块（标题起至下一个同级标题）"""
        self.load()
        fpath = LIB_DIR / "04-眼科病证分证论治.md"
        if not fpath.exists():
            return None
        lines = fpath.read_text(encoding="utf-8").splitlines()
        start = None
        start_line = 0
        for i, ln in enumerate(lines):
            if re.match(r"^#{2,4}\s*.*" + re.escape(dz_name), ln):
                start = i
                start_line = i + 1
                break
        if start is None:
            return None
        out = []
        for ln in lines[start:start + 14]:
            out.append(ln)
            # 遇到下一个同级/更高级标题则停
            if len(out) > 1 and re.match(r"^#{2,4}\s", ln):
                break
        return {"file": "04-眼科病证分证论治.md", "line": start_line,
                "text": "\n".join(out).strip()}

    def stats(self):
        self.load()
        return {"paragraphs": len(self.paragraphs), "lib": str(LIB_DIR)}


# 单例
LIB = TcmLibrary()
