"""
IRCTC Tatkal Booking Engine
============================
Selenium-based automation with:
  - Stealth browser (undetected-chromedriver)
  - Auto CAPTCHA solving (ddddocr)
  - NTP-synced countdown to tatkal window
  - Human-like interactions to avoid blocking
  - UPI payment auto-selection
"""

import json
import time
import random
import logging
import sys
import os

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, StaleElementReferenceException
)

from captcha_solver import CaptchaSolver
from utils import PreciseClock, human_delay, human_type

logger = logging.getLogger("TatkalBot")

IRCTC_URL = "https://www.irctc.co.in/nget/train-search"


# ================================================================== #
#  Browser factory
# ================================================================== #
def create_browser(headless=False):
    """
    Create a stealth Chrome browser.
    Priority: undetected-chromedriver (best anti-bot) → plain Selenium fallback.
    Requires Google Chrome installed on your PC.
    """
    # Clean proxy env vars that can interfere with ChromeDriver
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "localhost,127.0.0.1"
    os.environ["no_proxy"] = "localhost,127.0.0.1"

    # ── Method 1: undetected-chromedriver (BEST for IRCTC) ──────────
    try:
        import undetected_chromedriver as uc
        logger.info("Launching stealth Chrome (undetected-chromedriver)...")

        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-infobars")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1366,768")
        options.add_argument("--lang=en-US,en")
        if headless:
            options.add_argument("--headless=new")

        driver = uc.Chrome(options=options, use_subprocess=True)
        driver.maximize_window()

        # Extra stealth injections
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                window.chrome = { runtime: {} };
                const origQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (params) =>
                    params.name === 'notifications'
                        ? Promise.resolve({ state: Notification.permission })
                        : origQuery(params);
            """
        })

        logger.info("✅ Stealth browser ready (undetected-chromedriver).")
        return driver

    except Exception as e:
        logger.warning(f"undetected-chromedriver failed: {e}")
        logger.info("Falling back to standard Selenium...")

    # ── Method 2: Standard Selenium (fallback) ──────────────────────
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    logger.info("Launching Chrome (standard Selenium)...")
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-infobars")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--lang=en-US,en")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    if headless:
        options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=options)
    driver.maximize_window()

    # Stealth: hide webdriver fingerprint
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
            const origQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (params) =>
                params.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : origQuery(params);
        """
    })
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {
        "userAgent": driver.execute_script("return navigator.userAgent").replace("Headless", "")
    })

    logger.info("✅ Stealth browser ready (standard Selenium).")
    return driver


