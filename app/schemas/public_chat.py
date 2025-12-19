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


class PublicChatStatusResponse(BaseModel):
    session_key: str
    client_id: int
    client_name: str | None = None
    token_balance: int
    tokens_spent: int
    is_active: bool


class PublicChatMessageDto(BaseModel):
    role: str
    content: str


class PublicChatHistoryResponse(BaseModel):
    session_key: str
    messages: List[PublicChatMessageDto]


class PublicChatSendMessageRequest(BaseModel):
    content: str


class PublicChatSendMessageResponse(BaseModel):
    reply: str
    token_balance: int
    tokens_spent: int
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
