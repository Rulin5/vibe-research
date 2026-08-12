"""清数智算 后端 —— A股数据层 HTTP 接口（FastAPI）。

端点全部在 /api 下，前端 vite 代理 /api → localhost:8900。
只读、无状态、按用户传入代码返回客观数据。不预置标的、不建议。

启动：
    uvicorn app:app --host 127.0.0.1 --port 8900
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import astock
import ai_credentials
import teajoin
import chat as chat_layer
import cli_runtime
import debate as debate_layer
import gstock
import index_market
import newsradar
import market
import reflection as reflect_layer
from auth import (
    allowed_origins,
    clear_auth_cookies,
    create_session,
    hash_password,
    require_csrf,
    require_current_user,
    revoke_current_session,
    set_auth_cookies,
    validate_registration,
    verify_password,
)
from db import get_session
from models import User
import report_storage
import user_assets
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sector_refresh import SectorRefreshService
from runtime_security import enforce_rate_limit, enforce_startup_policy, redis_ready
from observability import request_observability_middleware
from metrics import DEPENDENCY_READY, metrics_endpoint, metrics_middleware


from version import read_version

__version__ = read_version()

app = FastAPI(title="清数智算 API", version=__version__)
enforce_startup_policy()
app.middleware("http")(request_observability_middleware)
app.middleware("http")(metrics_middleware)


@app.middleware("http")
async def public_data_rate_limit(request: Request, call_next):
    """Apply the distributed public-data ceiling independently of edge limits."""
    path = request.url.path
    exempt = path in {"/api/health", "/api/ready"} or path.startswith("/api/auth/")
    if path.startswith("/api/") and not exempt:
        enforce_rate_limit(request, "public-data", limit=120, window_seconds=60)
    return await call_next(request)

# CORS：本机自托管默认放开，前端经 Vite 代理访问本 API。
# 服务默认仅绑定 127.0.0.1；不提供公网部署或登录鉴权配置。
def parse_allowed_origins(raw: str | None = None) -> list[str]:
    return allowed_origins(raw)


_ORIGINS = parse_allowed_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

_CODE_RE = r"^\d{6}$"
_SECTOR_REFRESH = SectorRefreshService()


def _validate(code: str) -> str:
    code = (code or "").strip()
    if not code.isdigit() or len(code) != 6:
        raise HTTPException(400, "代码必须是 6 位数字")
    return code


@app.get("/api/health")
def health():
    return {"ok": True, "service": "qingshu-api", "version": __version__}


@app.get("/api/ready")
def ready(db: Session = Depends(get_session)):
    try:
        database_ok = db.execute(select(1)).scalar_one() == 1
    except SQLAlchemyError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "数据库未就绪") from exc
    redis_ok = redis_ready()
    DEPENDENCY_READY.labels("database").set(1 if database_ok else 0)
    DEPENDENCY_READY.labels("redis").set(1 if redis_ok else 0)
    if not database_ok or not redis_ok:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "服务依赖未就绪")
    return {"ok": True, "service": "qingshu-api", "version": __version__}


app.add_api_route("/api/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False)


class CredentialsIn(BaseModel):
    username: str
    password: str
    phone: str = ""


def _auth_response(response: Response, db: Session, user: User, status_code: int) -> dict:
    token = create_session(db, user.id)
    db.commit()
    set_auth_cookies(response, token)
    response.status_code = status_code
    return {"data": {"id": user.id, "username": user.username}}


@app.post("/api/auth/register")
def register(credentials: CredentialsIn, request: Request, response: Response, db: Session = Depends(get_session)):
    enforce_rate_limit(request, "register", limit=5, window_seconds=3600)
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in _ORIGINS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "请求来源不被允许")
    username, password, phone = validate_registration(credentials.username, credentials.password, credentials.phone)
    existing = db.execute(select(User).where(func.lower(User.username) == username.lower())).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "用户名已存在")
    user = User(username=username, password_hash=hash_password(password), phone=phone)
    db.add(user)
    db.flush()
    return _auth_response(response, db, user, status.HTTP_201_CREATED)


@app.post("/api/auth/login")
def login(credentials: CredentialsIn, request: Request, response: Response, db: Session = Depends(get_session)):
    enforce_rate_limit(request, "login", limit=10, window_seconds=900)
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in _ORIGINS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "请求来源不被允许")
    username = (credentials.username or "").strip()
    user = db.execute(select(User).where(func.lower(User.username) == username.lower())).scalar_one_or_none()
    if user is None or not verify_password(credentials.password or "", user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    return _auth_response(response, db, user, status.HTTP_200_OK)


@app.get("/api/auth/me")
def auth_me(user: User = Depends(require_current_user)):
    return {"data": {"id": user.id, "username": user.username}}


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_session), _: None = Depends(require_csrf)):
    revoke_current_session(request, db)
    clear_auth_cookies(response)


class AiCredentialIn(BaseModel):
    api_key: str
    base_url: str
    model: str


@app.get("/api/ai/credential")
def ai_credential_status(user: User = Depends(require_current_user), db: Session = Depends(get_session)):
    return {"data": ai_credentials.status_payload(db, user)}


@app.put("/api/ai/credential")
def ai_credential_save(
    payload: AiCredentialIn,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
):
    return {"data": ai_credentials.save_credential(db, user, payload.api_key, payload.base_url, payload.model)}


@app.delete("/api/ai/credential", status_code=status.HTTP_204_NO_CONTENT)
def ai_credential_delete(
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
):
    ai_credentials.delete_credential(db, user)


class ChatReq(BaseModel):
    messages: list[dict]
    context: str = ""


@app.post("/api/chat")
def chat(req: ChatReq, request: Request, user: User = Depends(require_current_user), db: Session = Depends(get_session), _: None = Depends(require_csrf)):
    """系统 AI 对话，**流式** NDJSON（每行一个事件 {type: tool|delta|done|error}）。

    - API 接入：OpenAI 兼容 function-calling，边流答案边推工具调用事件。
    - 订阅接入（provider=cli-*）：调本机已登录的 CLI，stdout 边出边流（数据靠 context）。
    配置错误（缺 key / 未装 CLI）走 HTTP 400；运行时错误走流内 error 事件。用户配置随请求传入，后端不持久化。
    """
    if not req.messages:
        raise HTTPException(400, "messages 不能为空")
    enforce_rate_limit(request, "chat", limit=30, window_seconds=3600, user_id=user.id)
    cfg = ai_credentials.runtime_config(db, user)

    def gen():
        try:
            events = chat_layer.run_chat_stream(cfg, req.messages, req.context)
            for ev in events:
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        except Exception as e:  # noqa: BLE001 — 运行时错误以流内事件上报，不中断连接
            yield json.dumps({"type": "error", "message": f"对话失败：{e}"}, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


def _ndjson(events):
    """把事件生成器包成 NDJSON 流；运行时异常转成流内 error 事件，不中断连接。"""
    def gen():
        try:
            for ev in events():
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        except Exception as e:  # noqa: BLE001
            yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


class DebateReq(BaseModel):
    code: str
    rounds: int = 1


@app.post("/api/debate")
def debate(req: DebateReq, request: Request, user: User = Depends(require_current_user), db: Session = Depends(get_session), _: None = Depends(require_csrf)):
    """多空辩论：后端先拉客观事实底稿，再让多方 / 空方 / 中立主持依次发言，**流式** NDJSON。

    刻意不产出买卖结论——终点是「分歧点 + 验证清单」，判断留给用户自己。
    """
    code = _validate(req.code)
    enforce_rate_limit(request, "debate", limit=30, window_seconds=3600, user_id=user.id)
    cfg = ai_credentials.runtime_config(db, user)
    rounds = 2 if req.rounds >= 2 else 1
    return _ndjson(lambda: debate_layer.run_debate_stream(cfg, code, rounds))


class ReflectReq(BaseModel):
    source: str
    title: str = ""


@app.post("/api/reflect")
def reflect(req: ReflectReq, request: Request, user: User = Depends(require_current_user), db: Session = Depends(get_session), _: None = Depends(require_csrf)):
    """反思：对一段已写好的分析做推理审计（哪些有数据支撑、最脆弱一环、验证清单），流式 NDJSON。"""
    if not (req.source or "").strip():
        raise HTTPException(400, "source 不能为空")
    enforce_rate_limit(request, "reflect", limit=30, window_seconds=3600, user_id=user.id)
    cfg = ai_credentials.runtime_config(db, user)
    return _ndjson(lambda: reflect_layer.run_reflection_stream(cfg, req.source, req.title))


class WatchlistIn(BaseModel):
    code: str


class NoteIn(BaseModel):
    kind: str = "general"
    title: str
    content: str


class PrivateHoldingIn(BaseModel):
    code: str
    shares: float
    cost: float


class PrivateCloseIn(BaseModel):
    code: str
    date: str
    price: float
    shares: float
    cost: float


class PrivateReportIn(BaseModel):
    name: str
    content_b64: str


@app.get("/api/watchlist")
def watchlist_list(user: User = Depends(require_current_user), db: Session = Depends(get_session)):
    return {"data": user_assets.list_watchlist(db, user)}


@app.post("/api/watchlist")
def watchlist_add(
    payload: WatchlistIn,
    response: Response,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
):
    item, created = user_assets.add_watchlist_item(db, user, payload.code)
    if created:
        response.status_code = status.HTTP_201_CREATED
    return {"data": item}


@app.delete("/api/watchlist/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def watchlist_delete(
    item_id: str,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
):
    user_assets.delete_watchlist_item(db, user, item_id)


@app.get("/api/portfolio")
def portfolio_get_private(user: User = Depends(require_current_user), db: Session = Depends(get_session)):
    return {"data": user_assets.portfolio_payload(db, user)}


@app.post("/api/portfolio/holding", status_code=status.HTTP_201_CREATED)
def portfolio_add_private(
    payload: PrivateHoldingIn,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
):
    return {"data": user_assets.add_holding(db, user, payload.code, payload.shares, payload.cost)}


@app.delete("/api/portfolio/holding/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def portfolio_remove_private(
    holding_id: str,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
):
    user_assets.delete_holding(db, user, holding_id)


@app.post("/api/portfolio/close", status_code=status.HTTP_201_CREATED)
def portfolio_close_private(
    payload: PrivateCloseIn,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
):
    try:
        closed_on = datetime.strptime(payload.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "清仓日期格式应为 YYYY-MM-DD") from None
    return {"data": user_assets.add_closed_position(db, user, payload.code, closed_on, payload.price, payload.shares, payload.cost)}


@app.delete("/api/portfolio/close/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
def portfolio_close_remove_private(
    position_id: str,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
):
    user_assets.delete_closed_position(db, user, position_id)


@app.get("/api/notes")
def notes_list(user: User = Depends(require_current_user), db: Session = Depends(get_session)):
    return {"data": user_assets.list_notes(db, user)}


@app.post("/api/notes", status_code=status.HTTP_201_CREATED)
def notes_create(
    payload: NoteIn,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
):
    return {"data": user_assets.create_note(db, user, payload.kind, payload.title, payload.content)}


@app.delete("/api/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def notes_delete(
    note_id: str,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
):
    user_assets.delete_note(db, user, note_id)


@app.get("/api/myreports")
def reports_list_private(user: User = Depends(require_current_user), db: Session = Depends(get_session)):
    return {"data": report_storage.list_reports(db, user)}


@app.post("/api/myreports", status_code=status.HTTP_201_CREATED)
def reports_upload_private(
    payload: PrivateReportIn,
    request: Request,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
):
    enforce_rate_limit(request, "report-upload", limit=20, window_seconds=3600, user_id=user.id)
    return {"data": report_storage.save_report(db, user, payload.name, payload.content_b64)}


@app.get("/api/myreports/file/{report_id}")
def reports_file_private(report_id: str, user: User = Depends(require_current_user), db: Session = Depends(get_session)):
    report = report_storage.owned_report(db, user, report_id)
    path = Path(report.storage_key)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "研报不存在")
    return FileResponse(str(path), filename=report.original_name, media_type=report.mime_type)


@app.delete("/api/myreports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def reports_delete_private(
    report_id: str,
    user: User = Depends(require_current_user),
    db: Session = Depends(get_session),
    _: None = Depends(require_csrf),
):
    report_storage.delete_report(db, user, report_id)


class HoldingIn(BaseModel):
    code: str
    shares: float
    cost: float


@app.get("/api/_legacy_disabled/portfolio")
def portfolio_get():
    raise HTTPException(status.HTTP_410_GONE, "旧全局持仓接口已停用")
    """持仓 + 实时盈亏（浮动盈亏红涨绿跌）。"""
    try:
        return {"data": pf.get_portfolio()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"持仓读取异常：{e}") from e


@app.post("/api/_legacy_disabled/portfolio/holding")
def portfolio_add(h: HoldingIn):
    raise HTTPException(status.HTTP_410_GONE, "旧全局持仓接口已停用")
    """加一笔持仓（同代码按加权平均成本合并）。存本地，不上传。"""
    code = (h.code or "").strip()
    if not code.isdigit() or len(code) != 6:
        raise HTTPException(400, "代码必须是 6 位数字")
    if h.shares <= 0:
        raise HTTPException(400, "数量必须大于 0")
    # 成本价不限正负：融券 / 返息 / 摊薄后为负成本等情形按结果计算，用户想怎么输就怎么输。
    return {"data": pf.add_holding(code, h.shares, h.cost)}


@app.delete("/api/_legacy_disabled/portfolio/holding")
def portfolio_remove(code: str = Query(...)):
    raise HTTPException(status.HTTP_410_GONE, "旧全局持仓接口已停用")
    return {"data": pf.remove_holding(code.strip())}


# ---- 我的研报（用户上传自己的研报，存本地、不上传、不进开源仓库）----

class ReportIn(BaseModel):
    name: str
    content_b64: str


@app.get("/api/_legacy_disabled/myreports")
def myreports_list():
    raise HTTPException(status.HTTP_410_GONE, "旧全局研报接口已停用")
    return {"data": mr.list_reports()}


@app.post("/api/_legacy_disabled/myreports")
def myreports_upload(r: ReportIn):
    raise HTTPException(status.HTTP_410_GONE, "旧全局研报接口已停用")
    """上传一份研报（base64）→ 存本地 + 按文件名自动打行业标签。"""
    try:
        return {"data": mr.save_report(r.name, r.content_b64)}
    except mr.ReportError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/_legacy_disabled/myreports/file/{rid}")
def myreports_file(rid: str):
    raise HTTPException(status.HTTP_410_GONE, "旧全局研报接口已停用")
    """下载/预览某份研报原文件。"""
    hit = mr.report_path(rid)
    if not hit:
        raise HTTPException(404, "研报不存在")
    path, name = hit
    return FileResponse(str(path), filename=name)


@app.delete("/api/_legacy_disabled/myreports/{rid}")
def myreports_delete(rid: str):
    raise HTTPException(status.HTTP_410_GONE, "旧全局研报接口已停用")
    return {"data": {"ok": mr.delete_report(rid)}}


class CloseIn(BaseModel):
    code: str
    date: str
    price: float
    shares: float
    cost: float


@app.post("/api/_legacy_disabled/portfolio/close")
def portfolio_close(c: CloseIn):
    raise HTTPException(status.HTTP_410_GONE, "旧全局持仓接口已停用")
    """记一笔已清仓（已实现盈亏）。存本地。"""
    code = (c.code or "").strip()
    if not code.isdigit() or len(code) != 6:
        raise HTTPException(400, "代码必须是 6 位数字")
    if c.price <= 0 or c.shares <= 0:
        raise HTTPException(400, "清仓价与股数必须大于 0")
    # 买入成本不限正负（同持仓录入）：按 (清仓价 - 成本) × 股数 的结果计算已实现盈亏。
    date = (c.date or "").strip()
    if not date:
        raise HTTPException(400, "请填清仓日期")
    from datetime import datetime
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "清仓日期格式应为 YYYY-MM-DD") from None
    return {"data": pf.close_position(code, date, c.price, c.shares, c.cost)}


@app.delete("/api/_legacy_disabled/portfolio/close")
def portfolio_close_remove(index: int = Query(...)):
    raise HTTPException(status.HTTP_410_GONE, "旧全局持仓接口已停用")
    return {"data": pf.remove_closed(index)}


@app.post("/api/_legacy_disabled/portfolio/refresh")
def portfolio_refresh():
    raise HTTPException(status.HTTP_410_GONE, "旧全局持仓接口已停用")
    """手动刷新：立即重拉行情算盈亏。"""
    try:
        return {"data": pf.get_portfolio()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"刷新失败：{e}") from e


@app.get("/api/radar")
def radar():
    """资讯雷达：12 赛道公开 RSS 资讯（读缓存，无缓存返回赛道骨架）。"""
    try:
        return {"data": newsradar.get_radar(force=False)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"资讯雷达异常：{e}") from e


@app.post("/api/radar/refresh")
def radar_refresh():
    """强制重抓全部 RSS 源（耗时约 20-40s），更新缓存。"""
    try:
        return {"data": newsradar.fetch_radar()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"资讯雷达刷新失败：{e}") from e


@app.get("/api/market/overview")
def market_overview():
    """市场情绪 + 板块资金流（板块/大盘级，全站共享缓存 5 分钟）。"""
    try:
        return {"data": market.get_overview()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"市场总览异常：{e}") from e


@app.get("/api/market/emotion")
def market_emotion():
    """短线情绪：连板梯队 / 最高连板 / 炸板率 / 封板率 / 晋级率 / 涨跌停家数。

    含连板梯队个股清单（code/name/连板数等）——2026-07-05 起如实展示客观公开榜单（东财同款），
    只呈现事实，不附推荐/评分/预测/买卖时机。全站共享缓存 5 分钟。
    """
    try:
        return {"data": market.get_short_term_emotion()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"短线情绪异常：{e}") from e


@app.get("/api/market/turnover-top")
def market_turnover_top():
    """全市场成交额榜 Top20（客观公开榜单数据，非推荐/非预测/不评分）。全站共享缓存 5 分钟。"""
    try:
        return {"data": market.get_turnover_top()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"成交额榜异常：{e}") from e


@app.get("/api/global/indices")
def global_indices():
    """全球指数快照（道指 / 标普500 / 纳斯达克 / 恒生 / 恒生科技）—— A 股看隔夜外围脸色。缓存 5 分钟。"""
    try:
        return {"data": market.get_global_indices()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"全球指数异常：{e}") from e


@app.get("/api/global/stock")
def global_stock(symbol: str = Query(..., min_length=1, max_length=16)):
    """美股 / 港股个股聚合：行情 + 关键财务指标（东财域内源）。symbol 如 AAPL / BABA / 00700。"""
    try:
        data = gstock.us_hk_stock(symbol.strip())
        if not data:
            raise HTTPException(404, f"未找到美股/港股代码「{symbol}」")
        return {"data": data}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"美港股查询异常：{e}") from e


@app.get("/api/global/hk/cashflow")
def global_hk_cashflow(symbol: str = Query(..., min_length=1, max_length=16)):
    """港股现金流量表（东财域内源 RPT_HKSK_FN_CASHFLOW）：经营/投资/筹资/净增加，多期。symbol 如 00700。"""
    try:
        data = gstock.hk_cashflow(symbol.strip())
        if not data:
            raise HTTPException(404, f"未找到港股「{symbol}」的现金流数据（仅港股支持）")
        return {"data": data}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"港股现金流查询异常：{e}") from e


@app.get("/api/indices")
def indices():
    """A股大盘指数实时行情（上证/深证成指/创业板指/沪深300）。仅标准库。"""
    try:
        return {"data": astock.index_quote()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"指数行情异常：{e}") from e


@app.get("/api/market/index-candles")
def index_candles(
    symbols: str = Query(..., min_length=1, max_length=300),
    period: str = Query("1d", pattern="^1d$"),
    limit: int = Query(60, ge=20, le=250),
):
    requested = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
    if not requested or len(requested) > 10 or len(requested) != len(set(requested)):
        raise HTTPException(422, "symbols must contain 1-10 unique index identifiers")
    try:
        return {"data": index_market.get_index_series_batch(requested, period=period, limit=limit)}
    except index_market.UnknownIndex as exc:
        raise HTTPException(422, f"unknown index: {exc}") from exc
    except index_market.InvalidIndexData as exc:
        raise HTTPException(502, f"invalid TeaJoin index data: {exc}") from exc
    except teajoin.TeaJoinError as exc:
        raise HTTPException(503 if isinstance(exc, teajoin.TeaJoinConfigError) else 502, str(exc)) from exc


@app.get("/api/quote")
def quote(codes: str = Query(..., description="逗号分隔的 6 位代码")):
    """实时行情：现价/涨跌/PE/PB/市值/换手/涨跌停。仅标准库，永远可用。"""
    lst = [c.strip() for c in codes.split(",") if c.strip()]
    if not lst or any(not c.isdigit() or len(c) != 6 for c in lst):
        raise HTTPException(400, "codes 必须是逗号分隔的 6 位数字")
    try:
        return {"data": astock.tencent_quote(lst)}
    except Exception as e:  # noqa: BLE001 — 边界统一兜底
        raise HTTPException(502, f"行情源异常：{e}") from e


import time as _time
_PCT_CACHE: dict = {}


@app.get("/api/valuation/percentile")
def valuation_percentile(code: str = Query(...)):
    """PE-TTM / PB 历史分位（近5年）。全站缓存 30 分钟/代码（历史序列日频、变化慢）。"""
    code = _validate(code)
    hit = _PCT_CACHE.get(code)
    if hit and _time.time() - hit[0] < 1800:
        return {"data": hit[1]}
    try:
        data = astock.valuation_percentile(code)
        _PCT_CACHE[code] = (_time.time(), data)
        return {"data": data}
    except astock.DependencyMissing as e:
        raise HTTPException(501, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"估值分位异常：{e}") from e


_ANN_CACHE: dict = {}


@app.get("/api/announcements")
def announcements(code: str = Query(...)):
    """个股近期公告（东财，仅 requests）。缓存 15 分钟/代码。"""
    code = _validate(code)
    hit = _ANN_CACHE.get(code)
    if hit and _time.time() - hit[0] < 900:
        return {"data": hit[1]}
    try:
        data = astock.announcements(code)
        _ANN_CACHE[code] = (_time.time(), data)
        return {"data": data}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"公告源异常：{e}") from e


_FIN_CACHE: dict = {}


@app.get("/api/financials")
def financials(code: str = Query(...)):
    """财务关键指标（同花顺财务摘要，最新报告期）。缓存 30 分钟/代码。"""
    code = _validate(code)
    hit = _FIN_CACHE.get(code)
    if hit and _time.time() - hit[0] < 1800:
        return {"data": hit[1]}
    try:
        data = astock.financials(code)
        _FIN_CACHE[code] = (_time.time(), data)
        return {"data": data}
    except astock.DependencyMissing as e:
        raise HTTPException(501, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"财务摘要异常：{e}") from e


@app.get("/api/valuation")
def valuation(code: str = Query(...)):
    """完整估值：行情 + 一致预期 + 前向PE/PEG/消化年数。"""
    code = _validate(code)
    try:
        return {"data": astock.full_valuation(code)}
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"估值计算异常：{e}") from e


@app.get("/api/reports")
def reports(code: str = Query(...), pages: int = Query(2, ge=1, le=5)):
    """个股研报列表（东财，含 PDF 链接）。仅需 requests。"""
    code = _validate(code)
    try:
        rows = astock.eastmoney_reports(code, max_pages=pages)
        for r in rows:
            r["pdfUrl"] = astock.pdf_url(r.get("infoCode", "")) if r.get("infoCode") else None
        return {"data": rows}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"研报源异常：{e}") from e


@app.get("/api/news")
def news(code: str = Query(...), limit: int = Query(20, ge=1, le=50)):
    """个股新闻（东财，需 akshare）。"""
    code = _validate(code)
    try:
        return {"data": astock.stock_news(code, limit=limit)}
    except astock.DependencyMissing as e:
        raise HTTPException(501, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"新闻源异常：{e}") from e


@app.get("/api/info")
def info(code: str = Query(...)):
    """个股基本面：行业/股本/上市时间（需 akshare）。"""
    code = _validate(code)
    try:
        return {"data": astock.individual_info(code)}
    except astock.DependencyMissing as e:
        raise HTTPException(501, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"基本面源异常：{e}") from e


@app.get("/api/disclosure")
def disclosure(code: str = Query(...)):
    """巨潮公告列表（需 akshare）。"""
    code = _validate(code)
    try:
        return {"data": astock.disclosure(code)}
    except astock.DependencyMissing as e:
        raise HTTPException(501, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"公告源异常：{e}") from e


@app.get("/api/kline")
def kline(code: str = Query(...), category: int = Query(4), offset: int = Query(60, ge=1, le=800)):
    """K线（需 mootdx）。category 4=日 5=周 6=月 11=60分钟。"""
    code = _validate(code)
    try:
        return {"data": astock.kline(code, category=category, offset=offset)}
    except astock.DependencyMissing as e:
        raise HTTPException(501, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"K线源异常：{e}") from e


@app.get("/api/finance")
def finance(code: str = Query(...)):
    """季报财务快照（需 mootdx）。"""
    code = _validate(code)
    try:
        return {"data": astock.finance(code)}
    except astock.DependencyMissing as e:
        raise HTTPException(501, str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"财务源异常：{e}") from e


# ---------------------------------------------------------------------------
# 资金面 / 筹码 / 信号（东财数据中心，v3.3 并入）—— 均为「用户查的那只股」的公开数据。
# 东财有 1s 限流，这些多为日/季级静态数据，统一走 30 分钟缓存，进一步降低被封风险。
# ---------------------------------------------------------------------------

_DC_CACHE: dict = {}  # key=(endpoint, code) -> (ts, data)


def _cached(endpoint: str, code: str, ttl: int, fetch):
    key = (endpoint, code)
    hit = _DC_CACHE.get(key)
    if hit and _time.time() - hit[0] < ttl:
        return hit[1]
    data = fetch()
    _DC_CACHE[key] = (_time.time(), data)
    return data


@app.get("/api/margin")
def margin(code: str = Query(...)):
    """融资融券明细（东财，日级）。缓存 30 分钟。"""
    code = _validate(code)
    try:
        return {"data": _cached("margin", code, 1800, lambda: astock.margin_trading(code))}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"融资融券异常：{e}") from e


@app.get("/api/block-trade")
def block_trade(code: str = Query(...)):
    """大宗交易（东财）。缓存 30 分钟。"""
    code = _validate(code)
    try:
        return {"data": _cached("block", code, 1800, lambda: astock.block_trade(code))}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"大宗交易异常：{e}") from e


@app.get("/api/holders")
def holders(code: str = Query(...)):
    """股东户数变化（东财，季度级）。缓存 30 分钟。"""
    code = _validate(code)
    try:
        return {"data": _cached("holders", code, 1800, lambda: astock.holder_num_change(code))}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"股东户数异常：{e}") from e


@app.get("/api/dividend")
def dividend(code: str = Query(...)):
    """分红送转历史（东财）。缓存 30 分钟。"""
    code = _validate(code)
    try:
        return {"data": _cached("dividend", code, 1800, lambda: astock.dividend_history(code))}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"分红送转异常：{e}") from e


@app.get("/api/fund-flow")
def fund_flow(code: str = Query(...)):
    """个股资金流（东财 push2his，120 日主力净流入）。缓存 15 分钟。
    注：push2his 对部分大陆住宅 IP 有间歇风控，可能返回空（非代码问题）。"""
    code = _validate(code)
    try:
        return {"data": _cached("fundflow", code, 900, lambda: astock.stock_fund_flow_120d(code))}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"资金流异常：{e}") from e


@app.get("/api/dragon-tiger")
def dragon_tiger(code: str = Query(...)):
    """龙虎榜：该股近期上榜记录 + 买卖席位 + 机构净买（东财）。缓存 30 分钟。"""
    code = _validate(code)
    try:
        return {"data": _cached("dt", code, 1800, lambda: astock.dragon_tiger_board(code))}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"龙虎榜异常：{e}") from e


@app.get("/api/lockup")
def lockup(code: str = Query(...)):
    """限售解禁日历：历史解禁 + 未来 90 天待解禁（东财）。缓存 30 分钟。"""
    code = _validate(code)
    try:
        return {"data": _cached("lockup", code, 1800, lambda: astock.lockup_expiry(code))}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"解禁日历异常：{e}") from e


@app.get("/api/blocks")
def blocks(code: str = Query(...)):
    """个股所属板块/概念归属（东财 slist）。缓存 30 分钟。"""
    code = _validate(code)
    try:
        return {"data": _cached("blocks", code, 1800, lambda: astock.concept_blocks(code))}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"板块归属异常：{e}") from e


@app.get("/api/hot-concepts")
def hot_concepts(code: str = Query(...)):
    """个股当下被市场归到哪些概念在炒（东财热门概念命中）。缓存 15 分钟。"""
    code = _validate(code)
    try:
        return {"data": _cached("hotcon", code, 900, lambda: astock.hot_concepts(code))}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"热门概念异常：{e}") from e


@app.get("/api/investor-qa")
def investor_qa(code: str = Query(...)):
    """互动易问答（巨潮）：投资者提问 + 公司回复。缓存 15 分钟。"""
    code = _validate(code)
    try:
        return {"data": _cached("irm", code, 900, lambda: astock.investor_qa(code))}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"互动易异常：{e}") from e


@app.get("/api/industry")
def industry(top: int = Query(20, ge=5, le=50)):
    """全行业涨跌幅排名（东财行业板块，板块级、零个股名单）。缓存 5 分钟。"""
    key = ("industry", str(top))
    hit = _DC_CACHE.get(key)
    if hit and _time.time() - hit[0] < 300:
        return {"data": hit[1]}
    try:
        data = astock.industry_comparison(top_n=top)
        _DC_CACHE[key] = (_time.time(), data)
        return {"data": data}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"行业排名异常：{e}") from e


@app.get("/api/all-sectors")
def all_sectors():
    """读取已验证板块快照；请求路径不会发起数百次上游成分股调用。"""
    snapshot = _SECTOR_REFRESH.store.load_current()
    if snapshot is None:
        raise HTTPException(503, {"code": "sector_snapshot_unavailable", "refresh": _SECTOR_REFRESH.status()})
    industries = [row for row in snapshot.get("sectors", []) if row.get("kind") == "行业"]
    concepts = [row for row in snapshot.get("sectors", []) if row.get("kind") == "概念"]
    for rows in (industries, concepts):
        rows.sort(key=lambda row: row.get("pct_change", 0), reverse=True)
    return {"data": {
        "industries": industries, "concepts": concepts,
        **{key: snapshot.get(key) for key in (
            "snapshot_id", "as_of", "retrieved_at", "source", "market", "currency", "timezone",
            "frequency", "method_version", "completeness",
        )},
    }}


def _teajoin_http_error(exc: teajoin.TeaJoinError) -> HTTPException:
    return HTTPException(503 if isinstance(exc, teajoin.TeaJoinConfigError) else 502, str(exc))


@app.get("/api/sector-members")
def sector_members(kind: str = Query(..., min_length=1, max_length=16), code: str = Query(..., min_length=1, max_length=32)):
    """返回与板块列表同一版本的经校验成分股。"""
    snapshot = _SECTOR_REFRESH.store.load_current()
    if snapshot is None:
        raise HTTPException(503, {"code": "sector_snapshot_unavailable", "refresh": _SECTOR_REFRESH.status()})
    exists = any(row.get("kind") == kind and row.get("code") == code for row in snapshot.get("sectors", []))
    if not exists:
        raise HTTPException(404, "板块未找到或未通过成分股校验")
    data = _SECTOR_REFRESH.store.load_members(snapshot["snapshot_id"], kind, code)
    if not data:
        raise HTTPException(503, {"code": "sector_snapshot_corrupt", "snapshot_id": snapshot["snapshot_id"]})
    return {"data": {"kind": kind, "code": code, "snapshot_id": snapshot["snapshot_id"], "as_of": snapshot["as_of"], "source": "TeaJoin/Tushare ths_member verified snapshot", "members": data}}


@app.get("/api/stocks/search")
def stocks_search(query: str = Query(..., min_length=2, max_length=32), limit: int = Query(20, ge=1, le=50)):
    """按证券代码或名称检索 A 股主数据；不返回供应商凭据。"""
    try:
        data = astock.teajoin_stock_search(query, limit)
    except teajoin.TeaJoinError as exc:
        raise _teajoin_http_error(exc) from exc
    return {"data": {"query": query.strip(), "source": "TeaJoin/Tushare stock_basic", "results": data}}


@app.get("/api/sector-detail")
def sector_detail(kind: str = Query(...), code: str = Query(...)):
    """读取与列表同一快照的板块日线详情。"""
    snapshot = _SECTOR_REFRESH.store.load_current()
    if snapshot is None:
        raise HTTPException(503, {"code": "sector_snapshot_unavailable", "refresh": _SECTOR_REFRESH.status()})
    data = next((row for row in snapshot.get("sectors", []) if row.get("kind") == kind and row.get("code") == code), None)
    if data is None:
        raise HTTPException(404, f"板块未找到：{kind}/{code}")
    return {"data": {**data, "snapshot_id": snapshot["snapshot_id"], "retrieved_at": snapshot["retrieved_at"], "method_version": snapshot["method_version"]}}


@app.get("/api/sectors/status")
def sector_refresh_status():
    return {"data": _SECTOR_REFRESH.status()}


@app.post("/api/sectors/refresh", status_code=202)
def sector_refresh():
    return {"data": _SECTOR_REFRESH.start("api-sector-refresh")}
