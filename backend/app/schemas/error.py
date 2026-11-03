"""Error signature schemas (novelty 8)."""

from datetime import datetime
from pydantic import BaseModel


class ErrorSignatureResponse(BaseModel):
    id: int
    signature_hash: str
    normalized_message: str
    occurrences: int
    first_seen: datetime
    last_seen: datetime

    model_config = {"from_attributes": True}
