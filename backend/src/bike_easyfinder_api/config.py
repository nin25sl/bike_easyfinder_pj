from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "test", "staging", "production"] = "local"
    database_url: str = "postgresql+psycopg://bike:bike_local_only@db:5432/bike_easyfinder"
    route_provider: Literal["approximate", "apple"] = "approximate"
    apple_maps_access_token: str | None = None
    apple_maps_directions_url: str = "https://maps-api.apple.com/v1/directions"
    recommendation_rule_version: str = "mvp-1.2"
    data_version: str = "canonical-local"
    request_deadline_seconds: float = Field(default=4.0, gt=0, le=10)
    cors_origins: str = ""

    @model_validator(mode="after")
    def reject_mock_provider_in_shared_environments(self) -> "Settings":
        if self.app_env in {"staging", "production"} and self.route_provider == "approximate":
            raise ValueError("ROUTE_PROVIDER=approximate is allowed only for local/test")
        if self.route_provider == "apple" and not self.apple_maps_access_token:
            raise ValueError("APPLE_MAPS_ACCESS_TOKEN is required for ROUTE_PROVIDER=apple")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
