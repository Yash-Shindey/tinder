from datetime import datetime
from typing import List, Dict, Any
from uuid import UUID, uuid4
from sqlalchemy import String, Integer, DateTime, JSON, ForeignKey, Column
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Profile(Base):
    """SQLAlchemy model for Tinder profiles"""
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    bio = Column(String(1000))
    gender = Column(String(50))
    photos = Column(JSON, nullable=False)  # Array of photo URLs
    passions = Column(JSON)  # Array of passions
    education = Column(String(200))
    job_title = Column(String(200))
    location = Column(String(200))
    scraped_from_city = Column(String(100), nullable=False)
    scraped_from_country = Column(String(100), nullable=False)
    face_embedding = Column(JSON)  # 128D face embedding
    source = Column(String(50), nullable=False, default="tinder")
    scraped_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert model to dictionary matching JSON structure"""
        return {
            "id": self.id,
            "name": self.name,
            "age": self.age,
            "bio": self.bio,
            "gender": self.gender,
            "photos": self.photos,
            "passions": self.passions,
            "education": self.education,
            "job_title": self.job_title,
            "location": self.location,
            "scraped_from_city": self.scraped_from_city,
            "scraped_from_country": self.scraped_from_country,
            "source": self.source,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Profile':
        """Create Profile instance from dictionary"""
        return cls(
            name=data['name'],
            age=data['age'],
            bio=data.get('bio'),
            gender=data.get('gender'),
            photos=data['photos'],
            passions=data.get('passions'),
            education=data.get('education'),
            job_title=data.get('job_title'),
            location=data.get('location'),
            scraped_from_city=data['scraped_from_city'],
            scraped_from_country=data['scraped_from_country'],
            source=data.get('source', 'tinder'),
            scraped_at=datetime.fromisoformat(data['scraped_at']) if data.get('scraped_at') else datetime.utcnow()
        )

class Location(Base):
    """SQLAlchemy model for scraped locations"""
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True)
    city = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    latitude = Column(String(50))
    longitude = Column(String(50))
    last_scraped = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "city": self.city,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "last_scraped": self.last_scraped.isoformat() if self.last_scraped else None
        }

    @classmethod
    def from_config(cls, config: dict) -> 'Location':
        """Create Location instance from LocationConfig"""
        return cls(
            city=config['city'],
            country=config['country'],
            latitude=config.get('latitude'),
            longitude=config.get('longitude')
        ) 