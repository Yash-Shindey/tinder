import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import shortuuid
from tinderbotz.helpers.constants_helper import LocationConfig
import re
from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import sessionmaker
from db.models import Profile
from db import get_db

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/daterDB"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class SearchJob:
    """Represents a search job request"""
    def __init__(self, name: str, age: int, location: Dict[str, str], photos: List[str]):
        self.name = name
        self.age = age
        self.location = LocationConfig(city=location["city"], country=location["country"])
        self.photos = photos

    @classmethod
    def from_json(cls, data: Dict) -> 'SearchJob':
        """Create a SearchJob from JSON data"""
        return cls(
            name=data["name"],
            age=data["age"],
            location=data["location"],
            photos=data["photos"]
        )

def load_profiles(location: LocationConfig) -> List[Profile]:
    """Load all profiles for a specific location from database"""
    profiles = []
    db = SessionLocal()
    
    try:
        # Query profiles by scraped_from location
        stmt = select(Profile).where(
            Profile.scraped_from_city == location.city,
            Profile.scraped_from_country == location.country
        )
        profiles = db.execute(stmt).scalars().all()
        
        logger.info(f"✅ Loaded {len(profiles)} profiles from database for {location.city}, {location.country}")
        
    except Exception as e:
        logger.error(f"❌ Error loading profiles from database: {str(e)}")
        
    finally:
        db.close()
        
    return profiles

def run_fuzzy_match(search_job: SearchJob, profiles: List[Profile]) -> Optional[Dict]:
    """Run fuzzy matching on profiles that have already been location-validated"""
    if not profiles:
        return None
    
    # Filter profiles by name (case-insensitive) and age (±1 year)
    valid_matches = [
        profile for profile in profiles
        if profile.name.lower() == search_job.name.lower() and
        abs(profile.age - search_job.age) <= 1
    ]
    
    if not valid_matches:
        logger.info(f"❌ No matches found for {search_job.name} (age: {search_job.age})")
        return None
    
    # Sort by name similarity and age difference
    def match_score(profile: Profile) -> Tuple[int, int]:
        name_diff = abs(len(profile.name) - len(search_job.name))
        age_diff = abs(profile.age - search_job.age)
        return (name_diff, age_diff)
    
    # Get the best match
    best_match = min(valid_matches, key=match_score)
    
    # Calculate confidence score (higher is better)
    name_similarity = 1 - (abs(len(best_match.name) - len(search_job.name)) / max(len(best_match.name), len(search_job.name)))
    age_similarity = 1 - (abs(best_match.age - search_job.age) / max(best_match.age, search_job.age))
    confidence = (name_similarity + age_similarity) / 2
    
    return {
        "match": {
            "name": best_match.name,
            "age": best_match.age,
            "profile_location": best_match.location,
            "confidence": confidence
        },
        "scraped_from": {
            "city": best_match.scraped_from_city,
            "country": best_match.scraped_from_country
        },
        "metadata": {
            "bio": best_match.bio,
            "job": best_match.job_title,
            "education": best_match.education,
            "photos": best_match.photos
        }
    }

async def process_search_job(search_job: SearchJob) -> Optional[Dict]:
    """Process a search job and return the best match"""
    try:
        logger.info(f"🔍 Processing search job for {search_job.name} in {search_job.location.city}, {search_job.location.country}")
        
        # Load profiles for the specified location
        profiles = load_profiles(search_job.location)
        if not profiles:
            logger.warning(f"⚠️ No profiles found for {search_job.location.city}, {search_job.location.country}")
            return None
            
        # Run fuzzy matching
        result = run_fuzzy_match(search_job, profiles)
        if result:
            logger.info(f"✅ Found match: {result['match']['name']} (confidence: {result['match']['confidence']:.2f})")
        else:
            logger.info("❌ No matches found")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error processing search job: {str(e)}")
        return None

