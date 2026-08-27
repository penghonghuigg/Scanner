from fastapi import APIRouter, Request

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live(request: Request) -> dict[str, object]:
    return {
        "success": True,
        "data": {"status": "ok"},
        "trace_id": request.state.trace_id,
    }
