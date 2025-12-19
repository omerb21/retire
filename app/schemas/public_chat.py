from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class PublicChatStartRequest(BaseModel):
    id_number: str
    initial_tokens: int | None = None


class PublicChatStartResponse(BaseModel):
    session_key: str
    client_id: int
    client_name: str | None = None
    token_balance: int
    llm_provider: str | None = None
    llm_backend: str | None = None
    llm_model_name: str | None = None


class PublicChatStatusResponse(BaseModel):
    session_key: str
    client_id: int
    client_name: str | None = None
    token_balance: int
    tokens_spent: int
    is_active: bool
    llm_provider: str | None = None
    llm_backend: str | None = None
    llm_model_name: str | None = None


class PublicChatMessageDto(BaseModel):
    role: str
    content: str
    estimated_tokens: int = 0


class PublicChatHistoryResponse(BaseModel):
    session_key: str
    messages: List[PublicChatMessageDto]


class PublicChatSendMessageRequest(BaseModel):
    content: str


class PublicChatSendMessageResponse(BaseModel):
    reply: str
    token_balance: int
    tokens_spent: int
    tokens_used: int
    depleted: bool


class PublicChatTopUpRequest(BaseModel):
    session_key: str
    tokens: int

    model_config = ConfigDict(protected_namespaces=())


class PublicChatTopUpResponse(BaseModel):
    session_key: str
    token_balance: int
    tokens_spent: int

    model_config = ConfigDict(protected_namespaces=())
