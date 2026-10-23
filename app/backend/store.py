# -*- coding: utf-8 -*-
# ============================================================================
# 眼健康自查助手 · 后端模块 · 手机号档案库：把每次生成的报告按手机号归档，后期可用手机号查询历史报告。
# @author  杨博 (yangbo621@163.com)
# @license Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
#          https://creativecommons.org/licenses/by-nc/4.0/
# （详见随包 LICENSE.txt / NOTICE.md；商业使用需另行获得书面授权）
# ============================================================================

"""
手机号档案库：把每次生成的报告按手机号归档，后期可用手机号查询历史报告。

存储结构（均在本地，不联网、不上传）：
  data/records.json     索引：[{id, phone, phone_masked, created_at, dz, dz_western,
                                syndrome, age_label, red_flag, md_name, html_name}]
  data/results/<id>.json  该次咨询的完整 result（用于复现报告页面）

隐私约定：
  - 索引与前端展示一律使用脱敏手机号（138****8888）；
  - 完整手机号仅用于精确查询匹配，不下发给列表接口。
"""

import json
import os
import re
import secrets
import threading
from datetime import datetime
from pathlib import Path

BASE = Path(os.environ.get("EYE_DATA_DIR", "").strip() or
            (Path(__file__).resolve().parent.parent / "data"))
DATA_DIR = Path(BASE)
RESULT_DIR = DATA_DIR / "results"
INDEX_FILE = DATA_DIR / "records.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# 可重入锁：读（列表/调阅）与写（建档）共用，避免读到写了一半的索引
_LOCK = threading.RLock()

# 中国大陆手机号：1 开头，第二位 3-9，共 11 位
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


def normalize_phone(raw):
    """归一化手机号：去空格/横线/括号，剥离 +86 / 86 前缀。非法返回 None"""
    if raw is None:
        return None
    s = re.sub(r"[\s\-()（）]", "", str(raw))
    if s.startswith("+"):
        s = s[1:]
    if s.startswith("86") and len(s) == 13:
        s = s[2:]
    if not s.isdigit():
        return None
    return s if PHONE_RE.match(s) else None


def mask_phone(phone):
    """138****8888"""
    if not phone or len(phone) != 11:
        return phone or ""
    return f"{phone[:3]}****{phone[-4:]}"


def subject_masked(subject, kind="phone"):
    """档案展示名：手机号建档显示脱敏号；IP 访客建档显示「本机访客（未建档）」"""
    if kind == "phone":
        return mask_phone(subject)
    if isinstance(subject, str) and subject.startswith("ip:"):
        parts = subject[3:].split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*（本机访客 · 未建档）"
    return "本机访客 · 未建档"


def _atomic_write_json(path: Path, text: str):
    """原子写：先写临时文件再 replace，读者永远不会看到半截 JSON"""
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


def _load_index():
    """读索引（带锁，避免与建档并发时读到写了一半的文件）"""
    with _LOCK:
        if not INDEX_FILE.exists():
            return []
        try:
            data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []


def _save_index(rows):
    with _LOCK:
        _atomic_write_json(INDEX_FILE,
                           json.dumps(rows, ensure_ascii=False, indent=1))


