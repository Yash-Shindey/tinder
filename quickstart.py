'''
Created by Frederikme (TeetiFM)
'''

import asyncio
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from tinderbotz.session import Session
from tinderbotz.helpers.constants_helper import DEFAULT_LOCATION
import os
from playwright.async_api import TimeoutError, Error as PlaywrightError
import re
import time
import shortuuid  # Add this import at the top

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Create data directory if it doesn't exist
DATA_DIR = Path("data/scraped_profiles")
DATA_DIR.mkdir(parents=True, exist_ok=True)

seen_photos = set()  # Global set to track all seen photo URLs

def sanitize_filename(name: str) -> str:
    """Sanitize a string to be used as a filename"""
    # Replace unsafe characters with underscores
    return re.sub(r'[^\w\-_.]', '_', name)

async def save_page_html(page, filename="tinder_profile.html"):
    """Save the current page HTML for debugging"""
    try:
        html = await page.content()
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"✅ Saved page HTML to {filename}")
    except Exception as e:
        logger.error(f"❌ Failed to save HTML: {str(e)}")

async def log_profile(profile_data):
    """Log profile data to a JSON file with the new naming convention"""
    try:
        # Skip profiles with missing name or age
        if not profile_data.get('name') or not profile_data.get('age'):
            logger.warning("⚠️ Skipping profile with missing name or age")
            return
            
        # Generate sanitized filename
        sanitized_name = sanitize_filename(profile_data['name'])
        short_uuid = shortuuid.uuid()[:8]  # Get first 8 chars of UUID
        filename = f"profile_{sanitized_name}_{profile_data['age']}_{short_uuid}.json"
        filepath = DATA_DIR / filename
        
        # Save the profile data
        with open(filepath, 'w') as f:
            json.dump(profile_data, f, indent=2)
            
        logger.info(f"✅ Logged profile data to {filename}")
        
    except Exception as e:
        logger.error(f"❌ Failed to log profile data: {str(e)}")

async def wait_for_element(page, selector, timeout=10000):
    """Wait for an element to be visible and return it"""
    try:
        logger.info(f"🔍 Waiting for element: {selector}")
        element = await page.wait_for_selector(selector, timeout=timeout)
        if element:
            await element.wait_for_element_state('visible')
            logger.info(f"✅ Found element: {selector}")
        return element
    except Exception as e:
        logger.error(f"❌ Error waiting for element {selector}: {str(e)}")
        return None

async def wait_for_manual_login(page):
    """Wait for user to manually log in"""
    logger.info("\n🔐 Please log in manually in the browser.")
    logger.info("The script will continue once you're logged in...")
    
    # List of selectors that indicate successful login
    logged_in_selectors = [
        'div[role="img"][aria-label^="Profile Photo"]',  # Profile photos
        'h2 span.Ell',  # Profile name
        'div:has-text("About") + div',  # Bio
        'div:has-text("I am a") + div',  # Gender
        'div:has-text("Passions") >> span, li'  # Passions
    ]
    
    while True:
        for selector in logged_in_selectors:
            try:
                logger.info(f"🔍 Checking for login indicator: {selector}")
                element = await wait_for_element(page, selector, timeout=5000)
                if element:
                    logger.info("✅ Login detected! Starting automation...")
                    return True
            except:
                continue
        logger.info("⏳ Waiting for login... (checking every 5 seconds)")
        await asyncio.sleep(5)

def is_own_avatar(url: str) -> bool:
    """Check if a photo URL belongs to the user's own avatar"""
    own_avatar_hashes = [
        '67f81020455f80eccaed0014',  # Add other known hashes if needed
    ]
    return any(hash in url for hash in own_avatar_hashes)

async def extract_photo_url(element) -> str:
    """Extract photo URL from an element's style attribute"""
    try:
        style = await element.get_attribute("style")
        if style:
            match = re.search(r'url\("([^"]+)"\)', style)
            if match:
                return match.group(1)
    except Exception as e:
        logger.error(f"❌ Error extracting photo URL: {str(e)}")
    return None

