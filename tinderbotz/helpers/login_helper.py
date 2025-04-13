from playwright.async_api import Page
import time
import asyncio

class LoginHelper:
    def __init__(self, page: Page):
        self.page = page

    async def login_by_google(self, email: str, password: str):
        """
        Login using Google account with a verified email address
        :param email: Your email address
        :param password: Your password
        """
        print("\nAttempting Google login...")
        
        # Try different selectors for the Google login button
        google_button_selectors = [
            'button[aria-label="Log in with Google"]',
            '[data-testid="google"]',
            '[aria-label="Log in with Google"]',
            'button:has-text("Continue with Google")',
            'button:has-text("Log in with Google")'
        ]
        
        popup_page = None
        for selector in google_button_selectors:
            try:
                print(f"Looking for Google button with selector: {selector}")
                # Try to find and click the button
                button = await self.page.wait_for_selector(selector, timeout=5000)
                if button:
                    print("Found Google login button")
                    # Wait for popup
                    async with self.page.expect_popup() as popup_info:
                        await button.click()
                        print("Clicked Google login button")
                        popup_page = await popup_info.value
                        break
            except Exception as e:
                print(f"Failed with selector {selector}: {str(e)}")
                continue

        if not popup_page:
            print("Could not find Google login button or trigger popup")
            raise Exception("Google login button not found")

        try:
            print("Waiting for Google login popup...")
            # Wait for the email input field
            email_input = await popup_page.wait_for_selector('input[type="email"]')
            print("Found email input")
            await email_input.fill(email)
            print("Entered email")
            
            next_button = await popup_page.wait_for_selector('#identifierNext')
            await next_button.click()
            print("Clicked next after email")

            # Wait for password input field
            print("Waiting for password field...")
            password_input = await popup_page.wait_for_selector('input[type="password"]', state='visible')
            await password_input.fill(password)
            print("Entered password")
            
            password_next = await popup_page.wait_for_selector('#passwordNext')
            await password_next.click()
            print("Clicked next after password")

            # Wait for the popup to close
            try:
                print("Waiting for popup to close...")
                await popup_page.wait_for_event('close', timeout=10000)
                print("Google login popup closed")
            except Exception as e:
                print(f"Warning: Popup didn't close as expected: {str(e)}")
                # Take a screenshot for debugging
                await popup_page.screenshot(path='google_login_popup.png')
                print("Saved popup screenshot to google_login_popup.png")
        except Exception as e:
            print(f"Error during Google login: {str(e)}")
            # Take a screenshot for debugging
            await popup_page.screenshot(path='google_login_error.png')
            print("Saved error screenshot to google_login_error.png")
            raise

    async def login_by_facebook(self, email: str, password: str):
        """
        Login using Facebook account with a connected profile
        :param email: Your email address
        :param password: Your password
        """
        # Wait for the Facebook login popup
        popup_page = None
        async with self.page.expect_popup() as popup_info:
            await self.page.click('button[aria-label="Log in with Facebook"]')
            popup_page = await popup_info.value

        if popup_page:
            # Wait for the email input field
            await popup_page.wait_for_selector('#email')
            await popup_page.fill('#email', email)
            await popup_page.fill('#pass', password)
            await popup_page.click('button[name="login"]')

            # Wait for the popup to close
            try:
                await popup_page.wait_for_event('close', timeout=10000)
            except:
                pass

    async def login_by_sms(self, country, phone_number):
        """Login using SMS verification
        :param country: Your country
        :param phone_number: Your phone number
        """
        print("\nAttempting SMS login...")
        
        try:
            # Wait for the main page to load
            await self.page.wait_for_load_state('networkidle')
            
            # Try different selectors for the phone login button
            phone_button_selectors = [
                'button[aria-label="Log in with phone number"]',
                'button:has-text("Log in with phone number")',
                'button:has-text("Continue with phone number")',
                '[data-testid="phone"]',
                'button:has-text("Phone Number")'
            ]
            
            phone_button = None
            for selector in phone_button_selectors:
                try:
                    print(f"Looking for phone button with selector: {selector}")
                    phone_button = await self.page.wait_for_selector(selector, timeout=10000)
                    if phone_button:
                        await phone_button.click()
                        print("Clicked phone login button")
                        break
                except Exception as e:
                    print(f"Failed with selector {selector}: {str(e)}")
                    continue

            if not phone_button:
                print("Could not find phone login button")
                await self.page.screenshot(path='phone_button_not_found.png')
                print("Saved error screenshot to phone_button_not_found.png")
                raise Exception("Phone login button not found")

            # Wait for the phone input form to appear
            await self.page.wait_for_load_state('networkidle')
            
            phone_input_selectors = [
                'input[name="phone_number"]',
                'input[type="tel"]',
                'input[aria-label="Phone number"]'
            ]
            
            phone_input = None
            for selector in phone_input_selectors:
                try:
                    print(f"Looking for phone input with selector: {selector}")
                    phone_input = await self.page.wait_for_selector(selector, timeout=10000)
                    if phone_input:
                        print("Phone input form loaded")
                        break
                except Exception as e:
                    print(f"Error with selector {selector}: {str(e)}")
                    continue

            if not phone_input:
                print("Could not find phone input form")
                await self.page.screenshot(path='phone_input_not_found.png')
                print("Saved error screenshot to phone_input_not_found.png")
                raise Exception("Phone input form not found")

            # Try to select country if the dropdown exists
            country_selectors = [
                'select[aria-label="Select country"]',
                'select[name="country"]',
                'select[data-testid="country-select"]'
            ]
            
            try:
                country_select = None
                for selector in country_selectors:
                    try:
                        print(f"Looking for country selector with: {selector}")
                        country_select = await self.page.wait_for_selector(selector, timeout=5000)
                        if country_select:
                            await country_select.click()
                            await self.page.type(selector, country)
                            await self.page.keyboard.press('Enter')
                            print(f"Selected country: {country}")
                            break
                    except Exception as e:
                        print(f"Error with country selector {selector}: {str(e)}")
                        continue
            except Exception as e:
                print(f"Warning: Could not select country: {str(e)}")
                print("Continuing with default country...")

            # Enter phone number
            print("Entering phone number...")
            await phone_input.fill(phone_number)
            print("Phone number entered")
            
            # Click continue button
            continue_button_selectors = [
                'button[type="submit"]',
                'button:has-text("Continue")',
                'button:has-text("Next")'
            ]
            
            continue_button = None
            for selector in continue_button_selectors:
                try:
                    print(f"Looking for continue button with selector: {selector}")
                    continue_button = await self.page.wait_for_selector(selector, timeout=5000)
                    if continue_button:
                        await continue_button.click()
                        print("Clicked continue button")
                        break
                except Exception as e:
                    print(f"Error with continue button selector {selector}: {str(e)}")
                    continue

            if not continue_button:
                print("Could not find continue button")
                await self.page.screenshot(path='continue_button_not_found.png')
                print("Saved error screenshot to continue_button_not_found.png")
                raise Exception("Continue button not found")

            # Wait for SMS code input
            print("Waiting for SMS code input...")
            code_input_selectors = [
                'input[type="text"]',
                'input[aria-label="Enter code"]',
                'input[name="code"]'
            ]
            
            code_input = None
            for selector in code_input_selectors:
                try:
                    print(f"Looking for code input with selector: {selector}")
                    code_input = await self.page.wait_for_selector(selector, timeout=30000)
                    if code_input:
                        print("SMS code input form loaded")
                        break
                except Exception as e:
                    print(f"Error with code input selector {selector}: {str(e)}")
                    continue

            if not code_input:
                print("Could not find SMS code input form")
                await self.page.screenshot(path='code_input_not_found.png')
                print("Saved error screenshot to code_input_not_found.png")
                raise Exception("SMS code input form not found")

            # Wait for user to enter the code manually
            print("\nPlease enter the SMS verification code in the browser window...")
            print("Waiting for code verification...")
            
            # Wait for the main page to load after code verification
            try:
                await self.page.wait_for_load_state('networkidle', timeout=30000)
                print("Successfully logged in!")
            except Exception as e:
                print(f"Error during code verification: {str(e)}")
                await self.page.screenshot(path='code_verification_error.png')
                print("Saved error screenshot to code_verification_error.png")
                raise

        except Exception as e:
            print(f"Error during SMS login: {str(e)}")
            await self.page.screenshot(path='sms_login_error.png')
            print("Saved error screenshot to sms_login_error.png")
            raise