async def main():
    """Main function to process a search job from JSON input"""
    try:
        # Load search job from JSON file
        with open("search_job.json", 'r') as f:
            search_job_data = json.load(f)
        
        search_job = SearchJob.from_json(search_job_data)
        
        # Process the search job
        result = await process_search_job(search_job)
        
        # Print or return the result
        if result:
            print("\n🔍 Search Results:")
            print(f"Name: {result['match']['name']}")
            print(f"Age: {result['match']['age']}")
            print(f"Profile Location: {result['match']['profile_location']}")
            print(f"Scraped From: {result['scraped_from']['city']}, {result['scraped_from']['country']}")
            print(f"Confidence: {result['match']['confidence']:.2f}")
            
            print("\n📝 Additional Info:")
            print(f"Bio: {format_field(result['metadata']['bio'])}")
            print(f"Job: {format_field(result['metadata']['job'])}")
            print(f"Education: {format_field(result['metadata']['education'])}")
            
            # Display all photos
            photos = result['metadata']['photos']
            print(f"\n🖼️ Photos ({len(photos) if photos else 0}):")
            if photos:
                for url in photos:
                    print(f"  • {url}")
            else:
                print("  Not Provided")
                
        else:
            print("\n❌ No matches found")
            
    except Exception as e:
        logger.error(f"❌ Error in main: {str(e)}")

def format_field(value: Any, default: str = "Not Provided") -> str:
    """Format a field value, handling None and empty values"""
    if value is None or value == "":
        return default
    return str(value)

def format_timestamp(timestamp: datetime) -> str:
    """Format a datetime object into a readable string"""
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")

def format_photos(photos: List[str], max_display: int = 2) -> str:
    """Format photo URLs with a maximum display limit and better formatting"""
    if not photos:
        return "Not Provided"
    
    # Format each URL with proper indentation and bullet points
    photo_lines = [f"  • {url}" for url in photos[:max_display]]
    
    # Add ellipsis if there are more photos
    if len(photos) > max_display:
        photo_lines.append(f"  • ... and {len(photos) - max_display} more photos")
    
    return "\n".join(photo_lines)

def format_passions(passions: List[str]) -> str:
    """Format passions as a comma-separated list"""
    if not passions:
        return "Not Provided"
    return ", ".join(passions)

def display_match_result(profile: Profile, confidence: float) -> None:
    """Display a detailed match result from the database"""
    print("\n" + "="*50)
    print(f"✅ Match retrieved from PostgreSQL (ID: {profile.id})")
    print("="*50)
    
    # Basic Info
    print(f"\n👤 Name: {format_field(profile.name)}")
    print(f"🎂 Age: {format_field(profile.age)}")
    
    # Location Info
    print(f"\n🌍 Scraped From: {format_field(profile.scraped_from_city)}, {format_field(profile.scraped_from_country)}")
    print(f"📍 Profile Location: {format_field(profile.location)}")
    
    # Profile Details
    print(f"\n📝 Bio: {format_field(profile.bio)}")
    print(f"💼 Job: {format_field(profile.job_title)}")
    print(f"🎓 Education: {format_field(profile.education)}")
    
    # Photos
    print(f"\n🖼️ Photos ({len(profile.photos) if profile.photos else 0}):")
    print(format_photos(profile.photos))
    
    # Passions
    print(f"\n🎯 Passions: {format_passions(profile.passions)}")
    
    # Metadata
    print(f"\n📅 Scraped At: {format_timestamp(profile.created_at)}")
    print(f"Confidence Score: {confidence:.2f}")
    print("="*50 + "\n")

def search_profiles(location_city: str, location_country: str) -> List[Dict[str, Any]]:
    """Search for profiles in a specific location"""
    try:
        db = next(get_db())
        profiles = db.query(Profile).filter(
            and_(
                Profile.scraped_from_city == location_city,
                Profile.scraped_from_country == location_country
            )
        ).all()
        
        # Display each match with detailed information
        for profile in profiles:
            # For now, using a random confidence score
            # This would be replaced with actual matching logic
            confidence = random.uniform(0.5, 1.0)
            display_match_result(profile, confidence)
        
        return [profile.to_dict() for profile in profiles]
        
    except Exception as e:
        logger.error(f"❌ Error searching profiles: {str(e)}")
        return []
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
    # Example usage
    results = search_profiles("New York", "USA")
    logger.info(f"Found {len(results)} profiles") 