async def scrape_profile_data(page):
    """Scrape profile data using the new selectors"""
    try:
        logger.info("🔄 Starting profile data scraping...")
        
        # Save HTML for debugging
        await save_page_html(page)
        
        # Check if this is our own profile
        try:
            # Check for edit profile button or settings icon
            edit_button = await page.query_selector('button[aria-label="Edit profile"]')
            settings_icon = await page.query_selector('svg[aria-label="Settings"]')
            if edit_button or settings_icon:
                logger.info("⏭️ Skipping own profile")
                return None
        except Exception as e:
            logger.error(f"❌ Error checking for own profile: {str(e)}")
        
        # Wait for new profile to load
        logger.info("⏳ Waiting for new profile to load...")
        try:
            # Wait for profile name to be visible
            name_element = await page.wait_for_selector('span[itemprop="name"]', timeout=10000)
            if not name_element:
                logger.error("❌ Profile name not found")
                return None
                
            # Get profile name and age
            name = await name_element.text_content()
            age_element = await page.query_selector('span[itemprop="age"]')
            age = await age_element.text_content() if age_element else None
            
            # Skip if name or age is missing
            if not name or not age:
                logger.warning("⚠️ Skipping profile with missing name or age")
                return None
                
            logger.info(f"✅ Found new profile: {name}, {age}")
            
            # Debounce first photo to ensure it's updated
            logger.info("🔁 Verifying first photo has updated...")
            try:
                # Get initial photo URL
                first_photo = await page.query_selector('div[role="img"][aria-label="Profile Photo 1"]')
                if not first_photo:
                    logger.error("❌ First photo element not found")
                    return None
                    
                initial_style = await first_photo.get_attribute('style')
                initial_url = None
                if initial_style:
                    match = re.search(r'url\("([^"]+)"\)', initial_style)
                    if match:
                        initial_url = match.group(1)
                        logger.info(f"📸 Initial photo URL: {initial_url}")
                
                # Wait for potential UI update
                await asyncio.sleep(0.8)
                
                # Check if photo has updated
                updated_style = await first_photo.get_attribute('style')
                updated_url = None
                if updated_style:
                    match = re.search(r'url\("([^"]+)"\)', updated_style)
                    if match:
                        updated_url = match.group(1)
                        logger.info(f"📸 Updated photo URL: {updated_url}")
                
                if initial_url and updated_url and initial_url != updated_url:
                    logger.info("✅ First photo has updated correctly")
                else:
                    logger.warning("⚠️ Profile photo may not have updated correctly — potential mismatch risk")
                    
            except Exception as e:
                logger.error(f"❌ Error during photo debounce: {str(e)}")
                return None
            
        except Exception as e:
            logger.error(f"❌ Error waiting for new profile: {str(e)}")
            return None
        
        # Get profile photos with improved handling
        logger.info("🖼️ Extracting profile photos...")
        photo_urls = []  # Fresh list for this profile
        MAX_PHOTOS = 6  # Maximum number of photos to scrape per profile
        photo_index = 1  # Start with first photo
        
        # Main photo collection loop
        while len(photo_urls) < MAX_PHOTOS:
            try:
                # Check for superlike dialog and close it if present
                superlike_dialog = await page.query_selector('div[role="dialog"]:has-text("No Thanks")')
                if superlike_dialog:
                    no_thanks_button = await superlike_dialog.query_selector('button:has-text("No Thanks")')
                    if no_thanks_button:
                        await no_thanks_button.click()
                        logger.info("✅ Closed superlike dialog")
                        await asyncio.sleep(0.5)
                
                # Wait for current photo to be visible
                selector = f'div[role="img"][aria-label="Profile Photo {photo_index}"]'
                logger.info(f"🔍 Waiting for photo {photo_index}...")
                photo_element = await page.wait_for_selector(selector, timeout=5000)
                
                if not photo_element:
                    logger.error(f"❌ Photo {photo_index} not found")
                    break
                
                # Extract photo URL
                style = await photo_element.get_attribute('style')
                if style:
                    match = re.search(r'url\("([^"]+)"\)', style)
                    if match:
                        url = match.group(1)
                        if url and not is_own_avatar(url) and url not in photo_urls and url not in seen_photos:
                            photo_urls.append(url)
                            seen_photos.add(url)  # Add to global set
                            logger.info(f"📸 Captured photo {photo_index}/6: {url}")
                        else:
                            logger.info(f"⏭️ Skipped duplicate or own avatar photo {photo_index}")
                
                # Check if we've reached the limit
                if len(photo_urls) >= MAX_PHOTOS:
                    logger.info("✅ Reached maximum number of photos")
                    break
                
                # Try to click next button
                next_btn = await page.query_selector('button[aria-label="Next Photo"]:not([disabled])')
                if not next_btn:
                    logger.info("⏹️ No more photos available")
                    break
                
                # Scroll the button into view and force click
                await next_btn.scroll_into_view_if_needed()
                await next_btn.click(force=True)
                logger.info("➡️ Clicked right arrow")
                await asyncio.sleep(0.8)  # Wait for new photo to load
                
                # Move to next photo index
                photo_index += 1
                
            except Exception as e:
                logger.error(f"❌ Error during photo navigation: {str(e)}")
                break
        
        # Get the rest of the profile data
        logger.info("🔍 Extracting profile details...")
        try:
            # Get bio
            bio_element = await page.query_selector('div[itemprop="description"]')
            bio = await bio_element.text_content() if bio_element else None
            
            # Get looking for
            looking_for_element = await page.query_selector('span.Typs\\(display-3-strong\\)')
            looking_for = await looking_for_element.text_content() if looking_for_element else None
            
            # Get distance
            distance_element = await page.query_selector('div:has-text("kilometres away")')
            distance = await distance_element.text_content() if distance_element else None
            
            # Get location
            location_element = await page.query_selector('div[itemprop="homeLocation"]')
            location = await location_element.text_content() if location_element else None
            
            # Get job
            job_element = await page.query_selector('div[itemprop="jobTitle"]')
            job = await job_element.text_content() if job_element else None
            
            # Get education
            education_element = await page.query_selector('div[itemprop="affiliation"]')
            education = await education_element.text_content() if education_element else None
            
            # Get passions
            passions = []
            passion_elements = await page.query_selector_all('div.Gp\\(8px\\) span.Typs\\(body-2-regular\\)')
            for element in passion_elements:
                text = await element.text_content()
                if text.strip():
                    passions.append(text.strip())
            
            # Set gender to female by default since we're only seeing girls
            gender = "female"
            
            # Create profile data
            profile_data = {
                "name": name,
                "age": age,
                "bio": bio,
                "looking_for": looking_for,
                "distance": distance,
                "location": location,
                "job": job,
                "education": education,
                "gender": gender,
                "passions": passions,
                "photos": photo_urls,
                "scraped_at": datetime.now().isoformat(),
                "source": "Tinder"
            }
            
            # Save profile data with new naming convention
            await log_profile(profile_data)
            logger.info(f"✅ Successfully scraped all profile data")
            return profile_data
            
        except Exception as e:
            logger.error(f"❌ Error extracting profile details: {str(e)}")
            return None
        
    except Exception as e:
        logger.error(f"❌ Error during profile scraping: {str(e)}")
        return None

