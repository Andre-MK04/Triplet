from pydantic import BaseModel


class AmadeusTokenResponse(BaseModel):
    access_token: str
    expires_in: int
    token_type: str | None = None
