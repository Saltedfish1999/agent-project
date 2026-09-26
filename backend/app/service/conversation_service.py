from datetime import datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.common.response import pageResponse
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.conversation import ConversationResponse


def resolve_thread(db:Session,current_user:User,thread_id:str|None,question:str) -> str:
    """拿到当前user的thread_id"""
    if not thread_id:
        return str(uuid4())

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
        except IntegrityError:
            db.rollback()
    elif conv.user_id != current_user.id:
        raise BusinessException(message="无权访问该对话",code=403)
    else:
        conv.update_time = datetime.now()
        db.commit()
    return thread_id

def get_conversation_list(db:Session,current_user:User,page:int,page_size:int):
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
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