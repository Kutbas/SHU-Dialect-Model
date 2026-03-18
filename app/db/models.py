from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm import declarative_base

# 声明 ORM 基类
Base = declarative_base()


class SessionModel(Base):
    __tablename__ = "sessions"

    # 对应 C++ 的 session_id TEXT PRIMARY KEY
    session_id = Column(String, primary_key=True, index=True)
    model_name = Column(String, nullable=False)
    create_time = Column(Integer, nullable=False)
    update_time = Column(Integer, nullable=False)

    # 建立与 MessageModel 的一对多关联，设置级联删除 (对应 C++ ON DELETE CASCADE)
    messages = relationship(
        "MessageModel", back_populates="session", cascade="all, delete-orphan"
    )


class MessageModel(Base):
    __tablename__ = "messages"

    message_id = Column(String, primary_key=True, index=True)
    # 外键约束
    session_id = Column(
        String, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    timestamp = Column(Integer, nullable=False)

    # 反向关联
    session = relationship("SessionModel", back_populates="messages")
