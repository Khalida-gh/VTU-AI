"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator


class GenerateAnswerRequest(BaseModel):
    """Request body for POST /generate-answer."""

    topic: str = Field(
        ..., min_length=1, description="The topic/keyword or question to answer"
    )
    marks: int = Field(
        ...,
        gt=0,
        description="Marks the answer should be suitable for (2, 5, 8, or 10 recommended)",
    )
    subject: str = Field(
        default="BCS501",
        min_length=1,
        description="Subject code. Defaults to BCS501 while only one subject is indexed.",
    )

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("topic cannot be blank")
        return stripped

    @field_validator("subject")
    @classmethod
    def subject_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("subject cannot be blank")
        return stripped

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "Software Engineering process models",
                "marks": 10,
                "subject": "BCS501",
            }
        }


class SourceMetadata(BaseModel):
    """Metadata for one retrieved chunk, returned for debugging/citation tracing."""

    chunk_id: str
    source_file: str
    chunk_index: Union[int, str]
    char_count: Union[int, str]
    similarity: float


class GenerateAnswerResponse(BaseModel):
    """Response body for POST /generate-answer."""

    answer: str
    topic: str
    marks: int
    subject: str
    sources: list[SourceMetadata]
    plan: Optional[str] = Field(
        default=None,
        description="Internal answer-planning outline generated before the final "
        "answer, included for transparency/debugging.",
    )
class TranslateRequest(BaseModel):
    """Request body for POST /translate."""

    answer: str = Field(
        ...,
        min_length=1,
        description="Answer text to translate",
    )

    language: str = Field(
        ...,
        min_length=1,
        description="Target language",
    )

    @field_validator("answer")
    @classmethod
    def answer_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("answer cannot be blank")
        return stripped

    @field_validator("language")
    @classmethod
    def language_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("language cannot be blank")
        return stripped


class TranslateResponse(BaseModel):
    """Response body for POST /translate."""

    translated_answer: str
    language: str

class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    chromadb: str
    ollama: str