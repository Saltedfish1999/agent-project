from pydantic import BaseModel

class ChatMessage(BaseModel):
    role:str
    content:str

class ChatRequest(BaseModel):
    messages:list[ChatMessage]
    thread_id:str | None = None
    model:str|None = None
    enable_web:bool=False

class ContinueRequest(BaseModel):
    thread_id:str
    content:str
    model: str | None = None

class RegenerateRequest(BaseModel):
    thread_id:str
    model: str | None = None
    attempt:int=0