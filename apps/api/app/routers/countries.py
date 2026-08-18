from fastapi import APIRouter, HTTPException, Query

from app.data.country_catalog import country_catalog, get_country, search_countries
from app.travel_map.schemas import CountryCatalogEntry, CountryCatalogResponse

router = APIRouter(prefix="/countries", tags=["countries"])


def _entry(country) -> CountryCatalogEntry:
    return CountryCatalogEntry(
        code=country.code,
        alpha3=country.alpha3,
        numericCode=country.numeric_code,
        name=country.name,
        continent=country.continent,
        countsTowardWorldTotal=country.counts_toward_world_total,
    )


@router.get("", response_model=CountryCatalogResponse)
def list_countries(q: str | None = Query(default=None, max_length=80)) -> CountryCatalogResponse:
    catalog = country_catalog()
    countries = search_countries(q, limit=195) if q is not None else list(catalog.countries)
    return CountryCatalogResponse(
        definition=catalog.definition,
        worldTotal=catalog.world_total,
        continentTotal=len(catalog.continents),
        continents=list(catalog.continents),
        countries=[_entry(country) for country in countries],
    )


@router.get("/{country_code}", response_model=CountryCatalogEntry)
def country_detail(country_code: str) -> CountryCatalogEntry:
    country = get_country(country_code)
    if not country:
        raise HTTPException(status_code=404, detail="Country not found.")
    return _entry(country)
