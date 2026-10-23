from datetime import datetime
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.common.response import pageResponse
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.conversation import ConversationResponse


def resolve_thread(db:Session,current_user:User,thread_id:str|None,question:str) -> tuple[str,bool]:
    """拿到当前user的thread_id，并告诉调用方这次是不是新建的会话"""
    if not thread_id:
        return str(uuid4()), False

    conv = db.query(Conversation).filter(Conversation.thread_id == thread_id).first()

    if conv is None:
        conv = Conversation(
            thread_id = thread_id,
            user_id = current_user.id,
            title = question[:30]
        )
        db.add(conv)
        try:
            db.commit()
            return thread_id, True
        except IntegrityError:
            db.rollback()
            return thread_id, False

    if conv.user_id != current_user.id:
        raise BusinessException(message="无权访问该对话",code=403)

    conv.update_time = datetime.now()
    db.commit()
    return thread_id, not (conv.summary or "").strip()

def get_conversation_list(db:Session,current_user:User,page:int,page_size:int, keyword: str | None = None):
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(Conversation.title.like(like),Conversation.summary.like(like)))

    total = query.count()
    items = (query.order_by(Conversation.update_time.desc())
             .offset((page - 1) * page_size).limit(page_size).all())

    return pageResponse(
        list=[ConversationResponse.model_validate(item) for item in items],
        total=total,
    )

def assert_owner(db:Session,current_user:User,thread_id:str) -> Conversation:
    """校验会话是否属于用户"""
    conv = db.query(Conversation).filter(Conversation.thread_id == thread_id).first()
    if conv is None:
        raise BusinessException(message="对话不存在")
    if conv.user_id != current_user.id:
        raise BusinessException(message="无权访问该对话")
    return conv;

def delete_conversation(db:Session,current_user:User,thread_id:str|None):
    conv = assert_owner(db,current_user,thread_id) # 归属校验
    db.delete(conv)
    db.commit()


def update_conversation_meta(db:Session,thread_id:str,title:str|None = None,summary:str|None = None) -> None:
    """更新会话标题和总结"""
    conv = db.query(Conversation).filter(Conversation.thread_id == thread_id).first()
    if conv is None:
        return
    if title:
        conv.title = title[:60]
    if summary:
        conv.summary = summary[:200]
    db.commit()

def rename_conversation_title(db:Session,current_user:User,thread_id:str,summary:str) -> Conversation:
    """标题重命名"""
    conv = assert_owner(db,current_user,thread_id)
    summary = (summary or "").strip()

    if not summary:
        raise BusinessException(message="标题不能为空")
    if len(summary) > 60:
        raise BusinessException(message="标题不能超过60")
    conv.summary = summary
    db.commit()
    db.refresh(conv)
    return conv