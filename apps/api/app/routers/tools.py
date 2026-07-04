from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.providers.errors import ProviderApiError, ProviderAuthError, ProviderConfigError
from app.services.flight_search_service import FlightProviderNotImplementedError, UnknownFlightProviderError
from app.tools.base import ToolContext
from app.tools.registry import (
    ToolNotFoundError,
    ToolValidationError,
    build_default_tool_registry,
)

router = APIRouter(prefix="/tools", tags=["tools"])
tool_registry = build_default_tool_registry()


class RunToolRequest(BaseModel):
    toolName: str
    input: dict[str, Any]


def require_dev_tools_enabled() -> None:
    if not settings.enable_dev_tool_endpoints:
        raise HTTPException(status_code=404, detail="Tool endpoints are disabled.")


@router.get("")
def list_tools() -> list[dict[str, Any]]:
    require_dev_tools_enabled()
    return tool_registry.list_tools()


@router.post("/run")
def run_tool(request: RunToolRequest, db: Session = Depends(get_db)) -> Any:
    require_dev_tools_enabled()
    try:
        return tool_registry.run_tool(request.toolName, request.input, ToolContext(db=db))
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ToolValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "errors": exc.errors},
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database is not ready.") from exc
    except FlightProviderNotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except UnknownFlightProviderError as exc:
        raise HTTPException(status_code=500, detail="Flight provider is not configured correctly.") from exc
    except ProviderConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except (ProviderAuthError, ProviderApiError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
