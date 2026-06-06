"""RAG API request/response schemas.

Raw embeddings are never included in any response.
Document content is never included in logs.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)
    document_id: UUID
    filename: str
    status: str
    chunk_count: int


class SearchRequest(BaseModel):
    project_id: UUID
    query: str = Field(min_length=1, max_length=4096)
    top_k: int = Field(default=5, ge=1, le=20)


class ChunkResult(BaseModel):
    """One retrieved chunk — content excerpt only, no raw embedding."""

    document_id: UUID
    filename: str
    chunk_index: int
    citation_label: str
    excerpt: str  # first 500 chars of chunk content, safe to return


class SearchResponse(BaseModel):
    results: list[ChunkResult]
    query_chars: int  # length of query, never the query itself


class AskRequest(BaseModel):
    project_id: UUID
    question: str = Field(min_length=1, max_length=4096)
    top_k: int = Field(default=5, ge=1, le=20)


class Citation(BaseModel):
    document_id: UUID
    filename: str
    chunk_index: int
    citation_label: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    provider: str = "ollama"
    model: str = "llama3.1"


class DocumentListItem(BaseModel):
    model_config = ConfigDict(from_attributes=False)
    document_id: UUID
    filename: str
    content_type: str
    status: str
    created_at: datetime
