import argparse
import json
import os
from typing import Optional, Dict, List, Union
import face_recognition
import numpy as np
from PIL import Image
import requests
from io import BytesIO
from db import get_db
from db.models import Profile
from sqlalchemy import and_, or_
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class SearchJob:
    def __init__(self, name: str, age: int, city: str, country: str, image_path: str,
                 age_min: Optional[int] = None, age_max: Optional[int] = None,
                 city_only: bool = False, name_contains: Optional[str] = None):
        self.name = name
        self.age = age
        self.city = city
        self.country = country
        self.image_path = image_path
        self.age_min = age_min
        self.age_max = age_max
        self.city_only = city_only
        self.name_contains = name_contains
        self.face_embedding = None

    @classmethod
    def from_json(cls, data: Dict) -> 'SearchJob':
        """Create SearchJob from JSON data, supporting both flat and nested formats"""
        try:
            # Handle nested location format
            if 'location' in data:
                location = data['location']
                city = location.get('city')
                country = location.get('country')
            else:
                city = data.get('city')
                country = data.get('country')

            # Validate required fields
            if not all([data.get('name'), data.get('age'), city, country, data.get('image')]):
                missing = [k for k, v in {
                    'name': data.get('name'),
                    'age': data.get('age'),
                    'city': city,
                    'country': country,
                    'image': data.get('image')
                }.items() if not v]
                raise ValueError(f"Missing required fields: {', '.join(missing)}")

            return cls(
                name=data['name'],
                age=data['age'],
                city=city,
                country=country,
                image_path=data['image'],
                age_min=data.get('age_min'),
                age_max=data.get('age_max'),
                city_only=data.get('city_only', False),
                name_contains=data.get('name_contains')
            )
        except Exception as e:
            logger.error(f"❌ Error parsing JSON data: {str(e)}")
            raise

def extract_face_embedding(image_path: str) -> Optional[List[float]]:
    """Extract face embedding from an image file"""
    try:
        # Load image
        if image_path.startswith(('http://', 'https://')):
            logger.info(f"🌐 Downloading image from URL: {image_path}")
            response = requests.get(image_path)
            image = Image.open(BytesIO(response.content))
        else:
            logger.info(f"📂 Loading local image: {image_path}")
            image = Image.open(image_path)
        
        # Log image details
        logger.info(f"📊 Image format: {image.format}, size: {image.size}, mode: {image.mode}")
        
        # Convert to RGB
        if image.mode != 'RGB':
            logger.info(f"🔄 Converting image from {image.mode} to RGB")
            image = image.convert('RGB')
        
        image_array = np.array(image)
        
        # Detect faces
        face_locations = face_recognition.face_locations(image_array)
        if not face_locations:
            logger.warning("⚠️ No face detected in the input image. Possible reasons:")
            logger.warning("  • Image resolution too low")
            logger.warning("  • No clear face in the image")
            logger.warning("  • Face is too small or too large")
            return None
            
        # Extract embedding
        face_encoding = face_recognition.face_encodings(image_array, [face_locations[0]])[0]
        logger.info("✅ Successfully extracted face embedding")
        return face_encoding.tolist()
        
    except Exception as e:
        logger.error(f"❌ Error extracting face embedding: {str(e)}")
        return None

def extract_face_embedding_from_photos(photos: List[str]) -> Optional[List[float]]:
    """Try to extract face embedding from multiple photos"""
    for i, photo_url in enumerate(photos):
        logger.info(f"🖼️ Trying photo {i+1}/{len(photos)}: {photo_url}")
        embedding = extract_face_embedding(photo_url)
        if embedding:
            return embedding
    logger.warning("⚠️ No faces detected in any of the profile photos")
    return None

def find_matching_profiles(search_job: SearchJob) -> List[Dict]:
    """Find profiles matching the search criteria"""
    try:
        db = next(get_db())
        
        # Build base query
        query = db.query(Profile).filter(
            and_(
                Profile.scraped_from_city == search_job.city,
                Profile.scraped_from_country == search_job.country
            )
        )
        
        # Add name filter
        if search_job.name_contains:
            query = query.filter(Profile.name.ilike(f"%{search_job.name_contains}%"))
        else:
            query = query.filter(Profile.name.ilike(f"%{search_job.name}%"))
        
        # Add age range filter
        if search_job.age_min is not None:
            query = query.filter(Profile.age >= search_job.age_min)
        if search_job.age_max is not None:
            query = query.filter(Profile.age <= search_job.age_max)
        
        # Add city-only filter
        if search_job.city_only:
            query = query.filter(Profile.location.ilike(f"%{search_job.city}%"))
        
        profiles = query.all()
        
        if not profiles:
            logger.info(f"❌ No profiles found in {search_job.city}, {search_job.country}")
            return []
            
        logger.info(f"✅ Found {len(profiles)} profiles matching location and name criteria")
            
        # Extract face embedding from search image
        search_embedding = extract_face_embedding(search_job.image_path)
        if not search_embedding:
            logger.warning(f"⚠️ Could not extract face embedding from: {search_job.image_path}")
            return []
            
        # Calculate similarity scores
        matches = []
        for profile in profiles:
            if not profile.face_embedding:
                # Try to extract face embedding from profile photos
                profile.face_embedding = extract_face_embedding_from_photos(profile.photos)
                if not profile.face_embedding:
                    continue
                
            # Calculate face similarity
            face_similarity = face_recognition.face_distance(
                [np.array(profile.face_embedding)],
                np.array(search_embedding)
            )[0]
            
            # Convert distance to similarity score (0-1)
            similarity_score = 1 - face_similarity
            
            # Only include matches with reasonable similarity
            if similarity_score > 0.6:
                matches.append({
                    "profile": profile,
                    "similarity_score": similarity_score
                })
        
        if not matches:
            logger.info("❌ No profiles found with face similarity > 0.6")
            return []
            
        # Sort by similarity score
        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        logger.info(f"✅ Found {len(matches)} profiles with face similarity > 0.6")
        return matches
        
    except Exception as e:
        logger.error(f"❌ Error finding matching profiles: {str(e)}")
        return []
    finally:
        db.close()

