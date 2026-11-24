"""SQLAlchemy ORM models stored in PostgreSQL.

FAISS still holds the embeddings for similarity search; PostgreSQL is the
system of record for the indexed documents and chunks, chat history, the
query log, and the customer reviews dataset (products, reviews, monthly sales
and the AI review insights).
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Document(Base):
    """A PDF in data/policies/ that has been chunked and indexed."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class Chunk(Base):
    """One retrievable passage; `faiss_id` is its row in the FAISS index."""

    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    faiss_id: Mapped[str] = mapped_column(String(64), index=True)
    page: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Message.id",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # "user" | "assistant"
    text: Mapped[str] = mapped_column(Text)
    found: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sources: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class QueryLog(Base):
    """Every /qa/ask call, for analytics and tuning the relevance threshold."""

    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    found: Mapped[bool] = mapped_column(Boolean)
    result_count: Mapped[int] = mapped_column(Integer)
    top_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    top_document: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float)
    embedding_model: Mapped[str] = mapped_column(String(128))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


# --- Customer reviews dataset ---------------------------------------------------


class Product(Base):
    """A product Honeycrumb sells (catalog from the product marketing guide)."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    category: Mapped[str] = mapped_column(String(64))
    price: Mapped[float] = mapped_column(Float)
    # When the product is on the menu, e.g. "Year-round" or "Nov–Dec".
    availability: Mapped[str] = mapped_column(String(64), default="Year-round")
    description: Mapped[str] = mapped_column(Text, default="")

    reviews: Mapped[list["Review"]] = relationship(back_populates="product")


class Review(Base):
    """One customer review. `sentiment`, `confidence` and `topics` are set by the AI agent."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    customer: Mapped[str] = mapped_column(String(64))
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(32))
    city: Mapped[str] = mapped_column(String(64))
    review_date: Mapped[date] = mapped_column(Date, index=True)
    sentiment: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    topics: Mapped[list[str]] = mapped_column(JSONB, default=list)
    analysed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    product: Mapped[Product] = relationship(back_populates="reviews")


class ProductSale(Base):
    """Units sold of one product in one month (the first day of the month)."""

    __tablename__ = "product_sales"
    __table_args__ = (UniqueConstraint("product_id", "month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    month: Mapped[date] = mapped_column(Date)
    units: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[float] = mapped_column(Float)


class ReviewInsight(Base):
    """A saved AI report on the reviews: computed statistics plus the agent's findings."""

    __tablename__ = "review_insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String(128))
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB)
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
