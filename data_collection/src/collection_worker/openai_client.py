from __future__ import annotations

import hashlib
from dataclasses import dataclass

from openai import OpenAI

from collection_worker.config import Settings
from collection_worker.contracts import SpotObservationBatch
from collection_worker.errors import PolicyError, TemporarySourceError


EXTRACTION_INSTRUCTIONS = """公開Web本文からSpotの明示的な事実だけを抽出してください。
不明な値は推測せず null または unknown にしてください。住所、座標、営業時間、駐車場、
二輪可否、営業状態を混同しないでください。説明文と特徴は分離し、抽出した値には
短い根拠 excerpt を付けてください。ページに複数Spotがあれば分離してください。"""


@dataclass
class ExtractionResult:
    batch: SpotObservationBatch | None
    response_id: str | None
    model: str
    status: str
    input_hash: str
    input_tokens: int | None
    output_tokens: int | None
    error_code: str | None = None


class OpenAIExtractor:
    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise PolicyError("OPENAI_API_KEY is required for AI extraction")
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai.request_timeout_seconds,
            max_retries=settings.openai.max_retries,
        )

    def extract(self, text: str, source_url: str) -> ExtractionResult:
        input_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        last_error = None
        for attempt in range(2):
            try:
                response = self.client.responses.parse(
                    model=self.settings.openai.extraction_model,
                    instructions=EXTRACTION_INSTRUCTIONS,
                    input=f"Source URL: {source_url}\n\n{text}",
                    text_format=SpotObservationBatch,
                    store=False,
                )
                raw_status = getattr(response, "status", "completed")
                status = str(getattr(raw_status, "value", raw_status))
                parsed = getattr(response, "output_parsed", None)
                usage = getattr(response, "usage", None)
                if status != "completed":
                    last_error = "INCOMPLETE"
                    continue
                if parsed is None:
                    last_error = "REFUSED_OR_INVALID"
                    break
                return ExtractionResult(
                    batch=parsed,
                    response_id=getattr(response, "id", None),
                    model=getattr(response, "model", self.settings.openai.extraction_model),
                    status="completed",
                    input_hash=input_hash,
                    input_tokens=getattr(usage, "input_tokens", None),
                    output_tokens=getattr(usage, "output_tokens", None),
                )
            except Exception as exc:
                last_error = type(exc).__name__
                if attempt == 0:
                    continue
        if last_error in {"INCOMPLETE", "REFUSED_OR_INVALID"}:
            return ExtractionResult(
                batch=None,
                response_id=None,
                model=self.settings.openai.extraction_model,
                status="incomplete" if last_error == "INCOMPLETE" else "invalid",
                input_hash=input_hash,
                input_tokens=None,
                output_tokens=None,
                error_code=last_error,
            )
        raise TemporarySourceError(f"OpenAI extraction failed: {last_error}")
