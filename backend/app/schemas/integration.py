from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class IntegrationSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: Literal["PENDING", "SUCCEEDED", "FAILED", "UNCERTAIN"]
    external_data_id: str | None
    attempt_count: int
    last_error_code: str | None
    last_error_message: str | None
    created_at: datetime
    updated_at: datetime
    succeeded_at: datetime | None


class IntegrationSnapshotPayload(BaseModel):
    snapshot: IntegrationSnapshotResponse | None
