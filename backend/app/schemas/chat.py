from datetime import datetime
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    task_id: int | None = None


class ChatTurn(BaseModel):
    id: int
    run_id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    run_id: int
    model: str
    reply: str
    memory_messages_used: int
    context_original_chars: int
    context_sent_chars: int
    context_reduction_pct: float
    summary_updated: bool


class MemoryResponse(BaseModel):
    agent_id: int
    messages: list[ChatTurn]


class MemorySummaryResponse(BaseModel):
    agent_id: int
    summary: str
    summarized_through_id: int
    source_message_count: int
    source_chars: int
    summary_chars: int
    reduction_pct: float
