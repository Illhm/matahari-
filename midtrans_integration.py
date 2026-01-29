import os
import time
import logging
import midtransclient
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MidtransTester:
    def __init__(self):
        self.server_key = os.getenv('MIDTRANS_SERVER_KEY')
        self.client_key = os.getenv('MIDTRANS_CLIENT_KEY')

        if not self.server_key or not self.client_key:
            logger.warning("Midtrans Server/Client Key not found in environment variables. Functionality will be limited.")

        self.snap = midtransclient.Snap(
            is_production=False,
            server_key=self.server_key,
            client_key=self.client_key
        )

    def create_transaction_token(self, order_id, amount):
        """
        Creates a Snap transaction token and redirect URL using the official API.
        """
        param = {
            "transaction_details": {
                "order_id": order_id,
                "gross_amount": amount
            },
            "credit_card":{
                "secure" : True
            }
        }

        try:
            logger.info(f"Creating transaction for Order ID: {order_id}, Amount: {amount}")
            transaction = self.snap.create_transaction(param)
            transaction_token = transaction['token']
            redirect_url = transaction['redirect_url']
            logger.info(f"Transaction created. Token: {transaction_token}")
            logger.info(f"Redirect URL: {redirect_url}")
            return redirect_url
        except Exception as e:
            logger.error(f"Failed to create transaction: {e}")
            raise

    def load_cards(self, filepath="card.txt"):
        """
        Reads card details from a file.
        Format expected: CardNumber MM/YYYY CVV
        """
        cards = []
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        card_number = parts[0]
                        expiry = parts[1] # Expected MM/YYYY or similar
                        cvv = parts[2]
                        cards.append({
                            "number": card_number,
                            "expiry": expiry,
                            "cvv": cvv
                        })
            logger.info(f"Loaded {len(cards)} cards from {filepath}")
            return cards
        except FileNotFoundError:
            logger.error(f"Card file {filepath} not found.")
            return []

    def simulate_payment(self, redirect_url, card):
        """
        Simulates the payment process using Playwright in the Sandbox environment.
        """
        # SECURITY CHECK: Ensure we are only running against Sandbox
        if "sandbox" not in redirect_url and "midtrans" in redirect_url:
             logger.error("SECURITY ALERT: Attempted to run automation against a non-Sandbox URL.")
             raise ValueError("This script is restricted to Midtrans Sandbox environment only.")

        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            try:
                logger.info(f"Navigating to {redirect_url}")
                page.goto(redirect_url)

                # Wait for Snap to load
                page.wait_for_load_state("networkidle")

                # Select Credit Card
                logger.info("Selecting Credit Card payment method...")
                try:
                    page.locator("div.list-title", has_text="Credit Card").click(timeout=10000)
                except:
                    logger.info("Could not find 'Credit Card' list item, checking if already on form...")
                    pass

                # Fill Card Details
                logger.info(f"Testing Card: {card['number'][:4]}********{card['number'][-4:]}")

                # Card Number
                page.get_by_placeholder("Card number").fill(card['number'])

                # Expiry
                page.get_by_placeholder("MM / YY").fill(card['expiry'])

                # CVV
                page.get_by_placeholder("123").fill(card['cvv'])

                # Click Pay Now
                logger.info("Submitting payment...")
                page.get_by_text("Pay Now").click()

                # Handle 3DS Simulator
                try:
                    logger.info("Waiting for 3DS Simulator...")
                    time.sleep(5)

                    if "api.sandbox.veritrans.co.id" in page.url or "api.sandbox.midtrans.com" in page.url:
                         # Check for failure message immediately
                         if page.get_by_text("Transaction failed").is_visible():
                             raise Exception("Transaction failed on 3DS page")

                         page.get_by_placeholder("112233").fill("112233")
                         page.get_by_text("OK").click()
                         logger.info("Entered 3DS OTP.")
                    else:
                        for frame in page.frames:
                            if "acs" in frame.url:
                                logger.info("Found ACS frame")
                                frame.get_by_placeholder("112233").fill("112233")
                                frame.get_by_role("button", name="OK").click()
                                break
                except Exception as e:
                    logger.warning(f"3DS step might have been skipped or failed: {e}")

                # Verify Success
                logger.info("Waiting for success message...")
                try:
                    page.wait_for_selector("text=Transaction Successful", timeout=15000)
                    logger.info("PAYMENT SUCCESSFUL!")
                    return True
                except:
                    logger.error("Payment failed or timed out.")
                    return False

            except PlaywrightTimeoutError:
                logger.error("Timeout waiting for element.")
                page.screenshot(path=f"error_screenshot_{card['number'][-4:]}.png")
                return False
            except Exception as e:
                logger.error(f"An error occurred during simulation: {e}")
                return False
            finally:
                browser.close()

    def run_test_suite(self):
        cards = self.load_cards()
        if not cards:
            logger.error("No cards to test. Exiting.")
            return

        # Create a fresh transaction for each card attempt
        # (Midtrans Snap tokens are often single-use or tied to specific attempts)
        for i, card in enumerate(cards):
            logger.info(f"--- Starting Test for Card {i+1}/{len(cards)} ---")
            order_id = f"test-order-{int(time.time())}-{i}"
            try:
                url = self.create_transaction_token(order_id, 10000)
                success = self.simulate_payment(url, card)
                if success:
                    logger.info("Test Suite Completed: SUCCESS found.")
                    break # Stop on first success
                else:
                    logger.info("Card failed. Moving to next card...")
            except Exception as e:
                logger.error(f"Test iteration failed: {e}")

if __name__ == "__main__":
    tester = MidtransTester()
    tester.run_test_suite()
