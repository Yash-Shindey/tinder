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
    bio = Column(String(1000), nullable=True)
    gender = Column(String(50), nullable=True)
    photos = Column(JSON, nullable=False)  # Array of photo URLs
    passions = Column(JSON, nullable=True)  # Array of passions
    education = Column(String(200), nullable=True)
    job_title = Column(String(200), nullable=True)
    location = Column(String(200), nullable=True)
    scraped_from_city = Column(String(100), nullable=False)
    scraped_from_country = Column(String(100), nullable=False)
    face_embedding = Column(JSON, nullable=True)  # Array of 128 floats
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
            "scraped_from": {
                "city": self.scraped_from_city,
                "country": self.scraped_from_country
            },
            "face_embedding": self.face_embedding,
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Profile':
        """Create Profile instance from dictionary"""
        scraped_from = data.get('scraped_from', {})
        return cls(
            name=data.get('name'),
            age=data.get('age'),
            bio=data.get('bio'),
            gender=data.get('gender'),
            photos=data.get('photos', []),
            passions=data.get('passions', []),
            education=data.get('education'),
            job_title=data.get('job_title'),
            location=data.get('location'),
            scraped_from_city=scraped_from.get('city'),
            scraped_from_country=scraped_from.get('country'),
            face_embedding=data.get('face_embedding')
        )

class Location(Base):
    """SQLAlchemy model for scraped locations"""
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True)
    city = Column(String(100), nullable=False)
    country = Column(String(100), nullable=False)
    latitude = Column(String(50), nullable=False)
    longitude = Column(String(50), nullable=False)
    last_scraped = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    @classmethod
    def from_config(cls, config: 'LocationConfig') -> 'Location':
        """Create Location instance from LocationConfig"""
        coords = config.get_coordinates()
        return cls(
            city=config.city,
            country=config.country,
            latitude=str(coords[0]),
            longitude=str(coords[1])
        ) 