from datetime import date
from urllib.parse import urlencode

from app.config import settings


class SkyscannerAffiliateLinkBuilder:
    def __init__(
        self,
        enabled: bool | None = None,
        media_partner_id: str | None = None,
        base_url: str | None = None,
    ):
        self.enabled = settings.skyscanner_affiliate_enabled if enabled is None else enabled
        self.media_partner_id = media_partner_id if media_partner_id is not None else settings.skyscanner_media_partner_id
        self.base_url = (base_url or settings.skyscanner_affiliate_base_url).rstrip("/")

    def can_generate(self) -> bool:
        return bool(self.enabled and self.media_partner_id)

    def build_day_view_link(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date | None = None,
        utm_term: str | None = None,
    ) -> str | None:
        return self._build(
            "day-view",
            {
                "origin": origin.upper(),
                "destination": destination.upper(),
                "departureDate": departure_date.isoformat(),
                "returnDate": return_date.isoformat() if return_date else None,
                "utm_term": utm_term,
            },
        )

    def build_browse_view_link(self, origin: str | None = None, destination: str | None = None) -> str | None:
        return self._build(
            "browse-view",
            {
                "origin": origin.upper() if origin else None,
                "destination": destination.upper() if destination else None,
            },
        )

    def build_multicity_link(self, legs: list[tuple[str, str, date]], utm_term: str | None = None) -> str | None:
        leg_value = ",".join(f"{origin.upper()}-{destination.upper()}-{travel_date.isoformat()}" for origin, destination, travel_date in legs)
        return self._build("multicity", {"legs": leg_value, "utm_term": utm_term})

    def _build(self, page_type: str, extra_params: dict[str, str | None]) -> str | None:
        if not self.can_generate():
            return None
        params = {
            "mediaPartnerId": self.media_partner_id,
            "utm_source": settings.skyscanner_affiliate_utm_source,
            "utm_medium": settings.skyscanner_affiliate_utm_medium,
            "utm_campaign": settings.skyscanner_affiliate_utm_campaign,
            **{key: value for key, value in extra_params.items() if value},
        }
        return f"{self.base_url}/flights/{page_type}?{urlencode(params)}"