def display_match_result(match: Dict) -> None:
    """Display detailed match result"""
    profile = match["profile"]
    similarity = match["similarity_score"]
    
    print("\n" + "="*50)
    print(f"✅ Match found (Similarity: {similarity:.2f})")
    print("="*50)
    
    print(f"\n👤 Name: {profile.name}")
    print(f"🎂 Age: {profile.age}")
    print(f"🌍 Location: {profile.location}")
    print(f"📝 Bio: {profile.bio}")
    print(f"💼 Job: {profile.job_title}")
    print(f"🎓 Education: {profile.education}")
    print(f"📅 Scraped At: {profile.scraped_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔍 Source: {profile.source}")
    
    print(f"\n🖼️ Photos ({len(profile.photos)}):")
    for url in profile.photos[:3]:  # Show first 3 photos
        print(f"  • {url}")
    
    print("\n🎯 Passions:")
    for passion in profile.passions:
        print(f"  • {passion}")
    
    print("="*50)

def save_matches_to_json(matches: List[Dict], output_path: str) -> None:
    """Save matches to JSON file"""
    try:
        results = []
        for match in matches[:3]:  # Save top 3 matches
            profile = match["profile"]
            results.append({
                "name": profile.name,
                "age": profile.age,
                "city": profile.scraped_from_city,
                "country": profile.scraped_from_country,
                "job": profile.job_title,
                "education": profile.education,
                "photos": profile.photos,
                "passions": profile.passions,
                "similarity_score": match["similarity_score"],
                "scraped_at": profile.scraped_at.isoformat(),
                "source": profile.source
            })
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"✅ Saved {len(results)} matches to {output_path}")
    except Exception as e:
        logger.error(f"❌ Error saving matches to JSON: {str(e)}")

def interactive_mode() -> SearchJob:
    """Run in interactive CLI mode"""
    print("\n🔍 Interactive Search Mode")
    print("="*50)
    
    name = input("Enter name: ").strip()
    age = int(input("Enter age: ").strip())
    city = input("Enter city: ").strip()
    country = input("Enter country: ").strip()
    image_path = input("Enter image path or URL: ").strip()
    
    print("\nOptional filters (press Enter to skip):")
    age_min = input("Minimum age: ").strip()
    age_max = input("Maximum age: ").strip()
    city_only = input("Match city only? (y/n): ").strip().lower() == 'y'
    name_contains = input("Name contains (partial match): ").strip()
    
    return SearchJob(
        name=name,
        age=age,
        city=city,
        country=country,
        image_path=image_path,
        age_min=int(age_min) if age_min else None,
        age_max=int(age_max) if age_max else None,
        city_only=city_only,
        name_contains=name_contains if name_contains else None
    )

def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(
            description="Search for matching profiles using face recognition",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Interactive mode
  python search_job.py -i
  
  # CLI mode with filters
  python search_job.py --name Shweta --age 25 --city Wayanad --country India --image shweta.webp --age-min 20 --age-max 30 --city-only
  
  # JSON mode with output
  python search_job.py --output results.json
            """
        )
        parser.add_argument("--name", help="Name to search for")
        parser.add_argument("--age", type=int, help="Age to search for")
        parser.add_argument("--city", help="City to search in")
        parser.add_argument("--country", help="Country to search in")
        parser.add_argument("--image", help="Path to image file")
        parser.add_argument("--age-min", type=int, help="Minimum age filter")
        parser.add_argument("--age-max", type=int, help="Maximum age filter")
        parser.add_argument("--city-only", action="store_true", help="Match city only")
        parser.add_argument("--name-contains", help="Partial name match")
        parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
        parser.add_argument("--output", "--save", help="Save results to JSON file")
        
        args = parser.parse_args()
        
        # If interactive mode is requested, use it regardless of other arguments
        if args.interactive:
            logger.info("💬 Starting interactive mode")
            search_job = interactive_mode()
        # Otherwise, check for CLI arguments
        elif any(vars(args).values()):
            logger.info("📝 Using CLI arguments")
            search_job = SearchJob(
                name=args.name,
                age=args.age,
                city=args.city,
                country=args.country,
                image_path=args.image,
                age_min=args.age_min,
                age_max=args.age_max,
                city_only=args.city_only,
                name_contains=args.name_contains
            )
        # If no arguments, check for JSON file
        elif os.path.exists("search_job.json"):
            logger.info("📄 Found search_job.json, using JSON mode")
            with open("search_job.json", 'r') as f:
                search_job = SearchJob.from_json(json.load(f))
        # If nothing else, start interactive mode
        else:
            logger.info("💬 No arguments provided, starting interactive mode")
            search_job = interactive_mode()
        
        # Find and display matches
        matches = find_matching_profiles(search_job)
        if matches:
            for match in matches[:3]:  # Show top 3 matches
                display_match_result(match)
            
            # Save results if requested
            if args.output:
                save_matches_to_json(matches, args.output)
        else:
            print("\n❌ No matches found")
            
    except Exception as e:
        logger.error(f"❌ Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    main() 