def save_record(phone, result, files, kind="phone"):
    """归档一次咨询，返回索引条目（含展示名与下载令牌）

    kind='phone'：按手机号建档，日后可凭同一手机号查询/下载；
    kind='ip'   ：按本机访客建档（subject 形如 'ip:1.2.3.4'），
                  报告照常落盘，但查询接口只认手机号，故无法被查询。
    """
    ts = datetime.now()
    # 同一秒内多次建档时避免 id 冲突（否则后一份会覆盖前一份）；分配与写入全程持锁
    tail = phone[-4:] if (kind == "phone" and phone and len(phone) >= 4) else "guest"
    base_id = ts.strftime("%Y%m%d_%H%M%S") + "_" + tail
    s = result.get("summary", {}) or {}

    red_flag = bool(result.get("red_flag"))
    dz = s.get("dz") or "—"
    west = s.get("dz_western") or "—"
    syndrome = s.get("syndrome") or ("—" if red_flag else "—")
    if red_flag:
        # 红线：病种即疑似急症，西医对应照实给出，便于急诊沟通
        dz = (s.get("dz") or "—") + "（红线预警）"
        west = (s.get("dz_western") or "疑似急症，须眼科急诊")

    with _LOCK:
        rid, n = base_id, 2
        while (RESULT_DIR / f"{rid}.json").exists():
            rid, n = f"{base_id}_{n}", n + 1
        row = {
            "id": rid,
            "phone": phone,
            "phone_masked": subject_masked(phone, kind),
            "kind": kind,
            "token": secrets.token_hex(10),
            "created_at": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "dz": dz,
            "dz_western": west,
            "syndrome": syndrome,
            "age_label": s.get("age_label") or "未提供",
            "red_flag": red_flag,
            "md_name": files.get("md_name", ""),
            "html_name": files.get("html_name", ""),
        }

        # 完整结果落盘（供后期按手机号调阅）
        try:
            _atomic_write_json(RESULT_DIR / f"{rid}.json",
                               json.dumps(result, ensure_ascii=False))
        except Exception:
            pass

        rows = _load_index()
        rows.append(row)
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        _save_index(rows)

    return {k: v for k, v in row.items() if k != "phone"}


def list_records(phone, limit=50):
    """按手机号精确查询历史报告（返回脱敏条目 + 已带校验参数的下载链接）

    只返回手机号档案：IP 访客档案不支持查询（既查不到，也不允许按 IP 反查）。
    """
    rows = _load_index()
    mine = [r for r in rows
            if r.get("kind", "phone") == "phone" and r.get("phone") == phone]
    mine.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    out = []
    for r in mine[:limit]:
        out.append({
            "id": r["id"],
            "phone_masked": r.get("phone_masked", ""),
            "created_at": r.get("created_at", ""),
            "dz": r.get("dz", ""),
            "dz_western": r.get("dz_western", ""),
            "syndrome": r.get("syndrome", ""),
            "age_label": r.get("age_label", ""),
            "red_flag": r.get("red_flag", False),
            "download": {"md": f"/reports/{r.get('md_name','')}",
                         "html": f"/reports/{r.get('html_name','')}"},
            "view": f"/api/records/{r['id']}",
        })
    return out


def report_belongs_to(fname, phone=None, token=None):
    """校验报告文件归属

    手机号档案：用建档手机号校验（防止按文件名遍历他人报告）；
    访客档案  ：用一次性下载令牌校验（令牌只在生成报告时回给本人）。
    """
    if not fname:
        return False
    p = normalize_phone(phone) if phone else None
    fname = str(fname)
    for r in _load_index():
        if fname not in (r.get("md_name"), r.get("html_name")):
            continue
        if p and r.get("kind", "phone") == "phone" and r.get("phone") == p:
            return True
        if token and r.get("token") and secrets.compare_digest(str(r.get("token")), str(token)):
            return True
    return False


def get_result(rid, phone=None):
    """读取某次咨询的完整 result；传入 phone 时校验归属（访客档案不提供调阅）"""
    p = RESULT_DIR / f"{rid}.json"
    if not p.exists():
        return None
    if phone:
        row = next((r for r in _load_index()
                    if r.get("id") == rid and r.get("kind", "phone") == "phone"
                    and r.get("phone") == phone), None)
        if not row:
            return None
    try:
        result = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return _backfill_sources(result)


def _backfill_sources(result):
    """为旧归档结果补齐出处字段（src_kind / cite_label / cited / bibliography）

    早期生成的报告只记录了「文件·章节·行号」，没有古籍书名与引用书目一览。
    调阅时按当前溯源规则就地重算，使历史报告同样能看到古籍出处。
    """
    if not isinstance(result, dict):
        return result
    try:
        from citations import enrich_all, build_bibliography
        need = (not result.get("bibliography")) or any(
            e for c in (result.get("conclusions") or [])
            for e in (c.get("evidence") or []) if not e.get("src_kind"))
        if need:
            enrich_all(result.get("conclusions") or [], result.get("daily_care"))
            result["bibliography"] = build_bibliography(result)
    except Exception:
        pass
    return result


def stats():
    rows = _load_index()
    named = [r for r in rows if r.get("kind", "phone") == "phone"]
    phones = {r.get("phone") for r in named}
    return {"records": len(rows), "people": len(phones),
            "guest": len(rows) - len(named)}
