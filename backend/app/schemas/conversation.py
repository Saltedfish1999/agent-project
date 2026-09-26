from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationResponse(BaseModel):
    """对话列表"""
    thread_id:str
    title:str | None = None
    create_time: datetime | None = None
    update_time: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

class ChatMessageResponse(BaseModel):
    """回放的消息"""
    role:str
    content:str