"""Health check API schemas."""

from typing import Literal

from pydantic import BaseModel, Field

HealthStatus = Literal["ok", "degraded"]
DatabaseStatus = Literal["connected", "disconnected"]


class HealthResponse(BaseModel):
    status: HealthStatus = Field(description="Overall process health")
    database: DatabaseStatus = Field(description="Result of a live database ping")
