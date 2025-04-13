from playwright.async_api import Page
import time
import os

class ProfileHelper:
    delay = 5
    HOME_URL = "https://www.tinder.com/app/profile"

    def __init__(self, page: Page):
        self.page = page

    async def _edit_info(self):
        try:
            await self.page.click('a[href="/app/profile/edit"]')
            await self.page.wait_for_timeout(1000)  # 1 second delay
        except Exception as e:
            print(e)

    async def _save(self):
        try:
            await self.page.click('div[data-testid="save-profile"]')
            await self.page.wait_for_timeout(1000)  # 1 second delay
        except Exception as e:
            print(e)

    async def add_photo(self, filepath):
        # get the absolute filepath instead of the relative one
        filepath = os.path.abspath(filepath)

        try:
            # Click "add media" button
            await self.page.click('button[aria-label="Add media"]')
            
            # Handle file input
            file_input = await self.page.wait_for_selector('input[type="file"]')
            await file_input.set_input_files(filepath)
            
            # Click choose/done button
            await self.page.click('button[type="submit"]')
            
            await self._save()
        except Exception as e:
            print(e)

    async def set_bio(self, bio):
        try:
            # Find and clear the textarea
            text_area = await self.page.wait_for_selector('textarea[data-testid="profile-bio"]')
            await text_area.fill('')  # Clear existing text
            await self.page.wait_for_timeout(1000)  # 1 second delay
            
            # Set new bio
            await text_area.fill(bio)
            await self.page.wait_for_timeout(1000)  # 1 second delay
            
            await self._save()
        except Exception as e:
            print(e)
