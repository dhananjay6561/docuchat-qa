"""Request/response models. These also drive the OpenAPI spec that the API tests validate against."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64, examples=["demo-session-1"])
    message: str = Field(min_length=1, max_length=2000, examples=["How many days of annual leave do I get?"])


class Source(BaseModel):
    doc: str = Field(description="Document name, e.g. 'leave_policy'")
    chunk_id: str = Field(description="Chunk identifier, e.g. 'leave_policy#2'")
    snippet: str = Field(description="First part of the chunk text, shown in the UI")


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[Source]
    refused: bool = Field(description="True when the assistant declined because the docs don't cover it")
    tool_calls: list[str] = Field(default_factory=list, description="Names of tools called for this answer")
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    provider: str
    chunks_indexed: int
