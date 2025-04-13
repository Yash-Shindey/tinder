# Browser automation
from playwright.async_api import async_playwright, Page, Browser
import asyncio
from typing import Optional

# some other imports :-)
import os
import platform
import time
import random
import requests
import atexit
from pathlib import Path

# Tinderbotz: helper classes
from tinderbotz.helpers.geomatch import Geomatch
from tinderbotz.helpers.match import Match
from tinderbotz.helpers.profile_helper import ProfileHelper
from tinderbotz.helpers.preferences_helper import PreferencesHelper
from tinderbotz.helpers.geomatch_helper import GeomatchHelper
from tinderbotz.helpers.match_helper import MatchHelper
from tinderbotz.helpers.login_helper import LoginHelper
from tinderbotz.helpers.storage_helper import StorageHelper
from tinderbotz.helpers.email_helper import EmailHelper
from tinderbotz.helpers.constants_helper import Printouts
from tinderbotz.helpers.xpaths import *
from tinderbotz.addproxy import get_proxy_extension


class Session:
    HOME_URL = "https://www.tinder.com/app/recs"

    def __init__(self, headless=False, store_session=True, proxy=None, user_data_dir=None, use_existing_browser=False):
        self.email = None
        self.may_send_email = False
        self.session_data = {
            "duration": 0,
            "like": 0,
            "dislike": 0,
            "superlike": 0
        }
        self.headless = headless
        self.store_session = store_session
        self.proxy = proxy
        self.user_data_dir = user_data_dir
        self.use_existing_browser = use_existing_browser
        self.start_session = time.time()
        
        # Register cleanup
        atexit.register(self._cleanup)

    def _cleanup(self):
        # End session duration
        seconds = int(time.time() - self.start_session)
        self.session_data["duration"] = seconds

        # add session data into a list of messages
        lines = []
        for key in self.session_data:
            message = "{}: {}".format(key, self.session_data[key])
            lines.append(message)

        # print out the statistics of the session
        try:
            box = self._get_msg_box(lines=lines, title="Tinderbotz")
            print(box)
        finally:
            if hasattr(self, 'started'):
                print("Started session: {}".format(self.started))
            y = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            print("Ended session: {}".format(y))

    @classmethod
    async def create(cls, headless=False, store_session=True, proxy=None, user_data_dir=None, use_existing_browser=False):
        self = cls(headless, store_session, proxy, user_data_dir, use_existing_browser)
        await self._initialize()
        return self

    async def _initialize(self):
        # Initialize Playwright
        print("Launching browser...")
        self.playwright = await async_playwright().start()
        
        # Configure browser options
        browser_args = []
        if self.proxy:
            if '@' in self.proxy:
                parts = self.proxy.split('@')
                user = parts[0].split(':')[0]
                pwd = parts[0].split(':')[1]
                host = parts[1].split(':')[0]
                port = parts[1].split(':')[1]
                browser_args.append(f'--proxy-server={host}:{port}')
            else:
                browser_args.append(f'--proxy-server={self.proxy}')

        # Create persistent context
        context_options = {
            'viewport': {'width': 1280, 'height': 800},
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        if self.user_data_dir:
            print(f"Using persistent context at: {self.user_data_dir}")
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                args=browser_args,
                **context_options
            )
            self.browser = self.context.browser
        else:
            # Launch browser with stealth mode
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=browser_args
            )
            self.context = await self.browser.new_context(**context_options)
        
        # Enable stealth mode
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # Create a new page
        self.page = await self.context.new_page()

        # Cool banner
        print(Printouts.BANNER.value)
        time.sleep(1)

        self.started = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print("Started session: {}\n\n".format(self.started))

    async def set_custom_location(self, latitude, longitude, accuracy="100%"):
        await self.context.set_geolocation({
            'latitude': latitude,
            'longitude': longitude,
            'accuracy': int(accuracy.split('%')[0])
        })

    def set_email_notifications(self, boolean):
        self.may_send_email = boolean

    async def set_distance_range(self, km):
        helper = PreferencesHelper(page=self.page)
        await helper.set_distance_range(km)

    async def set_age_range(self, min, max):
        helper = PreferencesHelper(page=self.page)
        await helper.set_age_range(min, max)

    async def set_sexuality(self, type):
        helper = PreferencesHelper(page=self.page)
        await helper.set_sexualitiy(type)

    async def set_global(self, boolean):
        helper = PreferencesHelper(page=self.page)
        await helper.set_global(boolean)

    async def set_bio(self, bio):
        helper = ProfileHelper(page=self.page)
        await helper.set_bio(bio)

    async def add_photo(self, filepath):
        helper = ProfileHelper(page=self.page)
        await helper.add_photo(filepath)

    async def login_using_google(self, email, password):
        self.email = email
        if not await self._is_logged_in():
            # Navigate to Tinder website first
            await self.page.goto(self.HOME_URL)
            # Wait for the page to load
            await self.page.wait_for_load_state('networkidle')
            # Handle any potential popups
            await self._handle_potential_popups()
            
            # Initialize login helper and perform login
            helper = LoginHelper(page=self.page)
            await helper.login_by_google(email, password)
            # Wait for login to complete
            await asyncio.sleep(5)
            # Check if we need manual intervention
            if not await self._is_logged_in():
                print('Manual interference is required.')
                input('press ENTER to continue')

    async def login_using_facebook(self, email, password):
        self.email = email
        if not await self._is_logged_in():
            helper = LoginHelper(page=self.page)
            await helper.login_by_facebook(email, password)
            time.sleep(5)
        if not await self._is_logged_in():
            print('Manual interference is required.')
            input('press ENTER to continue')

    async def login_using_sms(self, country, phone_number):
        if not await self._is_logged_in():
            helper = LoginHelper(page=self.page)
            await helper.login_by_sms(country, phone_number)
            time.sleep(5)
        if not await self._is_logged_in():
            print('Manual interference is required.')
            input('press ENTER to continue')

    async def _is_logged_in(self):
        try:
            # Wait for either the login button or the main app content
            login_button = await self.page.wait_for_selector('button[aria-label="Log in with Google"]', timeout=1000)
            if login_button:
                print("User is not logged in yet.")
                return False
        except:
            # If we can't find the login button, check if we're on the main app page
            try:
                await self.page.wait_for_selector('[data-testid="recsPage"]', timeout=1000)
                print("User is logged in.")
                return True
            except:
                print("Could not determine login status.")
                return False

    def _get_msg_box(self, lines, indent=1, width=None, title=None):
        """Print message-box with optional title."""
        space = " " * indent
        if not width:
            width = max(map(len, lines))
        box = f'/{"=" * (width + indent * 2)}\\\n'  # upper_border
        if title:
            box += f'|{space}{title:<{width}}{space}|\n'  # title
            box += f'|{space}{"-" * len(title):<{width}}{space}|\n'  # underscore
        box += ''.join([f'|{space}{line:<{width}}{space}|\n' for line in lines])
        box += f'\\{"=" * (width + indent * 2)}/'  # lower_border
        return box

    def store_local(self, match):
        if isinstance(match, Match):
            filename = 'matches'
        elif isinstance(match, Geomatch):
            filename = 'geomatches'
        else:
            print("type of match is unknown, storing local impossible")
            print("Crashing in 3.2.1... :)")
            assert False

        # store its images
        for url in match.image_urls:
            hashed_image = StorageHelper.store_image_as(url=url, directory='data/{}/images'.format(filename))
            match.images_by_hashes.append(hashed_image)

        # store its userdata
        StorageHelper.store_match(match=match, directory='data/{}'.format(filename), filename=filename)

    async def like(self, amount=1, ratio='100%', sleep=1, randomize_sleep = True):
        initial_sleep = sleep
        ratio = float(ratio.split('%')[0]) / 100

        if await self._is_logged_in():
            helper = GeomatchHelper(page=self.page)
            amount_liked = 0
            # handle one time up front, from then on check after every action instead of before
            await self._handle_potential_popups()
            print("\nLiking profiles started.")
            while amount_liked < amount:
                # randomize sleep
                if randomize_sleep:
                    sleep = random.uniform(0.5, 2.3) * initial_sleep
                if random.random() <= ratio:
                    if await helper.like():
                        amount_liked += 1
                        # update for stats after session ended
                        self.session_data['like'] += 1
                        print(f"{amount_liked}/{amount} liked, sleep: {sleep}")
                else:
                    await helper.dislike()
                    # update for stats after session ended
                    self.session_data['dislike'] += 1

                #await self._handle_potential_popups()
                time.sleep(sleep)

            await self._print_liked_stats()

    async def dislike(self, amount=1):
        if await self._is_logged_in():
            helper = GeomatchHelper(page=self.page)
            await self._handle_potential_popups()
            print("\nDisliking profiles started.")
            for _ in range(amount):
                await helper.dislike()

                # update for stats after session ended
                self.session_data['dislike'] += 1
                #time.sleep(1)
            await self._print_liked_stats()

    async def superlike(self, amount=1):
        if await self._is_logged_in():
            helper = GeomatchHelper(page=self.page)
            await self._handle_potential_popups()
            print("\nSuperliking profiles started.")
            for _ in range(amount):
                await helper.superlike()
                # update for stats after session ended
                self.session_data['superlike'] += 1
                time.sleep(1)
            await self._print_liked_stats()

    async def get_geomatch(self, quickload=True):
        if await self._is_logged_in():
            helper = GeomatchHelper(page=self.page)
            await self._handle_potential_popups()
            return await helper.get_geomatch(quickload=quickload)

    async def get_chat_ids(self, new=True, messaged=True):
        helper = MatchHelper(page=self.page)
        return await helper.get_chat_ids(new=new, messaged=messaged)

    async def get_new_matches(self, amount=100000, quickload=True):
        helper = MatchHelper(page=self.page)
        return await helper.get_new_matches(amount=amount, quickload=quickload)

    async def get_messaged_matches(self, amount=100000, quickload=True):
        helper = MatchHelper(page=self.page)
        return await helper.get_messaged_matches(amount=amount, quickload=quickload)

    async def send_message(self, chatid, message):
        helper = MatchHelper(page=self.page)
        await helper.send_message(chatid=chatid, message=message)

    async def send_gif(self, chatid, gifname):
        helper = MatchHelper(page=self.page)
        await helper.send_gif(chatid=chatid, gifname=gifname)

    async def send_song(self, chatid, songname):
        helper = MatchHelper(page=self.page)
        await helper.send_song(chatid=chatid, songname=songname)

    async def send_socials(self, chatid, media):
        helper = MatchHelper(page=self.page)
        await helper.send_socials(chatid=chatid, media=media)

    async def unmatch(self, chatid):
        helper = MatchHelper(page=self.page)
        await helper.unmatch(chatid=chatid)

    # Utilities
    async def _handle_potential_popups(self):
        """
        Handle potential popups that might appear
        """
        # Wait a bit for any popups
        await asyncio.sleep(2)

        try:
            # Handle location popup
            location_modal = await self.page.wait_for_selector('[data-testid="allow"]', timeout=1000)
            if location_modal:
                await location_modal.click()
                await asyncio.sleep(1)
        except:
            pass

        try:
            # Handle notifications popup
            notifications_modal = await self.page.wait_for_selector('[data-testid="deny"]', timeout=1000)
            if notifications_modal:
                await notifications_modal.click()
                await asyncio.sleep(1)
        except:
            pass

        try:
            # Handle cookies popup
            cookies_modal = await self.page.wait_for_selector('[data-testid="cookie-policy-dialog-accept"]', timeout=1000)
            if cookies_modal:
                await cookies_modal.click()
                await asyncio.sleep(1)
        except:
            pass

    async def _print_liked_stats(self):
        likes = self.session_data['like']
        dislikes = self.session_data['dislike']
        superlikes = self.session_data['superlike']

        if superlikes > 0:
            print(f"You've superliked {self.session_data['superlike']} profiles during this session.")
        if likes > 0:
            print(f"You've liked {self.session_data['like']} profiles during this session.")
        if dislikes > 0:
            print(f"You've disliked {self.session_data['dislike']} profiles during this session.")

