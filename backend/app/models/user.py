from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    preference = relationship(
        "Preference", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    observations = relationship("BehaviorObservation", back_populates="user", cascade="all, delete-orphan")
    twin_traits = relationship("TwinTrait", back_populates="user", cascade="all, delete-orphan")
