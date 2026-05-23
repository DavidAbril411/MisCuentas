"""SQLAlchemy ORM models. Mirror schema.sql; CHECK constraints live in the DDL."""

from datetime import date, datetime
from sqlalchemy import (
    Integer, String, Text, ForeignKey, Date, DateTime
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Flask-Login UserMixin equivalents
    @property
    def is_authenticated(self) -> bool: return True
    @property
    def is_active(self) -> bool: return True
    @property
    def is_anonymous(self) -> bool: return False
    def get_id(self) -> str: return str(self.id)


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    opening_balance_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opening_fx_rate_to_ars_micro: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    archived: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_credit_card: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)


class RecurringRule(Base):
    __tablename__ = "recurring_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    account: Mapped[Account] = relationship()
    category: Mapped[Category | None] = relationship()


class Debt(Base):
    __tablename__ = "debts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    counterparty: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    principal_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    fx_rate_to_ars_micro: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opened_on: Mapped[date] = mapped_column(Date, nullable=False)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    payments: Mapped[list["Transaction"]] = relationship(back_populates="debt")


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    fx_rate_to_ars_micro: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    recurring_rule_id: Mapped[int | None] = mapped_column(ForeignKey("recurring_rules.id"), nullable=True)
    debt_id: Mapped[int | None] = mapped_column(ForeignKey("debts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    account: Mapped[Account] = relationship()
    category: Mapped[Category | None] = relationship()
    rule: Mapped[RecurringRule | None] = relationship()
    debt: Mapped[Debt | None] = relationship(back_populates="payments")


class FxRate(Base):
    __tablename__ = "fx_rates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    effective_on: Mapped[date] = mapped_column(Date, nullable=False)
    rate_to_ars_micro: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Meta(Base):
    __tablename__ = "meta"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
