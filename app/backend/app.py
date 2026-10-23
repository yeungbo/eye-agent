# -*- coding: utf-8 -*-
# ============================================================================
# 眼健康自查助手 · 后端服务
# @author  杨博 (yangbo621@163.com)
# @license Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
#          https://creativecommons.org/licenses/by-nc/4.0/
# （详见随包 LICENSE.txt / NOTICE.md；商业使用需另行获得书面授权）
# ============================================================================

"""
眼健康自查助手 · 后端服务
接口：
  GET  /api/questions          返回采集问卷
  POST /api/consult          提交问卷 → 本地库检索 → 辨证 → 生成报告并归档
                             phone 非空：按手机号建档（可凭该号查询 / 下载）
                             phone 为空：按本机 IP 建「访客档案」，报告照存但不支持查询
  GET  /api/reports?phone=   按手机号查询历史报告（脱敏；只返回手机号档案）
  GET  /api/records/<id>     调阅某次咨询的完整结果（需带 phone 校验归属）
  GET  /reports/<filename>   下载/查看已生成报告（?phone= 或 ?token= 校验归属）
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Any, Optional

from question_bank import QUESTIONS
from engine import analyze
from tcm_lib import LIB
from store import (normalize_phone, mask_phone, subject_masked, save_record,
                   list_records, get_result, stats as store_stats)
import store
import report as report_mod

import os
BASE = Path(__file__).resolve().parent.parent
FRONTEND = Path(os.environ.get("EYE_FRONTEND", "").strip() or (BASE / "frontend"))
REPORTS = Path(os.environ.get("EYE_REPORT_DIR", "").strip() or (BASE / "reports"))

app = FastAPI(title="眼健康自查助手", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def no_cache_html(request, call_next):
    """页面与接口不缓存：改完前端/后端后刷新即可生效，避免看到旧版报告"""
    resp = await call_next(request)
    p = request.url.path
    if p == "/" or p.endswith(".html") or p.startswith("/api"):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


class ConsultReq(BaseModel):
    answers: Dict[str, Any]
    phone: str = ""          # 留空 = 跳过建档，按本机访客（IP）归档
    register: bool = True    # 兼容字段：False 表示用户选择跳过建档


@app.get("/api/questions")
def get_questions():
    """第一步：返回采集问卷（仅暴露题面与选项，不含内部路由标签）"""
    qs = []
    for q in QUESTIONS:
        qs.append({
            "id": q["id"], "step": q["step"], "title": q["title"],
            "hint": q["hint"], "type": q["type"],
            "options": [{"value": o["value"], "label": o["label"]} for o in q["options"]],
        })
    return {"total": len(qs), "questions": qs, "lib": LIB.stats()}


def _client_ip(request: Request) -> str:
    """取客户端 IP（兼容 nginx 反代）；取不到时退回 unknown"""
    xf = request.headers.get("x-forwarded-for", "")
    if xf:
        return xf.split(",")[0].strip() or "unknown"
    xr = request.headers.get("x-real-ip", "")
    if xr:
        return xr.strip()
    return (request.client.host if request.client else "") or "unknown"


@app.post("/api/consult")
def consult(req: ConsultReq, request: Request):
    """采集 → 本地库检索 → 中医辨证 → 报告落盘归档

    建档方式由 phone 决定（用户可在提交时选择跳过）：
      · 传手机号 → 按手机号建档，日后凭同一手机号可查询、下载；
      · 留空跳过 → 按本机 IP 建立「访客档案」，报告照常生成并后台存储，
        但查询接口只认手机号，故访客报告之后无法被查询（前端也只展示结果）。
    """
    raw = (req.phone or "").strip()
    phone = None
    if raw and req.register:
        phone = normalize_phone(raw)
        if not phone:
            return JSONResponse(status_code=400, content={
                "ok": False,
                "error": "手机号格式不对：请填写 11 位手机号，或点「跳过」直接生成报告"})
    if phone:
        kind, subject = "phone", phone
    else:
        kind, subject = "ip", "ip:" + _client_ip(request)
    try:
        result = analyze(req.answers)
        result["phone_masked"] = subject_masked(subject, kind)
        result["record_kind"] = kind
        files = report_mod.save_report(result, phone=(phone or ""))
        record = save_record(subject, result, files, kind=kind)
        # 下载链接自带归属校验参数：手机号档案带 phone，访客档案带一次性 token
        qs = f"phone={phone}" if kind == "phone" else f"token={record.get('token','')}"
        return {
            "ok": True,
            "kind": kind,
            "result": result,
            "record": record,
            "files": files,
            "download": {"md": f"/reports/{files['md_name']}?{qs}",
                         "html": f"/reports/{files['html_name']}?{qs}"},
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@app.get("/api/reports")
def query_reports(phone: str = ""):
    """按手机号查询历史报告列表（仅返回脱敏信息）"""
    p = normalize_phone(phone)
    if not p:
        return JSONResponse(status_code=400, content={
            "ok": False, "error": "请填写有效的 11 位手机号"})
    rows = list_records(p)
    for r in rows:
        r["download"] = {"md": f"{r['download']['md']}?phone={p}",
                         "html": f"{r['download']['html']}?phone={p}"}
    return {"ok": True, "phone_masked": mask_phone(p), "total": len(rows), "records": rows}


@app.get("/api/records/{rid}")
def read_record(rid: str, phone: str = ""):
    """调阅某次咨询的完整辨证结果（须提供归属手机号校验）"""
    p = normalize_phone(phone)
    if not p:
        return JSONResponse(status_code=400, content={
            "ok": False, "error": "请提供手机号以校验归属"})
    r = get_result(rid, p)
    if r is None:
        return JSONResponse(status_code=404, content={
            "ok": False, "error": "未找到该记录，或手机号不匹配"})
    return {"ok": True, "result": r}


@app.get("/api/health")
def health():
    return {"ok": True, "lib": LIB.stats(), "store": store_stats()}


@app.get("/reports/{fname}")
def get_report(fname: str, phone: str = "", token: str = ""):
    """下载报告：手机号档案带 phone 校验归属，访客档案带 token 校验（防止按文件名遍历）"""
    # 安全：文件名只取基名，杜绝 ../ 路径穿越
    safe = Path(fname).name
    if not safe or safe in (".", ".."):
        return JSONResponse(status_code=404, content={"ok": False, "error": "not found"})
    p = REPORTS / safe
    if not p.exists() or not p.is_file():
        return JSONResponse(status_code=404, content={"ok": False, "error": "not found"})
    if not store.report_belongs_to(safe, phone=phone, token=token):
        return JSONResponse(status_code=404, content={
            "ok": False, "error": "未找到该报告，或校验信息不匹配（下载需提供建档手机号）"})
    return FileResponse(str(p), filename=safe)


# 静态前端（放在最后，避免覆盖 API 路由）
app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
