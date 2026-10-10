from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import Settings, get_settings
from .contracts import AcceptedResponse, InteractionBatch, RecommendationRequest, RecommendationResponse
from .providers import AppleMapsRouteProvider, ApproximateRouteProvider, DatabaseCachingRouteProvider
from .rate_limit import SlidingWindowRateLimiter
from .recommendation import RecommendationEngine, RouteProviderUnavailable, search_radius_km
from .repository import Repository

logger = logging.getLogger("bike_easyfinder_api")


class HealthResponse(BaseModel):
    status: str


def _problem(
    request: Request,
    status_code: int,
    code: str,
    title: str,
    detail: str = "",
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": f"https://api.bike-easyfinder.invalid/problems/{code.lower()}",
            "title": title,
            "status": status_code,
            "code": code,
            "detail": detail,
            "request_id": request.state.request_id,
        },
        headers=headers,
    )


def create_app(
    settings: Settings | None = None,
    *,
    repository: Repository | None = None,
    engine: RecommendationEngine | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    repository = repository or Repository(settings.database_url)
    if engine is None:
        provider = (
            AppleMapsRouteProvider(
                settings.apple_maps_access_token or "",
                settings.apple_maps_directions_url,
                timeout_seconds=min(3.5, settings.request_deadline_seconds),
            )
            if settings.route_provider == "apple"
            else ApproximateRouteProvider()
        )
        provider = DatabaseCachingRouteProvider(repository.engine, provider)
        engine = RecommendationEngine(
            provider,
            rule_version=settings.recommendation_rule_version,
            data_version=settings.data_version,
            deadline_seconds=settings.request_deadline_seconds,
        )
    limiter = SlidingWindowRateLimiter()

    app = FastAPI(
        title="Bike EasyFinder MVP API",
        version="1.1.0",
        docs_url="/docs" if settings.app_env in {"local", "test"} else None,
        redoc_url=None,
    )
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_methods=["POST", "DELETE"],
            allow_headers=["Content-Type", "X-Request-ID", "X-Installation-ID", "X-Deletion-Token-Hash", "X-Deletion-Token"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID")
        try:
            request_id = str(UUID(incoming)) if incoming else str(uuid4())
        except ValueError:
            request_id = str(uuid4())
        request.state.request_id = request_id
        started = time.monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_finished method=%s path=%s status=%s duration_ms=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            round((time.monotonic() - started) * 1000),
            request_id,
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        too_many_events = any(
            error.get("type") == "too_long" and "events" in error.get("loc", ())
            for error in exc.errors()
        )
        if too_many_events:
            return _problem(request, 413, "PAYLOAD_TOO_LARGE", "At most 50 events are accepted", str(exc))
        return _problem(request, 422, "VALIDATION_ERROR", "Request validation failed", str(exc))

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return _problem(
            request,
            exc.status_code,
            "HTTP_ERROR",
            str(exc.detail),
            headers=exc.headers,
        )

    def enforce_limit(request: Request, bucket: str, limit: int, window: int) -> None:
        client = request.client.host if request.client else "unknown"
        result = limiter.check(client, bucket, limit, window)
        if not result.allowed:
            raise HTTPException(
                status_code=429,
                detail=f"rate limit exceeded; retry after {result.retry_after} seconds",
                headers={"Retry-After": str(result.retry_after)},
            )

    @app.get("/healthz", response_model=HealthResponse, include_in_schema=False)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post("/v1/recommendations", response_model=RecommendationResponse)
    def recommendations(payload: RecommendationRequest, request: Request) -> RecommendationResponse:
        enforce_limit(request, "recommendations", 30, 600)
        spots = repository.nearby_spots(payload.origin, search_radius_km(payload.available_minutes))
        try:
            return engine.recommend(payload, spots)
        except RouteProviderUnavailable as exc:
            raise HTTPException(status_code=503, detail="route provider unavailable") from exc

    @app.post("/v1/interactions", response_model=AcceptedResponse, status_code=202)
    def interactions(
        payload: InteractionBatch,
        request: Request,
        installation_id: UUID = Header(alias="X-Installation-ID"),
        deletion_token_hash: str = Header(alias="X-Deletion-Token-Hash", min_length=64, max_length=64),
    ) -> AcceptedResponse:
        enforce_limit(request, "interactions", 60, 600)
        try:
            accepted = repository.record_interactions(installation_id, deletion_token_hash, payload)
        except (ValueError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail="invalid installation credentials") from exc
        return AcceptedResponse(accepted=accepted)

    @app.delete("/v1/installations/{installation_id}/data", status_code=202)
    def delete_installation_data(
        installation_id: UUID,
        request: Request,
        deletion_token: str = Header(alias="X-Deletion-Token", min_length=32),
    ) -> Response:
        enforce_limit(request, "deletion", 5, 86_400)
        repository.request_deletion(installation_id, deletion_token)
        # Deliberately identical for matching, missing, and mismatching credentials.
        return Response(status_code=status.HTTP_202_ACCEPTED)

    return app


app = create_app()
