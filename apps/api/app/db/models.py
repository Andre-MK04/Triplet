from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AirportAreaDB(Base):
    __tablename__ = "airport_areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)

    airports: Mapped[list["AirportDB"]] = relationship(back_populates="area")


class AirportDB(Base):
    __tablename__ = "airports"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(80))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_id: Mapped[int | None] = mapped_column(ForeignKey("airport_areas.id"), nullable=True)
    is_user_origin_candidate: Mapped[bool] = mapped_column(Boolean, default=False)

    area: Mapped[AirportAreaDB | None] = relationship(back_populates="airports")


class FlightDB(Base):
    __tablename__ = "flights"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    origin_code: Mapped[str] = mapped_column(ForeignKey("airports.code"), index=True)
    destination_code: Mapped[str] = mapped_column(ForeignKey("airports.code"), index=True)
    departure_datetime: Mapped[datetime] = mapped_column(DateTime)
    arrival_datetime: Mapped[datetime] = mapped_column(DateTime)
    airline: Mapped[str] = mapped_column(String(120))
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    booking_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    baggage_included: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str] = mapped_column(String(80), default="mock")
    observed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    provider_offer_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    deep_link: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    affiliate_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    stops: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_provider_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)


class PriceObservationDB(Base):
    __tablename__ = "price_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    origin_code: Mapped[str] = mapped_column(String(8), index=True)
    destination_code: Mapped[str] = mapped_column(String(8), index=True)
    departure_date: Mapped[date] = mapped_column(Date, index=True)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    observed_price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    observed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    confidence: Mapped[str] = mapped_column(String(16), default="indicative")
    link_available: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_hash: Mapped[str] = mapped_column(String(64), index=True)


class GroundTransferDB(Base):
    __tablename__ = "ground_transfers"
    __table_args__ = (UniqueConstraint("from_airport_code", "to_airport_code", name="uq_transfer_airports"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_airport_code: Mapped[str] = mapped_column(ForeignKey("airports.code"), index=True)
    to_airport_code: Mapped[str] = mapped_column(ForeignKey("airports.code"), index=True)
    from_city: Mapped[str] = mapped_column(String(120))
    to_city: Mapped[str] = mapped_column(String(120))
    duration_hours: Mapped[float] = mapped_column(Float)
    estimated_cost: Mapped[float] = mapped_column(Float)
    mode: Mapped[str] = mapped_column(String(40))


class SearchLogDB(Base):
    __tablename__ = "search_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    origin_airports: Mapped[list[str]] = mapped_column(JSON)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    min_trip_length_days: Mapped[int] = mapped_column(Integer)
    max_trip_length_days: Mapped[int] = mapped_column(Integer)
    max_budget: Mapped[float] = mapped_column(Float)
    max_ground_transfer_hours: Mapped[float] = mapped_column(Float)
    trip_style: Mapped[str] = mapped_column(String(40))
    result_count: Mapped[int] = mapped_column(Integer)


class SavedSearchDB(Base):
    __tablename__ = "saved_searches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    origin_airports: Mapped[list[str]] = mapped_column(JSON)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    min_trip_length_days: Mapped[int] = mapped_column(Integer)
    max_trip_length_days: Mapped[int] = mapped_column(Integer)
    max_budget: Mapped[float] = mapped_column(Float)
    max_ground_transfer_hours: Mapped[float] = mapped_column(Float)
    trip_style: Mapped[str] = mapped_column(String(40))
    direct_only: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    include_baggage: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    frequency: Mapped[str] = mapped_column(String(20), default="daily")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_best_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_best_trip_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manage_token_hash: Mapped[str] = mapped_column(String(128))
    unsubscribe_token_hash: Mapped[str] = mapped_column(String(128))

    runs: Mapped[list["AlertRunDB"]] = relationship(back_populates="saved_search")
    deliveries: Mapped[list["AlertDeliveryDB"]] = relationship(back_populates="saved_search")
    user: Mapped["UserDB | None"] = relationship(back_populates="saved_searches")


class AlertRunDB(Base):
    __tablename__ = "alert_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    saved_search_id: Mapped[str] = mapped_column(ForeignKey("saved_searches.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    provider_used: Mapped[str | None] = mapped_column(String(80), nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    best_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    saved_search: Mapped[SavedSearchDB] = relationship(back_populates="runs")
    deliveries: Mapped[list["AlertDeliveryDB"]] = relationship(back_populates="alert_run")


class AlertDeliveryDB(Base):
    __tablename__ = "alert_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    saved_search_id: Mapped[str] = mapped_column(ForeignKey("saved_searches.id"), index=True)
    alert_run_id: Mapped[str | None] = mapped_column(ForeignKey("alert_runs.id"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    saved_search: Mapped[SavedSearchDB] = relationship(back_populates="deliveries")
    alert_run: Mapped[AlertRunDB | None] = relationship(back_populates="deliveries")


class UserDB(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    plan: Mapped[str] = mapped_column(String(40), default="free")
    subscription_status: Mapped[str] = mapped_column(String(40), default="none")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    saved_searches: Mapped[list[SavedSearchDB]] = relationship(back_populates="user")
    refresh_sessions: Mapped[list["RefreshTokenSessionDB"]] = relationship(back_populates="user")
    oauth_accounts: Mapped[list["UserOAuthAccountDB"]] = relationship(back_populates="user")
    billing_subscriptions: Mapped[list["BillingSubscriptionDB"]] = relationship(back_populates="user")


class UserOAuthAccountDB(Base):
    __tablename__ = "user_oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_user_oauth_provider_subject"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    provider_user_id: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped[UserDB] = relationship(back_populates="oauth_accounts")


class RefreshTokenSessionDB(Base):
    __tablename__ = "refresh_token_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)

    user: Mapped[UserDB] = relationship(back_populates="refresh_sessions")


class PasswordResetTokenDB(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EmailVerificationTokenDB(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BillingSubscriptionDB(Base):
    __tablename__ = "billing_subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(120), index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    plan: Mapped[str] = mapped_column(String(40), default="free")
    status: Mapped[str] = mapped_column(String(40), default="none")
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    trial_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    raw_last_event_type: Mapped[str | None] = mapped_column(String(120), nullable=True)

    user: Mapped[UserDB] = relationship(back_populates="billing_subscriptions")


class BillingEventDB(Base):
    __tablename__ = "billing_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    stripe_event_id: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(120))
    processed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processing_status: Mapped[str] = mapped_column(String(40))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class UsageCounterDB(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint("user_id", "feature", "period_start", "period_end", name="uq_usage_user_feature_period"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    feature: Mapped[str] = mapped_column(String(80), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
