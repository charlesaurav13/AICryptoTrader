from fastapi import APIRouter, Depends
from cryptoswarm.api.auth import require_auth
from cryptoswarm.api.deps import get_engine

router = APIRouter(prefix="/circuit-breaker")


@router.get("/status")
async def status(engine=Depends(get_engine), _: str = Depends(require_auth)):
    dl = engine._daily_loss
    dd = engine._max_dd
    return {
        "daily_loss": {
            "tripped": dl.is_tripped(),
            "cumulative_pnl": dl._cumulative_pnl,
            "threshold": dl._threshold,
        },
        "max_drawdown": {
            "tripped": dd.is_tripped(),
            "peak_equity": dd._peak,
        },
    }


@router.post("/reset")
async def reset(engine=Depends(get_engine), _: str = Depends(require_auth)):
    engine._daily_loss.reset()
    engine._max_dd.reset()
    return {"reset": True}