# ================================================================== #
#  Main Booking Class
# ================================================================== #
class TatkalBooker:

    def __init__(self, config_path="config.json"):
        with open(config_path, "r") as f:
            raw = f.read()
        # Strip comment-like keys
        self.cfg = json.loads(raw)

        self.driver = None
        self.wait = None
        self.captcha = CaptchaSolver(max_retries=self.cfg.get("captcha_max_retries", 10))
        self.clock = PreciseClock(self.cfg.get("ntp_server", "time.google.com"))

    # ------------------------------------------------------------ #
    #  Safe click / type helpers
    # ------------------------------------------------------------ #
    def safe_click(self, locator, timeout=10, scroll=True):
        """Click element with retry on intercept."""
        for _ in range(3):
            try:
                el = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable(locator)
                )
                if scroll:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", el)
                    human_delay(100, 200)
                el.click()
                return el
            except ElementClickInterceptedException:
                human_delay(300, 500)
                # Try JS click as fallback
                try:
                    el = self.driver.find_element(*locator)
                    self.driver.execute_script("arguments[0].click();", el)
                    return el
                except Exception:
                    continue
            except StaleElementReferenceException:
                human_delay(200, 400)
                continue
        raise TimeoutException(f"Could not click {locator}")

    def safe_send(self, locator, text, timeout=10):
        """Clear and type into an element."""
        el = WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable(locator)
        )
        el.clear()
        human_delay(50, 100)
        human_type(el, text)
        return el

    def dismiss_overlays(self):
        """Close any popups / alerts that IRCTC throws."""
        # Cookie consent / alerts
        overlay_selectors = [
            "button.btn.btn-primary",           # generic OK
            "//button[text()='OK']",            # OK alert
            "//button[contains(text(),'AGREE')]",
            "//button[contains(text(),'Got it')]",
        ]
        for sel in overlay_selectors:
            try:
                if sel.startswith("//"):
                    el = self.driver.find_element(By.XPATH, sel)
                else:
                    el = self.driver.find_element(By.CSS_SELECTOR, sel)
                el.click()
                human_delay(200, 400)
            except Exception:
                pass

    # ------------------------------------------------------------ #
    #  STEP 1: Open IRCTC & Login
    # ------------------------------------------------------------ #
    def login(self):
        logger.info("Opening IRCTC...")
        self.driver = create_browser(headless=self.cfg.get("headless", False))
        self.wait = WebDriverWait(self.driver, 15)
        self.driver.get(IRCTC_URL)
        time.sleep(3)

        self.dismiss_overlays()

        # Click LOGIN button in top nav
        logger.info("Clicking LOGIN...")
        try:
            login_btn = self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(text(),'LOGIN')]"))
            )
            login_btn.click()
        except Exception:
            # Try alternate selector
            try:
                self.safe_click((By.CSS_SELECTOR, "a.loginText"))
            except Exception:
                self.safe_click((By.XPATH, "//a[@class='search_btn' and contains(text(),'LOGIN')]"))

        time.sleep(2)

        # Fill username
        logger.info("Entering credentials...")
        self.safe_send(
            (By.CSS_SELECTOR, "input[formcontrolname='userid']"),
            self.cfg["irctc_username"]
        )
        human_delay(200, 400)

        # Fill password
        self.safe_send(
            (By.CSS_SELECTOR, "input[formcontrolname='password']"),
            self.cfg["irctc_password"]
        )
        human_delay(200, 400)

        # Click SIGN IN (no CAPTCHA needed)
        logger.info("Clicking SIGN IN...")
        try:
            self.safe_click(
                (By.XPATH, "//button[contains(text(),'SIGN IN')]"), timeout=5
            )
        except Exception:
            try:
                self.safe_click(
                    (By.CSS_SELECTOR, "button[type='submit']"), timeout=5
                )
            except Exception:
                logger.warning("Could not find SIGN IN button. Please click manually.")
                input("Press ENTER after you've logged in manually...")

        time.sleep(3)

        # Check for login success
        try:
            self.wait.until(lambda d: "logged" in d.page_source.lower() or
                            d.find_elements(By.CSS_SELECTOR, "a.dropdown-toggle .user-icon, span.user-name"))
            logger.info("✅ Login successful!")
        except TimeoutException:
            # Check if there's an error alert
            try:
                err = self.driver.find_element(By.CSS_SELECTOR, ".loginError, .alert-danger")
                logger.error(f"Login failed: {err.text}")
                input("Please check the browser and press ENTER to continue...")
            except Exception:
                logger.info("Login status uncertain, proceeding...")

        self.dismiss_overlays()
        time.sleep(1)

    # ------------------------------------------------------------ #
    #  STEP 2: Search for train
    # ------------------------------------------------------------ #
    def search_train(self):
        logger.info(f"Searching: {self.cfg['from_station']} → {self.cfg['to_station']} on {self.cfg['journey_date']}")

        # Navigate to search page
        self.driver.get(IRCTC_URL)
        time.sleep(2)
        self.dismiss_overlays()

        # --- FROM station ---
        from_input = self.wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "input[aria-label='Please Enter Journey Starting Station'], p-autocomplete#origin input"))
        )
        from_input.click()
        human_delay(100, 200)
        from_input.clear()
        # Type station code (last part after " - ")
        from_text = self.cfg["from_station"]
        human_type(from_input, from_text.split(" - ")[-1] if " - " in from_text else from_text)
        time.sleep(1)

        # Select first dropdown match
        try:
            self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "ul.ui-autocomplete-list-item li, .ui-autocomplete-panel li")
            ))
            first_option = self.driver.find_element(
                By.CSS_SELECTOR, "ul.ui-autocomplete-list-item li:first-child, .ui-autocomplete-panel li:first-child"
            )
            first_option.click()
        except Exception:
            from_input.send_keys(Keys.RETURN)
        human_delay(300, 500)

        # --- TO station ---
        to_input = self.wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "input[aria-label='Please Enter Journey Destination Station'], p-autocomplete#destination input"))
        )
        to_input.click()
        human_delay(100, 200)
        to_input.clear()
        to_text = self.cfg["to_station"]
        human_type(to_input, to_text.split(" - ")[-1] if " - " in to_text else to_text)
        time.sleep(1)

        try:
            self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "ul.ui-autocomplete-list-item li, .ui-autocomplete-panel li")
            ))
            first_option = self.driver.find_element(
                By.CSS_SELECTOR, "ul.ui-autocomplete-list-item li:first-child, .ui-autocomplete-panel li:first-child"
            )
            first_option.click()
        except Exception:
            to_input.send_keys(Keys.RETURN)
        human_delay(300, 500)

        # --- Journey Date ---
        date_input = self.driver.find_element(
            By.CSS_SELECTOR, "p-calendar input, input[placeholder*='Date']"
        )
        date_input.click()
        human_delay(100, 200)
        date_input.clear()
        # Use JS to set date value reliably
        self.driver.execute_script(
            "arguments[0].value = arguments[1];", date_input, self.cfg["journey_date"]
        )
        date_input.send_keys(Keys.ESCAPE)
        human_delay(200, 300)

        # --- Quota ---
        booking_type = self.cfg.get("booking_type", "TATKAL").upper()
        try:
            quota_dropdown = self.driver.find_element(
                By.CSS_SELECTOR, "p-dropdown[formcontrolname='journeyQuota'], p-dropdown[id='journeyQuota']"
            )
            quota_dropdown.click()
            time.sleep(0.5)
            if booking_type == "TATKAL":
                quota_text = "TATKAL"
                logger.info("Selecting TATKAL quota...")
            else:
                quota_text = "GENERAL"
                logger.info("Selecting GENERAL quota...")
            quota_opt = self.driver.find_element(
                By.XPATH, f"//li[contains(@class,'ui-dropdown-item')]//span[contains(translate(text(),'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'{quota_text}')]"
            )
            quota_opt.click()
        except Exception as e:
            logger.warning(f"Quota selection issue: {e}. Will try after search.")
        human_delay(200, 400)

        # --- Class selection ---
        try:
            class_dropdown = self.driver.find_element(
                By.CSS_SELECTOR, "p-dropdown[formcontrolname='journeyClass'], p-dropdown[id='journeyClass']"
            )
            class_dropdown.click()
            time.sleep(0.5)
            class_map = {
                "SL": "Sleeper", "3A": "Third AC", "2A": "Second AC",
                "1A": "First AC", "3E": "Third AC Economy", "CC": "Chair Car",
                "2S": "Second Sitting", "EV": "Exec. Chair Car"
            }
            class_text = class_map.get(self.cfg["travel_class"], self.cfg["travel_class"])
            class_opt = self.driver.find_element(
                By.XPATH, f"//li[contains(@class,'ui-dropdown-item')]//span[contains(text(),'{class_text}')]"
            )
            class_opt.click()
        except Exception as e:
            logger.warning(f"Class selection issue: {e}")
        human_delay(200, 400)

        # --- Search button ---
        logger.info("Clicking Search...")
        self.safe_click(
            (By.XPATH, "//button[contains(text(),'Search') or contains(text(),'Find Trains') or @type='submit']")
        )
        time.sleep(3)
        self.dismiss_overlays()
        logger.info("Search results loaded.")

    # ------------------------------------------------------------ #
    #  STEP 3: Select train & class
    # ------------------------------------------------------------ #
    def _wait_for_spinner_gone(self, timeout=10):
        """Wait for any PrimeNG / IRCTC loading spinners to disappear."""
        spinner_selectors = [
            "div.spinner", "p-progressSpinner", ".ui-progress-spinner",
            "div.loading", ".loader-overlay", "div.overlay",
        ]
        for sel in spinner_selectors:
            try:
                WebDriverWait(self.driver, 2).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                WebDriverWait(self.driver, timeout).until_not(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
            except TimeoutException:
                pass
            except Exception:
                pass

    def _find_train_row(self, train_no):
        """Locate the train card/row element containing the given train number."""
        # IRCTC nget wraps each train in div.bull-back inside app-train-avl-enq
        row_selectors = [
            "app-train-avl-enq div.bull-back",
            "div.bull-back",
            "app-train-avl-enq .form-group",
            "div.train-list",
        ]
        for sel in row_selectors:
            rows = self.driver.find_elements(By.CSS_SELECTOR, sel)
            for row in rows:
                try:
                    if train_no in row.text:
                        return row
                except StaleElementReferenceException:
                    continue
        return None

    def _click_class_tab(self, train_row, travel_class):
        """Click the class availability tab (SL, 3A, 2A …) inside a train row."""
        # Strategy 1: find <td class="pre-avl"> or <td> with <strong> matching
        #             the class code inside that train row
        class_tab_selectors = [
            "td.pre-avl",             # standard class cells
            "td.pre-avl strong",      # <strong> inside class cell
            "div.pre-avl",            # alternate layout
            "a.cls-name",             # link variant
            "span.class-name",        # span variant
            "strong",                 # any strong (filter by text below)
        ]
        for sel in class_tab_selectors:
            tabs = train_row.find_elements(By.CSS_SELECTOR, sel)
            for tab in tabs:
                try:
                    tab_text = tab.text.strip().upper()
                    if travel_class.upper() in tab_text:
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", tab)
                        human_delay(150, 250)
                        tab.click()
                        logger.info(f"Clicked class tab: {travel_class}")
                        return True
                except (StaleElementReferenceException, ElementClickInterceptedException):
                    continue

        # Strategy 2: XPath scoped inside the train row
        try:
            tab = train_row.find_element(
                By.XPATH,
                f".//td[contains(@class,'pre-avl')]//strong[contains(translate(text(),"
                f"'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'{travel_class.upper()}')]"
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", tab)
            human_delay(150, 250)
            # Click the parent <td> – more reliable than clicking the <strong>
            parent_td = tab.find_element(By.XPATH, "./ancestor::td[1]")
            parent_td.click()
            logger.info(f"Clicked class tab (XPath): {travel_class}")
            return True
        except Exception:
            pass

        # Strategy 3: JavaScript click on any element containing the class text
        try:
            tab = train_row.find_element(
                By.XPATH,
                f".//*[contains(translate(text(),'abcdefghijklmnopqrstuvwxyz',"
                f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'{travel_class.upper()}')]"
            )
            self.driver.execute_script("arguments[0].click();", tab)
            logger.info(f"Clicked class tab (JS): {travel_class}")
            return True
        except Exception:
            pass

        return False

    def _wait_for_availability_data(self, timeout=15):
        """Wait for the availability table/section to load after clicking a class."""
        avail_selectors = [
            # Table rows with availability data
            "table.table tbody tr td",
            # Availability status text
            "div.pre-avl td.pre-avl",
            # The entire availability container
            "div.table-container",
            # Any Book Now element appearing
            "button.btnDefault.train_Search",
            "td.book_link a",
            "td.book_link button",
        ]
        for sel in avail_selectors:
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                logger.info("Availability data loaded.")
                return True
            except TimeoutException:
                continue

        # Fallback: wait for any "Book Now" text to appear
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(translate(text(),'abcdefghijklmnopqrstuvwxyz',"
                               "'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'BOOK NOW')]"))
            )
            logger.info("Availability data loaded (found Book Now text).")
            return True
        except TimeoutException:
            logger.warning("Availability data may not have loaded yet.")
            return False

    def _click_book_now(self):
        """
        Click the 'Book Now' button in the expanded availability section.
        Handles: <button>, <a>, and various class names IRCTC has used.
        Targets the correct journey date row when multiple dates are shown.
        """
        journey_date = self.cfg.get("journey_date", "")
        self._wait_for_spinner_gone()

        # ── Strategy 1: Find Book Now in the row matching the journey date ──
        if journey_date:
            # Convert DD/MM/YYYY → possible display formats IRCTC uses
            parts = journey_date.split("/")
            if len(parts) == 3:
                # IRCTC may display as "Wed, 25 Mar" or "25-03-2026" etc.
                date_fragments = [
                    parts[0],                              # "25"
                    f"{parts[0]}-{parts[1]}",              # "25-03"
                    f"{parts[0]}/{parts[1]}",              # "25/03"
                ]
            else:
                date_fragments = [journey_date]

            # Look for table rows containing the date, then find Book Now in same row
            try:
                avail_rows = self.driver.find_elements(
                    By.CSS_SELECTOR, "table.table tbody tr, div.table-container tr"
                )
                for row in avail_rows:
                    row_text = row.text
                    date_match = any(frag in row_text for frag in date_fragments)
                    if date_match:
                        # Find Book Now inside this date row
                        book_els = row.find_elements(
                            By.XPATH,
                            ".//button[contains(translate(text(),'abcdefghijklmnopqrstuvwxyz',"
                            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'BOOK NOW')] | "
                            ".//a[contains(translate(text(),'abcdefghijklmnopqrstuvwxyz',"
                            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'BOOK NOW')] | "
                            ".//button[contains(@class,'btnDefault')] | "
                            ".//a[contains(@class,'book_link')]"
                        )
                        for el in book_els:
                            if el.is_displayed() and el.is_enabled():
                                self.driver.execute_script(
                                    "arguments[0].scrollIntoView({block:'center'});", el)
                                human_delay(200, 300)
                                try:
                                    el.click()
                                    logger.info(f"Clicked Book Now for date row: {row_text[:40]}")
                                    return True
                                except ElementClickInterceptedException:
                                    self.driver.execute_script("arguments[0].click();", el)
                                    logger.info(f"Clicked Book Now (JS) for date: {row_text[:40]}")
                                    return True
            except Exception as e:
                logger.debug(f"Date-targeted Book Now search failed: {e}")

        # ── Strategy 2: Click first visible/enabled Book Now (any format) ──
        book_now_xpaths = [
            # <button> with text "Book Now"
            "//button[contains(translate(text(),'abcdefghijklmnopqrstuvwxyz',"
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'BOOK NOW')]",
            # <a> with text "Book Now"
            "//a[contains(translate(text(),'abcdefghijklmnopqrstuvwxyz',"
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'BOOK NOW')]",
            # <button> with class btnDefault (IRCTC's standard)
            "//button[contains(@class,'btnDefault') and contains(@class,'train_Search')]",
            # <td> with book_link class containing <a>
            "//td[contains(@class,'book_link')]//a",
            # Any input type submit with Book Now value
            "//input[@type='submit' and contains(translate(@value,'abcdefghijklmnopqrstuvwxyz',"
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'BOOK NOW')]",
            # Link with book-btn class
            "//a[contains(@class,'book-btn')]",
        ]
        for xpath in book_now_xpaths:
            try:
                elements = self.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    if el.is_displayed():
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", el)
                        human_delay(200, 300)
                        try:
                            el.click()
                        except ElementClickInterceptedException:
                            self.driver.execute_script("arguments[0].click();", el)
                        logger.info(f"Clicked Book Now (strategy 2, xpath: {xpath[:50]}...)")
                        return True
            except Exception:
                continue

        # ── Strategy 3: CSS selector broad search ──
        book_css_selectors = [
            "button.btnDefault.train_Search",
            "button.btnDefault",
            "a.book_link",
            "td.book_link a",
            "td.book_link button",
            ".btn.book-btn",
        ]
        for sel in book_css_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", el)
                        human_delay(200, 300)
                        try:
                            el.click()
                        except ElementClickInterceptedException:
                            self.driver.execute_script("arguments[0].click();", el)
                        logger.info(f"Clicked Book Now (strategy 3, css: {sel})")
                        return True
            except Exception:
                continue

        return False

    def select_train(self):
        train_no = self.cfg["train_number"]
        travel_class = self.cfg["travel_class"]
        logger.info(f"Looking for train {train_no}, class {travel_class}...")

        self._wait_for_spinner_gone()
        time.sleep(2)
        self.dismiss_overlays()

        # ── Phase 1: Find the train row ──
        train_row = None
        for attempt in range(5):
            train_row = self._find_train_row(train_no)
            if train_row:
                logger.info(f"Found train {train_no} (attempt {attempt+1})")
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", train_row)
                human_delay(300, 500)
                break
            logger.info(f"Train {train_no} not found yet (attempt {attempt+1}/5)...")
            time.sleep(2)

        if not train_row:
            logger.error(f"Could not find train {train_no} in search results.")
            logger.info("Please select the train manually in the browser.")
            input("Press ENTER after selecting train and class, "
                  "then click 'Check Availability'...")

        # ── Phase 2: Click the class tab (SL, 3A, etc.) ──
        class_clicked = False
        if train_row:
            for attempt in range(3):
                class_clicked = self._click_class_tab(train_row, travel_class)
                if class_clicked:
                    break
                logger.warning(f"Class tab click attempt {attempt+1} failed, retrying...")
                time.sleep(1)
                # Re-find the train row (DOM may have re-rendered)
                train_row = self._find_train_row(train_no)
                if not train_row:
                    break

        if not class_clicked:
            logger.warning(f"Could not auto-click class {travel_class}.")
            logger.info("Please click the class tab manually in the browser.")
            input("Press ENTER after clicking the class tab...")

        # ── Phase 3: Wait for availability data to load ──
        logger.info("Waiting for availability data to load...")
        self._wait_for_availability_data(timeout=15)
        self._wait_for_spinner_gone()
        human_delay(500, 1000)

        # ── Phase 4: Click "Book Now" ──
        logger.info("Clicking Book Now...")
        book_clicked = False
        for attempt in range(3):
            self.dismiss_overlays()
            book_clicked = self._click_book_now()
            if book_clicked:
                break
            logger.warning(f"Book Now click attempt {attempt+1} failed, retrying...")
            time.sleep(2)

        if not book_clicked:
            logger.warning("Could not auto-click Book Now. Please click manually.")
            input("Press ENTER after clicking Book Now...")

        # ── Phase 5: Wait for page to transition to passenger form ──
        logger.info("Waiting for passenger form to load...")
        self._wait_for_spinner_gone(timeout=15)
        passenger_loaded = False
        passenger_page_selectors = [
            "input[formcontrolname='passengerName']",
            "app-passenger",
            "div.passenger-form",
            "input[formcontrolname='passengerAge']",
            ".passenger-info",
        ]
        for sel in passenger_page_selectors:
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                passenger_loaded = True
                logger.info("✅ Passenger form loaded.")
                break
            except TimeoutException:
                continue

        if not passenger_loaded:
            # Check if we're still on the same page (Book Now didn't work)
            logger.warning("Passenger form not detected. The page may not have transitioned.")
            logger.info("If still on train list, please click Book Now manually.")
            input("Press ENTER when you see the passenger form...")

        time.sleep(2)
        self.dismiss_overlays()

    # ------------------------------------------------------------ #
    #  STEP 4: Fill passenger details
    # ------------------------------------------------------------ #
    def fill_passengers(self):
        logger.info("Filling passenger details...")
        time.sleep(2)
        self.dismiss_overlays()

        passengers = self.cfg["passengers"]

        for idx, pax in enumerate(passengers):
            logger.info(f"Filling passenger {idx+1}: {pax['name']}")

            # Add passenger button (for 2nd passenger onwards)
            if idx > 0:
                try:
                    self.safe_click(
                        (By.XPATH, "//span[contains(text(),'Add Passenger')] | //a[contains(text(),'+ Add Passenger')]"),
                        timeout=5
                    )
                    human_delay(300, 500)
                except Exception:
                    pass

            # Name
            try:
                name_inputs = self.driver.find_elements(
                    By.CSS_SELECTOR, "input[formcontrolname='passengerName']"
                )
                if len(name_inputs) > idx:
                    name_input = name_inputs[idx]
                    name_input.clear()
                    human_type(name_input, pax["name"])
                    human_delay(100, 200)
            except Exception as e:
                logger.warning(f"Name input issue: {e}")

            # Age
            try:
                age_inputs = self.driver.find_elements(
                    By.CSS_SELECTOR, "input[formcontrolname='passengerAge']"
                )
                if len(age_inputs) > idx:
                    age_input = age_inputs[idx]
                    age_input.clear()
                    human_type(age_input, str(pax["age"]))
                    human_delay(100, 200)
            except Exception as e:
                logger.warning(f"Age input issue: {e}")

            # Gender
            try:
                gender_dropdowns = self.driver.find_elements(
                    By.CSS_SELECTOR, "select[formcontrolname='passengerGender'], p-dropdown[formcontrolname='passengerGender']"
                )
                if len(gender_dropdowns) > idx:
                    gdd = gender_dropdowns[idx]
                    gdd.click()
                    time.sleep(0.3)
                    gender_map = {"Male": "M", "Female": "F", "Transgender": "T"}
                    g_val = gender_map.get(pax["gender"], pax["gender"])
                    try:
                        opt = self.driver.find_element(
                            By.XPATH, f"//li//span[contains(text(),'{pax['gender']}')]"
                        )
                        opt.click()
                    except Exception:
                        try:
                            Select(gdd).select_by_visible_text(pax["gender"])
                        except Exception:
                            Select(gdd).select_by_value(g_val)
                    human_delay(100, 200)
            except Exception as e:
                logger.warning(f"Gender selection issue: {e}")

            # Berth Preference
            try:
                berth_dropdowns = self.driver.find_elements(
                    By.CSS_SELECTOR, "select[formcontrolname='passengerBerthChoice'], p-dropdown[formcontrolname='passengerBerthChoice']"
                )
                if len(berth_dropdowns) > idx:
                    bdd = berth_dropdowns[idx]
                    bdd.click()
                    time.sleep(0.3)
                    try:
                        opt = self.driver.find_element(
                            By.XPATH, f"//li//span[contains(text(),'{pax['berth_preference']}')]"
                        )
                        opt.click()
                    except Exception:
                        try:
                            Select(bdd).select_by_visible_text(pax["berth_preference"])
                        except Exception:
                            pass
                    human_delay(100, 200)
            except Exception as e:
                logger.warning(f"Berth preference issue: {e}")

            # Food Choice (if applicable)
            if pax.get("food_choice"):
                try:
                    food_dropdowns = self.driver.find_elements(
                        By.CSS_SELECTOR, "select[formcontrolname='passengerFoodChoice'], p-dropdown[formcontrolname='passengerFoodChoice']"
                    )
                    if len(food_dropdowns) > idx:
                        fdd = food_dropdowns[idx]
                        fdd.click()
                        time.sleep(0.3)
                        try:
                            opt = self.driver.find_element(
                                By.XPATH, f"//li//span[contains(text(),'{pax['food_choice']}')]"
                            )
                            opt.click()
                        except Exception:
                            pass
                except Exception:
                    pass

        # Mobile number
        try:
            mobile_input = self.driver.find_element(
                By.CSS_SELECTOR, "input[formcontrolname='mobileNumber'], input[formcontrolname='mobile']"
            )
            mobile_input.clear()
            human_type(mobile_input, self.cfg["mobile_number"])
        except Exception:
            pass

        # Auto-upgrade checkbox
        if self.cfg.get("auto_upgrade", True):
            try:
                auto_up = self.driver.find_element(
                    By.CSS_SELECTOR, "p-checkbox[formcontrolname='autoUpgradation'] .ui-chkbox-box, input#autoUpgradation"
                )
                if not auto_up.is_selected():
                    auto_up.click()
            except Exception:
                pass

        # Travel Insurance - No
        if not self.cfg.get("travel_insurance", False):
            try:
                insurance_no = self.driver.find_element(
                    By.XPATH, "//p-radiobutton[@value='0']//div[contains(@class,'radio')] | //input[@name='travelInsurance' and @value='0']"
                )
                insurance_no.click()
            except Exception:
                try:
                    self.safe_click(
                        (By.XPATH, "//label[contains(text(),'opt out')]//input | //span[contains(text(),'No')]/ancestor::p-radiobutton"),
                        timeout=3
                    )
                except Exception:
                    pass

        human_delay(300, 500)

        # Click Continue / Submit
        logger.info("Submitting passenger details...")
        try:
            self.safe_click(
                (By.XPATH, "//button[contains(text(),'Continue') or contains(text(),'CONTINUE')]"),
                timeout=10
            )
        except Exception:
            try:
                self.safe_click(
                    (By.CSS_SELECTOR, "button.train_Search.btn"),
                    timeout=5
                )
            except Exception:
                logger.warning("Cannot find Continue button. Click manually.")
                input("Press ENTER after clicking Continue...")

        time.sleep(3)
        self.dismiss_overlays()

    # ------------------------------------------------------------ #
    #  STEP 5: Payment via UPI
    # ------------------------------------------------------------ #
    def make_payment(self):
        logger.info("Proceeding to payment...")
        time.sleep(2)
        self.dismiss_overlays()

        # Select payment method - UPI
        try:
            # Look for payment gateway options
            logger.info("Selecting UPI payment...")

            # IRCTC usually shows payment gateway options
            # Try to find and click "Pay through BHIM/UPI"
            upi_selectors = [
                "//div[contains(text(),'UPI')]",
                "//label[contains(text(),'UPI')]",
                "//span[contains(text(),'UPI')]",
                "//a[contains(text(),'UPI')]",
                "//div[contains(text(),'BHIM')]",
                "//img[contains(@alt,'UPI')]/..",
            ]
            upi_found = False
            for sel in upi_selectors:
                try:
                    el = self.driver.find_element(By.XPATH, sel)
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", el)
                    human_delay(200, 300)
                    el.click()
                    upi_found = True
                    logger.info("UPI payment option selected.")
                    break
                except Exception:
                    continue

            if not upi_found:
                logger.warning("Could not auto-select UPI. Please select manually.")

            time.sleep(2)

            # Fill UPI ID
            upi_id = self.cfg["upi_id"]
            upi_input_selectors = [
                "input[placeholder*='UPI']",
                "input[placeholder*='upi']",
                "input[formcontrolname*='upi']",
                "input[formcontrolname*='vpa']",
                "input[name*='upi']",
                "input[name*='vpa']",
                "input[id*='upi']",
            ]
            upi_filled = False
            for sel in upi_input_selectors:
                try:
                    upi_input = self.driver.find_element(By.CSS_SELECTOR, sel)
                    upi_input.clear()
                    human_type(upi_input, upi_id)
                    upi_filled = True
                    logger.info(f"UPI ID entered: {upi_id}")
                    break
                except Exception:
                    continue

            if not upi_filled:
                logger.warning(f"Could not auto-fill UPI ID. Please enter: {upi_id}")

            human_delay(300, 500)

            # Click Pay / Submit
            pay_selectors = [
                "//button[contains(text(),'Pay')]",
                "//button[contains(text(),'PAY')]",
                "//button[contains(text(),'Submit')]",
                "//button[contains(text(),'Make Payment')]",
                "//input[@value='Pay']",
            ]
            for sel in pay_selectors:
                try:
                    pay_btn = self.driver.find_element(By.XPATH, sel)
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", pay_btn)
                    human_delay(200, 300)
                    pay_btn.click()
                    logger.info("Payment initiated! Check your UPI app for approval.")
                    break
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Payment error: {e}")
            logger.info("Please complete the payment manually in the browser.")

        # Wait for user to approve UPI payment
        print("\n" + "=" * 60)
        print("  💰 PAYMENT INITIATED!")
        print(f"  UPI ID: {self.cfg['upi_id']}")
        print("  📱 Please APPROVE the payment in your UPI app NOW!")
        print("=" * 60 + "\n")

    # ------------------------------------------------------------ #
    #  STEP 6: Booking CAPTCHA (if any)
    # ------------------------------------------------------------ #
    def solve_booking_captcha(self):
        """Some flows show a CAPTCHA before final booking."""
        logger.info("Checking for booking CAPTCHA...")
        time.sleep(1)

        try:
            captcha_img = self.driver.find_element(
                By.CSS_SELECTOR, "app-captcha img.captcha-img, img.captcha-img"
            )
            logger.info("Booking CAPTCHA found! Solving...")
            self.captcha.solve_with_retry(
                driver=self.driver,
                captcha_img_locator=(By.CSS_SELECTOR, "app-captcha img.captcha-img, img.captcha-img"),
                captcha_input_locator=(By.CSS_SELECTOR, "input[formcontrolname='captcha'], input[name='captcha']"),
                refresh_locator=(By.CSS_SELECTOR, "app-captcha .captcha-canvas span.fa-repeat, app-captcha a"),
            )
        except NoSuchElementException:
            logger.info("No booking CAPTCHA found.")

    # ------------------------------------------------------------ #
    #  MAIN FLOW
    # ------------------------------------------------------------ #
    def run(self):
        """Execute the full booking flow (tatkal or general)."""
        try:
            booking_type = self.cfg.get("booking_type", "TATKAL").upper()
            is_tatkal = booking_type == "TATKAL"

            if is_tatkal:
                logger.info("📋 Mode: TATKAL booking (with countdown)")
                tatkal_hour, tatkal_min = 10, 0  # 10:00 AM IST

                login_before = self.cfg.get("login_before_minutes", 10)

                # Step 0: Wait for pre-login time
                pre_login_hour = tatkal_hour
                pre_login_min = tatkal_min - login_before
                if pre_login_min < 0:
                    pre_login_hour -= 1
                    pre_login_min += 60

                now = self.clock.now()
                target_login = now.replace(hour=pre_login_hour, minute=pre_login_min, second=0)

                if now < target_login:
                    logger.info(f"Will login at {pre_login_hour}:{pre_login_min:02d} IST ({login_before} min before tatkal window)")
                    self.clock.wait_until(pre_login_hour, pre_login_min)
                else:
                    logger.info("Already past pre-login time. Logging in now.")

                # Step 1: Login
                self.login()

                # Step 2: Search train (pre-fill form)
                self.search_train()

                # Step 3: Wait for EXACT tatkal time
                now = self.clock.now()
                target_tatkal = now.replace(hour=tatkal_hour, minute=tatkal_min, second=0)
                if now < target_tatkal:
                    logger.info(f"⏰ Waiting for tatkal window: {tatkal_hour}:{tatkal_min:02d}:00 IST")
                    self.clock.wait_until(tatkal_hour, tatkal_min, 0)

                    # Rapid refresh at exact time
                    logger.info("🚀 TATKAL WINDOW OPEN! Refreshing...")
                    self.search_train()

            else:
                logger.info("📋 Mode: GENERAL booking (no countdown)")

                # Step 1: Login immediately
                self.login()

                # Step 2: Search train
                self.search_train()

            # Step 4: Select train
            self.select_train()

            # Step 5: Solve booking CAPTCHA if present
            self.solve_booking_captcha()

            # Step 6: Fill passengers
            self.fill_passengers()

            # Step 7: Payment
            self.make_payment()

            logger.info("🎉 Booking flow complete! Approve payment in UPI app.")

            # Keep browser open
            input("\nPress ENTER to close browser...")

        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            print(f"\n❌ Error: {e}")
            print("The browser is still open. You can complete the booking manually.")
            input("Press ENTER to close browser...")
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
