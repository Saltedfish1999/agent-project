from pydantic import BaseModel

class ChatMessage(BaseModel):
    role:str
    content:str

class ChatRequest(BaseModel):
    messages:list[ChatMessage]
    thread_id:str | None = None