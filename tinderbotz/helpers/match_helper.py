from playwright.async_api import Page, TimeoutError
import asyncio
from tinderbotz.helpers.match import Match
from tinderbotz.helpers.constants_helper import Socials
from tinderbotz.helpers.loadingbar import LoadingBar
from tinderbotz.helpers.xpaths import content, modal_manager

class MatchHelper:
    delay = 5000  # milliseconds
    HOME_URL = "https://tinder.com/app/recs"

    def __init__(self, page: Page):
        self.page = page

    async def _scroll_down(self, selector):
        element = await self.page.wait_for_selector(selector)
        last_height = await self.page.evaluate("(element) => element.scrollHeight", element)

        while True:
            await self.page.evaluate("(element) => element.scrollTo(0, element.scrollHeight)", element)
            await asyncio.sleep(0.5)
            
            new_height = await self.page.evaluate("(element) => element.scrollHeight", element)
            if new_height == last_height:
                return True
            last_height = new_height

    async def get_chat_ids(self, new, messaged):
        chatids = []

        try:
            await self.page.wait_for_selector('button[role="tab"]', timeout=self.delay)
        except TimeoutError:
            print("match tab could not be found, trying again")
            await self.page.goto(self.HOME_URL)
            await asyncio.sleep(1)
            return await self.get_chat_ids(new, messaged)

        tabs = await self.page.query_selector_all('button[role="tab"]')

        if new:
            # Make sure we're in the 'new matches' tab
            for tab in tabs:
                text = await tab.text_content()
                if text == 'Matches':
                    try:
                        await tab.click()
                    except:
                        await self.page.goto(self.HOME_URL)
                        return await self.get_chat_ids(new, messaged)

            # start scraping new matches
            try:
                await self.page.wait_for_selector('div[role="tabpanel"]', timeout=self.delay)
                div = await self.page.query_selector('div[role="tabpanel"]')
                list_refs = await div.query_selector_all('div > div > a')
                
                for ref in list_refs:
                    try:
                        href = await ref.get_attribute('href')
                        if "likes-you" in href or "my-likes" in href:
                            continue
                        else:
                            chatids.append(href.split('/')[-1])
                    except:
                        continue

            except Exception:
                pass

        if messaged:
            # Make sure we're in the 'messaged matches' tab
            for tab in tabs:
                text = await tab.text_content()
                if text == 'Messages':
                    try:
                        await tab.click()
                    except:
                        await self.page.goto(self.HOME_URL)
                        return await self.get_chat_ids(new, messaged)

            # Start scraping the chatted matches
            try:
                await self.page.wait_for_selector('.messageList', timeout=self.delay)
                div = await self.page.query_selector('.messageList')
                list_refs = await div.query_selector_all('a')
                
                for ref in list_refs:
                    try:
                        href = await ref.get_attribute('href')
                        chatids.append(href.split('/')[-1])
                    except:
                        continue

            except Exception:
                pass

        return chatids

    async def get_new_matches(self, amount, quickload):
        matches = []
        used_chatids = []
        iteration = 0
        
        while True:
            iteration += 1
            if len(matches) >= amount:
                break

            new_chatids = await self.get_chat_ids(new=True, messaged=False)
            copied = new_chatids.copy()
            for chatid in copied:
                if chatid in used_chatids:
                    new_chatids.remove(chatid)
                else:
                    used_chatids.append(chatid)

            if len(new_chatids) == 0:
                break

            diff = len(matches) + len(new_chatids) - amount
            if diff > 0:
                del new_chatids[-diff:]

            print(f"\nGetting not-interacted-with, NEW MATCHES, part {iteration}")
            loadingbar = LoadingBar(len(new_chatids), "new matches")
            for index, chatid in enumerate(new_chatids):
                matches.append(await self.get_match(chatid, quickload))
                loadingbar.update_loading(index)
            print("\n")

            # scroll down to get more chatids
            tab = await self.page.query_selector('div[role="tabpanel"]')
            await self.page.evaluate('(element) => element.scrollTop = element.scrollHeight', tab)
            await asyncio.sleep(4)

        return matches

    async def get_messaged_matches(self, amount, quickload):
        matches = []
        used_chatids = []
        iteration = 0
        
        while True:
            iteration += 1
            if len(matches) >= amount:
                break

            new_chatids = await self.get_chat_ids(new=False, messaged=True)
            copied = new_chatids.copy()
            for chatid in copied:
                if chatid in used_chatids:
                    new_chatids.remove(chatid)
                else:
                    used_chatids.append(chatid)

            if len(new_chatids) == 0:
                break

            diff = len(matches) + len(new_chatids) - amount
            if diff > 0:
                del new_chatids[-diff:]

            print(f"\nGetting interacted-with, MESSAGED MATCHES, part {iteration}")
            loadingbar = LoadingBar(len(new_chatids), "interacted-with-matches")
            for index, chatid in enumerate(new_chatids):
                matches.append(await self.get_match(chatid, quickload))
                loadingbar.update_loading(index)
            print("\n")

            # scroll down to get more chatids
            tab = await self.page.query_selector('.messageList')
            await self.page.evaluate('(element) => element.scrollTop = element.scrollHeight', tab)
            await asyncio.sleep(4)

        return matches

    async def send_message(self, chatid, message):
        if not await self._is_chat_opened(chatid):
            await self._open_chat(chatid)

        try:
            textbox = await self.page.wait_for_selector('textarea', timeout=self.delay)
            await textbox.fill(message)
            await textbox.press('Enter')
            print(f"Message sent successfully.\nmessage: {message}\n")
            await asyncio.sleep(1.5)
        except Exception as e:
            print("SOMETHING WENT WRONG LOCATING TEXTBOX")
            print(e)

    async def send_gif(self, chatid, gifname):
        if not await self._is_chat_opened(chatid):
            await self._open_chat(chatid)

        try:
            gif_btn = await self.page.wait_for_selector('button[aria-label="GIF"]', timeout=self.delay)
            await gif_btn.click()
            await asyncio.sleep(1.5)

            search_box = await self.page.query_selector('textarea')
            await search_box.fill(gifname)
            await asyncio.sleep(1.5)

            gif = await self.page.wait_for_selector('div[role="button"]', timeout=self.delay)
            await gif.click()
            await asyncio.sleep(1.5)

        except Exception as e:
            print(e)

    async def send_song(self, chatid, songname):
        if not await self._is_chat_opened(chatid):
            await self._open_chat(chatid)

        try:
            song_btn = await self.page.wait_for_selector('button[aria-label="Song"]', timeout=self.delay)
            await song_btn.click()
            await asyncio.sleep(1.5)

            search_box = await self.page.query_selector('textarea')
            await search_box.fill(songname)
            await asyncio.sleep(1.5)

            song = await self.page.wait_for_selector('button[type="button"]', timeout=self.delay)
            await song.click()
            await asyncio.sleep(0.5)

            confirm_btn = await self.page.wait_for_selector('button[type="submit"]', timeout=self.delay)
            await confirm_btn.click()
            await asyncio.sleep(1.5)

        except Exception as e:
            print(e)

    async def send_socials(self, chatid, media):
        did_match = False
        for social in Socials:
            if social == media:
                did_match = True

        if not did_match:
            print("Media must be of type Socials")
            return

        if not await self._is_chat_opened(chatid):
            await self._open_chat(chatid)

        try:
            socials_btn = await self.page.wait_for_selector('button[aria-label="Socials"]', timeout=self.delay)
            await socials_btn.click()
            await asyncio.sleep(1)
            
            social_btn = await self.page.wait_for_selector(f'img[alt="{media.value}"]', timeout=self.delay)
            await social_btn.click()

            try:
                submit_btn = await self.page.wait_for_selector('button[type="submit"]', timeout=self.delay)
                await submit_btn.click()
                print("Successfully sent social card")
                await asyncio.sleep(1.5)
            except Exception as e:
                print("SOMETHING WENT WRONG LOCATING SUBMIT BUTTON")
                print(e)

        except Exception as e:
            print(e)
            await self.page.reload()
            await self.send_socials(chatid, media)

    async def unmatch(self, chatid):
        if not await self._is_chat_opened(chatid):
            await self._open_chat(chatid)

        try:
            unmatch_button = await self.page.wait_for_selector('button:has-text("Unmatch")', timeout=self.delay)
            await unmatch_button.click()
            await asyncio.sleep(1)

            confirm_button = await self.page.wait_for_selector('button:has-text("Unmatch")', timeout=self.delay)
            await confirm_button.click()
            await asyncio.sleep(1)

        except Exception as e:
            print("SOMETHING WENT WRONG FINDING THE UNMATCH BUTTONS")
            print(e)

    async def _open_chat(self, chatid):
        if await self._is_chat_opened(chatid):
            return

        href = f"/app/messages/{chatid}"

        try:
            await self.page.wait_for_selector('button[role="tab"]', timeout=self.delay)
            tabs = await self.page.query_selector_all('button[role="tab"]')
            
            for tab in tabs:
                text = await tab.text_content()
                if text == "Messages":
                    await tab.click()
            await asyncio.sleep(1)
        except Exception as e:
            await self.page.goto(self.HOME_URL)
            print(e)
            return await self._open_chat(chatid)

        try:
            match_button = await self.page.wait_for_selector(f'a[href="{href}"]', timeout=self.delay)
            await match_button.click()
        except Exception as e:
            await self.page.wait_for_selector('button[role="tab"]', timeout=self.delay)
            tabs = await self.page.query_selector_all('button[role="tab"]')
            
            for tab in tabs:
                text = await tab.text_content()
                if text == "Matches":
                    await tab.click()

            await asyncio.sleep(1)

            try:
                matched_button = await self.page.wait_for_selector(f'a[href="{href}"]', timeout=self.delay)
                await matched_button.click()
            except Exception as e:
                print(e)
        await asyncio.sleep(1)

    async def get_match(self, chatid, quickload):
        if not await self._is_chat_opened(chatid):
            await self._open_chat(chatid)

        name = await self.get_name(chatid)
        age = await self.get_age(chatid)
        bio = await self.get_bio(chatid)
        image_urls = await self.get_image_urls(chatid, quickload)

        rowdata = await self.get_row_data(chatid)
        work = rowdata.get('work')
        study = rowdata.get('study')
        home = rowdata.get('home')
        gender = rowdata.get('gender')
        distance = rowdata.get('distance')

        passions = await self.get_passions(chatid)

        return Match(name=name, chatid=chatid, age=age, work=work, study=study, home=home, gender=gender, distance=distance, bio=bio, passions=passions, image_urls=image_urls)

    async def get_name(self, chatid):
        if not await self._is_chat_opened(chatid):
            await self._open_chat(chatid)

        try:
            element = await self.page.wait_for_selector('h1', timeout=self.delay)
            return await element.text_content()
        except Exception as e:
            print(e)

    async def get_age(self, chatid):
        if not await self._is_chat_opened(chatid):
            await self._open_chat(chatid)

        try:
            element = await self.page.wait_for_selector('span', timeout=self.delay)
            text = await element.text_content()
            try:
                return int(text)
            except ValueError:
                return None
        except Exception:
            return None

    async def get_row_data(self, chatid):
        if not await self._is_chat_opened(chatid):
            await self._open_chat(chatid)

        rowdata = {}
        svg_paths = {
            'work': self._WORK_SVG_PATH,
            'study': self._STUDYING_SVG_PATH,
            'home': self._HOME_SVG_PATH,
            'distance': self._LOCATION_SVG_PATH,
            'gender': self._GENDER_SVG_PATH
        }

        for key, path in svg_paths.items():
            try:
                element = await self.page.wait_for_selector(f'svg path[d="{path}"]', timeout=self.delay)
                parent = await element.evaluate_handle('(element) => element.closest("div")')
                text = await parent.text_content()
                rowdata[key] = text.strip()
            except Exception:
                rowdata[key] = None

        return rowdata

    async def get_passions(self, chatid):
        if not await self._is_chat_opened(chatid):
            await self._open_chat(chatid)

        passions = []
        try:
            elements = await self.page.query_selector_all('div[role="button"]')
            for element in elements:
                text = await element.text_content()
                if text:
                    passions.append(text.strip())
        except Exception:
            pass

        return passions

    async def get_bio(self, chatid):
        if not await self._is_chat_opened(chatid):
            await self._open_chat(chatid)

        try:
            element = await self.page.wait_for_selector('div[data-testid="bio"]', timeout=self.delay)
            return await element.text_content()
        except Exception:
            return None

    async def get_image_urls(self, chatid, quickload):
        if not await self._is_chat_opened(chatid):
            await self._open_chat(chatid)

        image_urls = []
        try:
            if quickload:
                elements = await self.page.query_selector_all('img[src*="images-ssl"]')
                for element in elements:
                    src = await element.get_attribute('src')
                    if src:
                        image_urls.append(src)
            else:
                # Click through all photos to ensure they're loaded
                while True:
                    try:
                        next_button = await self.page.wait_for_selector('button[aria-label="Next"]', timeout=self.delay)
                        await next_button.click()
                        await asyncio.sleep(0.5)
                    except Exception:
                        break

                elements = await self.page.query_selector_all('img[src*="images-ssl"]')
                for element in elements:
                    src = await element.get_attribute('src')
                    if src:
                        image_urls.append(src)
        except Exception:
            pass

        return image_urls

    async def _is_chat_opened(self, chatid):
        try:
            await self.page.wait_for_selector(f'a[href="/app/messages/{chatid}"]', timeout=self.delay)
            return True
        except Exception:
            return False
