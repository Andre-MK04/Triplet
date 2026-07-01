from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.flight_search_service import FlightSearchService


class ToolContext(BaseModel):
    db: Session
    flight_search_service: FlightSearchService | None = None
    request_id: str | None = None
    user_id: str | None = None
    permissions: set[str] = set()

    model_config = {"arbitrary_types_allowed": True}


class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel] | None = None

    def run(self, input_data: BaseModel, context: ToolContext) -> Any:
        raise NotImplementedError
