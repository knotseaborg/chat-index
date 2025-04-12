from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Thread(Base):
    __tablename__ = "threads"
    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String, nullable=True)
    prompt = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now)

    # Relationships
    messages = relationship("Message", back_populates="thread", cascade="all, delete-orphan")
    links = relationship("Link", back_populates="thread", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False)
    content = Column(String, nullable=False)
    embedding_file = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now)

    # Relationships
    thread = relationship("Thread", back_populates="messages")

    # Link relationships
    previous_links = relationship(
        "Link",
        back_populates="next_message",
        foreign_keys="Link.next_message_id"
    )
    next_links = relationship(
        "Link",
        back_populates="previous_message",
        foreign_keys="Link.previous_message_id"
    )

    # Summary links
    summaries_starting_here = relationship(
        "Summary",
        back_populates="start_message",
        foreign_keys="Summary.start_message_id"
    )
    summaries_ending_here = relationship(
        "Summary",
        back_populates="end_message",
        foreign_keys="Summary.end_message_id"
    )


class Summary(Base):
    __tablename__ = "summaries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(String, nullable=False)
    embedding_file = Column(String, nullable=True)
    start_message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    end_message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    created_at = Column(DateTime, default=func.now)

    # Relationships
    start_message = relationship(
        "Message",
        back_populates="summaries_starting_here",
        foreign_keys=[start_message_id]
    )
    end_message = relationship(
        "Message",
        back_populates="summaries_ending_here",
        foreign_keys=[end_message_id]
    )


class Link(Base):
    __tablename__ = "links"
    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False)
    previous_message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    next_message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    created_at = Column(DateTime, default=func.now)

    # Relationships
    thread = relationship("Thread", back_populates="links")
    previous_message = relationship(
        "Message",
        back_populates="next_links",
        foreign_keys=[previous_message_id]
    )
    next_message = relationship(
        "Message",
        back_populates="previous_links",
        foreign_keys=[next_message_id]
    )
