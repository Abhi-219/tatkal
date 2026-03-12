"""
CAPTCHA Solver for IRCTC using ddddocr + PIL preprocessing.
Auto-solves login and booking CAPTCHAs with retry logic.
"""

import io
import re
import base64
import logging
import time
from PIL import Image, ImageFilter, ImageEnhance

logger = logging.getLogger("TatkalBot")


class CaptchaSolver:
    def __init__(self, max_retries=10):
        self.max_retries = max_retries
        self._ocr = None

    @property
    def ocr(self):
        """Lazy-load ddddocr to save startup time."""
        if self._ocr is None:
            import ddddocr
            self._ocr = ddddocr.DdddOcr(show_ad=False)
            logger.info("CAPTCHA OCR engine loaded.")
        return self._ocr

    # ------------------------------------------------------------------ #
    #  Image preprocessing pipeline
    # ------------------------------------------------------------------ #
    @staticmethod
    def _preprocess(img_bytes: bytes) -> bytes:
        """
        Clean noise from IRCTC CAPTCHA for better OCR accuracy.
        Pipeline: grayscale -> contrast -> sharpen -> threshold -> denoise
        """
        img = Image.open(io.BytesIO(img_bytes)).convert("L")  # grayscale

        # Boost contrast
        img = ImageEnhance.Contrast(img).enhance(2.0)

        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)

        # Binary threshold
        threshold = 140
        img = img.point(lambda p: 255 if p > threshold else 0)

        # Remove small noise
        img = img.filter(ImageFilter.MedianFilter(size=3))

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # ------------------------------------------------------------------ #
    #  Core solver
    # ------------------------------------------------------------------ #
    def solve(self, img_bytes: bytes) -> str:
        """
        Solve a CAPTCHA image.
        Returns cleaned alphanumeric text (uppercase).
        """
        processed = self._preprocess(img_bytes)
        raw = self.ocr.classification(processed)

        # Also try on original image
        raw_orig = self.ocr.classification(img_bytes)

        # Pick the one that looks more alphanumeric
        cleaned = re.sub(r'[^A-Za-z0-9]', '', raw).upper()
        cleaned_orig = re.sub(r'[^A-Za-z0-9]', '', raw_orig).upper()

        # IRCTC CAPTCHAs are typically 5-6 characters
        if 4 <= len(cleaned) <= 7:
            result = cleaned
        elif 4 <= len(cleaned_orig) <= 7:
            result = cleaned_orig
        else:
            result = cleaned if len(cleaned) >= len(cleaned_orig) else cleaned_orig

        logger.info(f"CAPTCHA OCR result: '{result}' (raw: '{raw}' / '{raw_orig}')")
        return result

    # ------------------------------------------------------------------ #
    #  Selenium integration: extract + solve from page
    # ------------------------------------------------------------------ #
    def solve_from_element(self, driver, captcha_img_element):
        """
        Extract CAPTCHA image bytes from a Selenium WebElement and solve.
        Handles both <img src="data:..."> and regular image URLs.
        """
        src = captcha_img_element.get_attribute("src")
        if src and src.startswith("data:image"):
            # Base64 encoded image
            img_data = src.split(",", 1)[1]
            img_bytes = base64.b64decode(img_data)
        else:
            # Screenshot the element directly
            img_bytes = captcha_img_element.screenshot_as_png

        return self.solve(img_bytes)

    def solve_with_retry(self, driver, captcha_img_locator, captcha_input_locator,
                         refresh_locator=None, submit_callback=None):
        """
        Repeatedly attempt to solve CAPTCHA with retries.

        Args:
            driver: Selenium WebDriver
            captcha_img_locator: tuple (By, value) for CAPTCHA image
            captcha_input_locator: tuple (By, value) for CAPTCHA text input
            refresh_locator: tuple (By, value) for refresh/reload CAPTCHA button
            submit_callback: callable to invoke after filling CAPTCHA

        Returns:
            True if CAPTCHA was solved and accepted, False otherwise
        """
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"CAPTCHA attempt {attempt}/{self.max_retries}")

                # Wait for CAPTCHA image
                captcha_img = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(captcha_img_locator)
                )
                time.sleep(0.5)  # Let image fully render

                # Solve
                answer = self.solve_from_element(driver, captcha_img)
                if len(answer) < 4:
                    logger.warning(f"CAPTCHA answer too short: '{answer}', refreshing...")
                    if refresh_locator:
                        try:
                            driver.find_element(*refresh_locator).click()
                            time.sleep(1)
                        except Exception:
                            pass
                    continue

                # Fill CAPTCHA input
                captcha_input = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable(captcha_input_locator)
                )
                captcha_input.clear()
                # Type like a human
                for ch in answer:
                    captcha_input.send_keys(ch)
                    time.sleep(0.05)

                logger.info(f"Filled CAPTCHA: {answer}")

                if submit_callback:
                    submit_callback()

                return True

            except Exception as e:
                logger.error(f"CAPTCHA attempt {attempt} failed: {e}")
                if refresh_locator:
                    try:
                        driver.find_element(*refresh_locator).click()
                        time.sleep(1)
                    except Exception:
                        pass

        logger.error("All CAPTCHA attempts exhausted!")
        return False

    def manual_fallback(self, driver, captcha_img_element, captcha_input_element):
        """
        Fallback: prompt user to solve CAPTCHA manually via console.
        """
        logger.warning("Auto CAPTCHA failed. Showing CAPTCHA for manual entry...")
        # Save CAPTCHA image temporarily
        try:
            captcha_img_element.screenshot("_captcha_temp.png")
            print("\n" + "=" * 50)
            print("  CAPTCHA saved to _captcha_temp.png")
            print("  Please look at the CAPTCHA image and type below.")
            print("=" * 50)
        except Exception:
            print("\n⚠️  Look at the CAPTCHA in the browser and type it below.")

        answer = input("Enter CAPTCHA text: ").strip()
        captcha_input_element.clear()
        captcha_input_element.send_keys(answer)
        return answer
