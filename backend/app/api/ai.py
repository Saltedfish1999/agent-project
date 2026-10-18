import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.common.response import Response
from app.config import MODEL_REGISTRY
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.ai import ChatMessage, ChatRequest, ContinueRequest, RegenerateRequest
from app.service import agent_service, ai_service, conversation_service

router = APIRouter(prefix="/api/ai",tags=["agent"])

@router.post("/chat")
def chat(data:ChatRequest,current_user:User = Depends(get_current_user),db:Session = Depends(get_db)):
    content = agent_service.run_agent(db,current_user,data)
    return Response.success(data=ChatMessage(role="assistant",content=content))

def _sse_line(payload:dict) -> str:
    """拼接SSE帧"""
    return f"data:{json.dumps(payload,ensure_ascii=False)}\n\n"

@router.post("/chat/stream")
async def chat_stream(data:ChatRequest,current_user:User=Depends(get_current_user),db:Session = Depends(get_db)):
    async def event_gen():
        """内层生成器：取出业务事件，包装成SSE文本再往外yield"""
        async for event in agent_service.stream_agent(db,current_user,data):
            yield _sse_line(event)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream", # 标识SSE
        headers={
            "Cache-Control":"no-cache",
            "Connection":"keep-alive",
            "X-Accel-Buffering":"no"
        }
    )

@router.get("/conversations")
def list_conversations(    
    page:int=1,
    page_size:int=10,
    current_user:User = Depends(get_current_user),
    db:Session = Depends(get_db)
):
    res = conversation_service.get_conversation_list(db,current_user,page,page_size)
    return Response.success(data=res)

@router.get("/conversation/{thread_id}/messages")
async def get_conversation_messages(
    thread_id:str,
    current_user:User = Depends(get_current_user),
    db:Session = Depends(get_db)
):
    conversation_service.assert_owner(db,current_user,thread_id)
    messages = await agent_service.load_messages(thread_id)
    return Response.success(data=agent_service.to_chat_messages(messages))

@router.delete("/conversations/{thread_id}")
async def delete_conversation(
    thread_id:str,
    current_user:User = Depends(get_current_user),
    db:Session = Depends(get_db)
):
    conversation_service.delete_conversation(db,current_user,thread_id)
    await agent_service.delete_thread(thread_id)
    return Response.success()

@router.get("/models")
def list_models():
    """可选模型列表"""
    return Response.success(data=[
        {"id": k, "label": v["label"]}
        for k, v in MODEL_REGISTRY.items()
        if v.get("supports_tools")   
    ])

@router.post("/chat/continue")
async def chat_continue(data:ContinueRequest,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    async def event_gen():
        async for event in agent_service.continue_stream_agent(db,current_user,data):
            yield _sse_line(event)
    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

@router.post("/chat/regenerate")
async def chat_regenerate(data:RegenerateRequest,current_user:User=Depends(get_current_user),db:Session = Depends(get_db)):
    conversation_service.assert_owner(db,current_user,data.thread_id)

    async def event_gen():
        async for event in agent_service.regenerate_stream_agent(db, current_user, data):
            yield _sse_line(event)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache",
                 "Connection": "keep-alive",
                 "X-Accel-Buffering": "no"},
    )