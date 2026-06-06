"""Dashboard routes — decisions, ML signals, and the HTML dashboard."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from cryptoswarm.api.deps import get_pg
from cryptoswarm.api.auth import require_auth

router = APIRouter()


@router.get("/decisions")
async def list_decisions(limit: int = 20, pg=Depends(get_pg), _: str = Depends(require_auth)):
    rows = await pg._pool.fetch(
        """
        SELECT correlation_id, agent_name, input_state, output,
               reasoning, confidence, ts
        FROM decisions
        ORDER BY ts DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


@router.get("/ml-signals")
async def list_ml_signals(limit: int = 20, pg=Depends(get_pg), _: str = Depends(require_auth)):
    rows = await pg._pool.fetch(
        """
        SELECT symbol, ts, regime_pred, direction_pred, short_direction,
               confidence, size_adjustment, model_version
        FROM ml_signals
        ORDER BY ts DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(r) for r in rows]


@router.get("/stats")
async def get_stats(pg=Depends(get_pg), _: str = Depends(require_auth)):
    row = await pg._pool.fetchrow(
        """
        SELECT
            COUNT(*)                                              AS total_trades,
            COUNT(*) FILTER (WHERE realized_pnl > 0)            AS wins,
            COUNT(*) FILTER (WHERE realized_pnl <= 0
                             AND closed_ts IS NOT NULL)          AS losses,
            COALESCE(SUM(realized_pnl), 0)                      AS total_pnl,
            COALESCE(SUM(fees), 0)                               AS total_fees,
            COUNT(*) FILTER (WHERE closed_ts IS NULL)           AS open_count
        FROM trades
        """
    )
    d = dict(row)
    closed = (d["wins"] or 0) + (d["losses"] or 0)
    d["win_rate"] = round(d["wins"] / closed * 100, 1) if closed > 0 else 0
    return d


@router.get("/pnl-history")
async def pnl_history(pg=Depends(get_pg), _: str = Depends(require_auth)):
    rows = await pg._pool.fetch(
        """
        SELECT closed_ts AS ts, realized_pnl,
               SUM(realized_pnl) OVER (ORDER BY closed_ts) AS cumulative_pnl
        FROM trades
        WHERE closed_ts IS NOT NULL AND realized_pnl IS NOT NULL
        ORDER BY closed_ts
        """
    )
    return [dict(r) for r in rows]


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: str = Depends(require_auth)):
    with open("/Users/sauravpandey/claude-projects/AI_Trading/backend/src/cryptoswarm/api/dashboard.html") as f:
        html = f.read()
    return html.replace("__USERNAME__", user)


@router.get("/")
async def root():
    return RedirectResponse(url="/dashboard")