async def perform_swipe(page, action: str):
    """Perform a swipe action with human-like behavior"""
    try:
        # Random delay between 1.5-3.5 seconds
        delay = random.uniform(1.5, 3.5)
        logger.info(f"⏳ Waiting {delay:.2f} seconds before swipe...")
        await asyncio.sleep(delay)

        # Only allow like and dislike actions
        if action not in ["like", "dislike"]:
            logger.warning("⚠️ Invalid swipe action, defaulting to like")
            action = "like"

        if action == "like":
            button = await page.query_selector('button svg[stroke*="--border-sparks-like"]')
            if button:
                await button.evaluate("node => node.closest('button').click()")
                logger.info("👍 Liked profile")
        elif action == "dislike":
            button = await page.query_selector('button svg[stroke*="--border-sparks-nope"]')
            if button:
                await button.evaluate("node => node.closest('button').click()")
                logger.info("👎 Disliked profile")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error during swipe: {str(e)}")
        return False

async def main():
    logger.info("🚀 Starting Tinder scraper...")
    
    # Initialize session with persistent context
    user_data_dir = os.path.expanduser('~/Library/Application Support/Playwright/PersistentContext')
    os.makedirs(user_data_dir, exist_ok=True)
    
    session = None
    try:
        session = await Session.create(
            headless=False,
            store_session=True,
            user_data_dir=user_data_dir
        )
        
        # Set location using the centralized config
        latitude, longitude = DEFAULT_LOCATION.get_coordinates()
        logger.info(f"📍 Setting location to {DEFAULT_LOCATION.city}, {DEFAULT_LOCATION.country} ({latitude}, {longitude})")
        await session.set_custom_location(latitude, longitude)
        
        logger.info("🌐 Navigating to Tinder...")
        await session.page.goto('https://tinder.com/app/recs', wait_until='networkidle')
        
        # Wait for manual login
        await wait_for_manual_login(session.page)
        
        logger.info("\n🎯 Starting profile scraping...")
        
        # Main scraping loop
        while True:
            try:
                logger.info("🔄 Waiting for new profile to load...")
                # Wait for profile to load
                await session.page.wait_for_selector('div[role="img"][aria-label^="Profile Photo"]', timeout=10000)
                
                # Scrape profile data
                profile_data = await scrape_profile_data(session.page)
                if profile_data:
                    logger.info(f"✅ Scraped profile: {profile_data['name']}")
                    
                    # Only choose between like and dislike
                    action = random.choice(["like", "dislike"])
                    
                    # Perform the swipe
                    await perform_swipe(session.page, action)
                    profile_data["swipe_action"] = action
                    
                else:
                    logger.error("❌ Failed to scrape profile data")
                
            except Exception as e:
                logger.error(f"❌ Error getting profile: {str(e)}")
                await session.page.screenshot(path='error.png')
                logger.info("📸 Saved error screenshot to error.png")
                await asyncio.sleep(5)  # Wait before retrying
                continue
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Graceful shutdown triggered by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {str(e)}")
        await session.page.screenshot(path='fatal_error.png')
        logger.info("📸 Saved error screenshot to fatal_error.png")
    
    finally:
        if session:
            logger.info("\n🔌 Closing browser...")
            try:
                await session.browser.close()
            except Exception as e:
                logger.error(f"❌ Error closing browser: {str(e)}")
            try:
                await session.playwright.stop()
            except Exception as e:
                logger.error(f"❌ Error stopping playwright: {str(e)}")
        logger.info("✅ Script finished. All profile data has been logged.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 Script stopped by user.")
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {str(e)}")
