from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.analysis import generate_analysis, generate_capa

router = APIRouter(prefix="/analysis", tags=["analysis"])


class GenerateRequest(BaseModel):
    method: Literal["5whys", "ishikawa", "fta", "rca"]
    issue: str = Field(..., min_length=3, max_length=2000)
    grounded: bool = False
    owner: str | None = None


class CapaRequest(BaseModel):
    issue: str = Field(..., min_length=3, max_length=2000)
    root_causes: list[str] = Field(default_factory=list)


@router.post("/generate")
def generate(req: GenerateRequest) -> dict:
    """First-pass structured analysis for the chosen methodology. Optionally grounded
    in the requester's corpus + uploaded docs. Off the chat path."""
    return generate_analysis(req.method, req.issue, req.grounded, req.owner)


@router.post("/capa")
def capa(req: CapaRequest) -> dict:
    """Corrective + preventive actions for the refined root cause(s)."""
    return generate_capa(req.issue, req.root_causes)
