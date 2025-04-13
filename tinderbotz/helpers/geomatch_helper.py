from playwright.async_api import Page
import time
import re
from datetime import datetime

class GeomatchHelper:
    delay = 5
    HOME_URL = "https://www.tinder.com/app/recs"

    def __init__(self, page: Page):
        self.page = page

    async def _get_home_page(self):
        await self.page.goto(self.HOME_URL)
        await self.page.wait_for_load_state('networkidle')

    async def like(self) -> bool:
        try:
            await self.page.keyboard.press('ArrowRight')
            return True
        except Exception:
            await self._get_home_page()
            return False

    async def dislike(self):
        try:
            await self.page.keyboard.press('ArrowLeft')
        except Exception:
            await self._get_home_page()

    async def superlike(self):
        try:
            if 'profile' in self.page.url:
                await self.page.click('button[aria-label="Super Like"]')
            else:
                await self.page.keyboard.press('ArrowUp')
            await self.page.wait_for_timeout(1000)  # 1 second delay
        except Exception:
            await self._get_home_page()

    async def _is_profile_opened(self):
        try:
            profile_info = await self.page.wait_for_selector('div[data-testid="profile-info"]', timeout=1000)
            return profile_info is not None
        except:
            return False

    async def _open_profile(self, second_try=False):
        if await self._is_profile_opened():
            return

        try:
            await self.page.keyboard.press('ArrowUp')
        except Exception:
            if not second_try:
                print("Trying again to locate the profile info button in a few seconds")
                await self.page.wait_for_timeout(2000)
                await self._open_profile(second_try=True)
            else:
                await self.page.reload()

    async def get_name(self):
        if not await self._is_profile_opened():
            await self._open_profile()

        try:
            name_element = await self.page.wait_for_selector('h1[data-testid="name"]')
            if name_element:
                return await name_element.text_content()
        except Exception:
            pass
        return None

    async def get_age(self):
        if not await self._is_profile_opened():
            await self._open_profile()

        try:
            age_element = await self.page.wait_for_selector('span[data-testid="age"]')
            if age_element:
                age_text = await age_element.text_content()
                return int(age_text)
        except Exception:
            pass
        return None

    async def is_verified(self):
        if not await self._is_profile_opened():
            await self._open_profile()

        try:
            verified_badge = await self.page.wait_for_selector('div[data-testid="verifiedBadge"]', timeout=1000)
            return verified_badge is not None
        except:
            return False

    _WORK_SVG_PATH = "M7.15 3.434h5.7V1.452a.728.728 0 0 0-.724-.732H7.874a.737.737 0 0 0-.725.732v1.982z"
    _STUDYING_SVG_PATH = "M11.87 5.026L2.186 9.242c-.25.116-.25.589 0 .705l.474.204v2.622a.78.78 0 0 0-.344.657c0 .42.313.767.69.767.378 0 .692-.348.692-.767a.78.78 0 0 0-.345-.657v-2.322l2.097.921a.42.42 0 0 0-.022.144v3.83c0 .45.27.801.626 1.101.358.302.842.572 1.428.804 1.172.46 2.755.776 4.516.776 1.763 0 3.346-.317 4.518-.777.586-.23 1.07-.501 1.428-.803.355-.3.626-.65.626-1.1v-3.83a.456.456 0 0 0-.022-.145l3.264-1.425c.25-.116.25-.59 0-.705L12.13 5.025c-.082-.046-.22-.017-.26 0v.001zm.13.767l8.743 3.804L12 13.392 3.257 9.599l8.742-3.806zm-5.88 5.865l5.75 2.502a.319.319 0 0 0 .26 0l5.75-2.502v3.687c0 .077-.087.262-.358.491-.372.29-.788.52-1.232.68-1.078.426-2.604.743-4.29.743s-3.212-.317-4.29-.742c-.444-.161-.86-.39-1.232-.68-.273-.23-.358-.415-.358-.492v-3.687z"
    _HOME_SVG_PATH = "M19.695 9.518H4.427V21.15h15.268V9.52zM3.109 9.482h17.933L12.06 3.709 3.11 9.482z"
    _LOCATION_SVG_PATH = "M11.436 21.17l-.185-.165a35.36 35.36 0 0 1-3.615-3.801C5.222 14.244 4 11.658 4 9.524 4 5.305 7.267 2 11.436 2c4.168 0 7.437 3.305 7.437 7.524 0 4.903-6.953 11.214-7.237 11.48l-.2.167zm0-18.683c-3.869 0-6.9 3.091-6.9 7.037 0 4.401 5.771 9.927 6.897 10.972 1.12-1.054 6.902-6.694 6.902-10.95.001-3.968-3.03-7.059-6.9-7.059h.001z"
    _LOCATION_SVG_PATH_2 = "M11.445 12.5a2.945 2.945 0 0 1-2.721-1.855 3.04 3.04 0 0 1 .641-3.269 2.905 2.905 0 0 1 3.213-.645 3.003 3.003 0 0 1 1.813 2.776c-.006 1.653-1.322 2.991-2.946 2.993zm0-5.544c-1.378 0-2.496 1.139-2.498 2.542 0 1.404 1.115 2.544 2.495 2.546a2.52 2.52 0 0 0 2.502-2.535 2.527 2.527 0 0 0-2.499-2.545v-.008z"
    _GENDER_SVG_PATH = "M15.507 13.032c1.14-.952 1.862-2.656 1.862-5.592C17.37 4.436 14.9 2 11.855 2 8.81 2 6.34 4.436 6.34 7.44c0 3.07.786 4.8 2.02 5.726-2.586 1.768-5.054 4.62-4.18 6.204 1.88 3.406 14.28 3.606 15.726 0 .686-1.71-1.828-4.608-4.4-6.338"

    async def get_row_data(self):
        if not await self._is_profile_opened():
            await self._open_profile()

        data = {}
        try:
            # Get all SVG paths
            svg_elements = await self.page.query_selector_all('path')
            for svg in svg_elements:
                d = await svg.get_attribute('d')
                if d == self._WORK_SVG_PATH:
                    work_element = await svg.evaluate('el => el.closest("div").textContent')
                    data['work'] = work_element.strip() if work_element else None
                elif d == self._STUDYING_SVG_PATH:
                    study_element = await svg.evaluate('el => el.closest("div").textContent')
                    data['study'] = study_element.strip() if study_element else None
                elif d == self._HOME_SVG_PATH:
                    home_element = await svg.evaluate('el => el.closest("div").textContent')
                    data['home'] = home_element.strip() if home_element else None
                elif d in [self._LOCATION_SVG_PATH, self._LOCATION_SVG_PATH_2]:
                    distance_element = await svg.evaluate('el => el.closest("div").textContent')
                    if distance_element:
                        try:
                            data['distance'] = int(re.search(r'\d+', distance_element).group())
                        except:
                            data['distance'] = None
                elif d == self._GENDER_SVG_PATH:
                    gender_element = await svg.evaluate('el => el.closest("div").textContent')
                    data['gender'] = gender_element.strip() if gender_element else None
        except Exception as e:
            print(f"Error getting row data: {str(e)}")

        return data

    async def get_bio_and_passions(self):
        if not await self._is_profile_opened():
            await self._open_profile()

        bio = None
        passions = []
        lifestyle = {}
        basics = {}
        anthem = None
        looking_for = None

        try:
            # Get bio
            bio_element = await self.page.wait_for_selector('div[data-testid="bio"]')
            if bio_element:
                bio = await bio_element.text_content()

            # Get passions
            passion_elements = await self.page.query_selector_all('div[data-testid="passion"]')
            for element in passion_elements:
                passion = await element.text_content()
                if passion:
                    passions.append(passion.strip())

            # Get lifestyle info
            lifestyle_elements = await self.page.query_selector_all('div[data-testid="lifestyle"]')
            for element in lifestyle_elements:
                key_element = await element.query_selector('div[data-testid="lifestyle-key"]')
                value_element = await element.query_selector('div[data-testid="lifestyle-value"]')
                if key_element and value_element:
                    key = await key_element.text_content()
                    value = await value_element.text_content()
                    if key and value:
                        lifestyle[key.strip()] = value.strip()

            # Get basics info
            basics_elements = await self.page.query_selector_all('div[data-testid="basics"]')
            for element in basics_elements:
                key_element = await element.query_selector('div[data-testid="basics-key"]')
                value_element = await element.query_selector('div[data-testid="basics-value"]')
                if key_element and value_element:
                    key = await key_element.text_content()
                    value = await value_element.text_content()
                    if key and value:
                        basics[key.strip()] = value.strip()

            # Get anthem
            anthem_element = await self.page.wait_for_selector('div[data-testid="anthem"]')
            if anthem_element:
                anthem = await anthem_element.text_content()

            # Get looking for
            looking_for_element = await self.page.wait_for_selector('div[data-testid="looking-for"]')
            if looking_for_element:
                looking_for = await looking_for_element.text_content()

        except Exception as e:
            print(f"Error getting bio and passions: {str(e)}")

        return bio, passions, lifestyle, basics, anthem, looking_for

    async def get_image_urls(self, quickload=True):
        if not await self._is_profile_opened():
            await self._open_profile()

        image_urls = []
        try:
            # Wait for images to load
            await self.page.wait_for_selector('div[data-testid="photo"]')
            
            # Get all image elements
            image_elements = await self.page.query_selector_all('div[data-testid="photo"] img')
            
            for img in image_elements:
                src = await img.get_attribute('src')
                if src and src not in image_urls:
                    image_urls.append(src)

            if not quickload:
                # Click through all photos to ensure they're loaded
                next_button = await self.page.query_selector('button[data-testid="next-photo"]')
                while next_button:
                    await next_button.click()
                    await self.page.wait_for_timeout(500)
                    
                    # Get any new images
                    current_img = await self.page.query_selector('div[data-testid="photo"] img')
                    if current_img:
                        src = await current_img.get_attribute('src')
                        if src and src not in image_urls:
                            image_urls.append(src)
                    
                    next_button = await self.page.query_selector('button[data-testid="next-photo"]')

        except Exception as e:
            print(f"Error getting image URLs: {str(e)}")

        return image_urls

    @staticmethod
    def de_emojify(text):
        if not text:
            return text
            
        regrex_pattern = re.compile(pattern="["
                                  u"\U0001F600-\U0001F64F"  # emoticons
                                  u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                                  u"\U0001F680-\U0001F6FF"  # transport & map symbols
                                  u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                                  u"\U00002702-\U000027B0"
                                  u"\U000024C2-\U0001F251"
                                  "]+", flags=re.UNICODE)
        return regrex_pattern.sub(r'', text)

    async def get_insta(self, text):
        """
        Get instagram username from bio text
        :param text: bio text
        :return: username or None
        """
        if not text:
            return None

        # Remove emojis
        text = self.de_emojify(text)

        # First check if there is any reference to instagram
        instagram_strings = ['ig:', 'ig ', 'insta:', 'insta ', 'instagram:', 'instagram ', '@']

        for ig_string in instagram_strings:
            if ig_string in text.lower():
                text_after = text[text.lower().find(ig_string) + len(ig_string):]
                text_after = text_after.split('\n')[0]
                text_after = text_after.split(' ')[0]
                text_after = text_after.strip()
                if text_after:
                    return text_after

        return None

    async def get_geomatch(self):
        try:
            # Wait for a profile to be visible
            await self.page.wait_for_selector('.recsCardboard__cardsContainer', timeout=10000)
            
            # Get profile data
            name = await self.get_name()
            age = await self.get_age()
            bio, passions, lifestyle, basics, anthem, looking_for = await self.get_bio_and_passions()
            row_data = await self.get_row_data()
            image_urls = await self.get_image_urls()
            verified = await self.is_verified()
            
            # Create Geomatch object
            geomatch = Geomatch(
                name=name,
                age=age,
                bio=bio,
                passions=passions,
                lifestyle=lifestyle,
                basics=basics,
                anthem=anthem,
                looking_for=looking_for,
                work=row_data.get('work'),
                study=row_data.get('study'),
                home=row_data.get('home'),
                distance=row_data.get('distance'),
                gender=row_data.get('gender'),
                image_urls=image_urls,
                verified=verified
            )
            
            return geomatch
        except Exception as e:
            print(f"Error getting geomatch: {str(e)}")
            return None
