from playwright.async_api import Page
from tinderbotz.helpers.constants_helper import Sexuality
import time

class PreferencesHelper:
    delay = 5
    HOME_URL = "https://www.tinder.com/app/profile"

    def __init__(self, page: Page):
        self.page = page

    async def set_distance_range(self, km):
        # correct out of bounds values
        if km > 160:
            final_percentage = 100
        elif km < 2:
            final_percentage = 0
        else:
            final_percentage = (km / 160) * 100

        # Try different possible selectors for the distance slider
        selectors = [
            '[aria-label="Maximum distance in kilometres"]',
            '[aria-label="Maximum distance in kilometers"]',
            '[aria-label="Maximum distance in miles"]'
        ]

        slider = None
        for selector in selectors:
            try:
                slider = await self.page.wait_for_selector(selector, timeout=5000)
                if slider:
                    break
            except:
                continue

        if not slider:
            print("Could not find distance slider")
            return

        print("\nSlider of distance will be adjusted...")
        
        # Get current value
        current_style = await slider.get_attribute('style')
        current_percentage = float(current_style.split(' ')[1].split('%')[0])
        
        print("from {}% = {}km".format(current_percentage, current_percentage*1.6))
        print("to {}% = {}km".format(final_percentage, final_percentage*1.6))
        print("with a fault margin of 1%\n")

        # Set the value using mouse movements
        box = await slider.bounding_box()
        if box:
            current_x = box['x'] + (box['width'] * current_percentage / 100)
            target_x = box['x'] + (box['width'] * final_percentage / 100)
            
            await self.page.mouse.move(current_x, box['y'] + box['height']/2)
            await self.page.mouse.down()
            await self.page.mouse.move(target_x, box['y'] + box['height']/2, steps=10)
            await self.page.mouse.up()

        await self.page.wait_for_timeout(5000)  # 5 second delay

    async def set_age_range(self, min_age, max_age):
        # locate elements
        min_slider = await self.page.wait_for_selector('[aria-label="Minimum age"]')
        max_slider = await self.page.wait_for_selector('[aria-label="Maximum age"]')

        if not min_slider or not max_slider:
            print("Could not find age sliders")
            return

        min_age_tinder = int(await min_slider.get_attribute('aria-valuemin'))
        max_age_tinder = int(await max_slider.get_attribute('aria-valuemax'))

        # Correct out of bounds values
        min_age = max(min_age, min_age_tinder)
        max_age = min(max_age, max_age_tinder)

        # Ensure minimum 5-year range
        while max_age - min_age < 5:
            max_age += 1
            min_age -= 1
            min_age = max(min_age, min_age_tinder)
            max_age = min(max_age, max_age_tinder)

        # Calculate percentages
        range_ages_tinder = max_age_tinder - min_age_tinder
        percentage_per_year = 100 / range_ages_tinder

        to_percentage_min = (min_age - min_age_tinder) * percentage_per_year
        to_percentage_max = (max_age - min_age_tinder) * percentage_per_year

        # Set min age
        min_box = await min_slider.bounding_box()
        if min_box:
            await self.page.mouse.move(min_box['x'] + min_box['width'] * to_percentage_min / 100, 
                                     min_box['y'] + min_box['height']/2)
            await self.page.mouse.down()
            await self.page.mouse.up()

        # Set max age
        max_box = await max_slider.bounding_box()
        if max_box:
            await self.page.mouse.move(max_box['x'] + max_box['width'] * to_percentage_max / 100,
                                     max_box['y'] + max_box['height']/2)
            await self.page.mouse.down()
            await self.page.mouse.up()

        await self.page.wait_for_timeout(5000)  # 5 second delay

    async def set_sexuality(self, type):
        if not isinstance(type, Sexuality):
            raise ValueError("Type must be a Sexuality enum value")

        # Click settings button
        await self.page.click('a[href="/app/settings/gender"]')
        
        # Find and click the correct sexuality option
        options = await self.page.query_selector_all('[aria-pressed="false"]')
        for option in options:
            label = await option.query_selector('label')
            if label:
                text = await label.text_content()
                if text == type.value:
                    await option.click()
                    break

        print(f"clicked on {type.value}")
        await self.page.wait_for_timeout(5000)  # 5 second delay

    async def set_global(self, boolean, language=None):
        # Check if global is already activated
        is_activated = await self.page.is_visible('a[href="/app/settings/global/languages"]')

        if boolean != is_activated:
            await self.page.click('input[name="global"]')

        if is_activated and language:
            print("\nUnfortunately, Languages setting feature does not yet exist")
            print("If needed anyways:\nfeel free to open an issue and ask for the feature")
            print("or contribute by making a pull request.\n")
            await self.page.wait_for_timeout(5000)  # 5 second delay
