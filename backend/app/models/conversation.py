from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Conversation(Base):
    __tablename__ = "conversation"
    __table_args__ = {"comment":"AI对话记录"}

    thread_id:Mapped[str] = mapped_column(
        String(64),unique=True,index=True,comment="会话ID",nullable=False
    )

    user_id:Mapped[int] = mapped_column(
        ForeignKey("users.id"),index=True,comment="所属用户",nullable=False
    )

    title:Mapped[str] = mapped_column(
        String(60),comment="会话标题",nullable=True
    )