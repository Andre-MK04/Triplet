from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.repositories.airports_repository import AirportsRepository
from app.models import Airport

router = APIRouter()


@router.get("/airports", response_model=list[Airport])
def list_airports(originCandidatesOnly: bool = False, db: Session = Depends(get_db)) -> list[Airport]:
    repository = AirportsRepository(db)
    try:
        if originCandidatesOnly:
            return repository.list_origin_candidates()
        return repository.list_airports()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=(
                "Database is not ready. Start the Triplet PostgreSQL container, "
                "run migrations, and seed the database."
            ),
        ) from exc
