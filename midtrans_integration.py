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

    def simulate_payment(self, redirect_url):
        """
        Simulates the payment process using Playwright in the Sandbox environment.
        """
        # SECURITY CHECK: Ensure we are only running against Sandbox
        if "sandbox" not in redirect_url and "midtrans" in redirect_url:
             logger.error("SECURITY ALERT: Attempted to run automation against a non-Sandbox URL.")
             raise ValueError("This script is restricted to Midtrans Sandbox environment only.")

        with sync_playwright() as p:
            # Launch browser (headless=True for automation, set to False to see it running)
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            try:
                logger.info(f"Navigating to {redirect_url}")
                page.goto(redirect_url)

                # Wait for Snap to load
                page.wait_for_load_state("networkidle")

                # Select Credit Card (This might vary depending on Snap configuration)
                # Using generous timeout as Snap loads iframe/resources
                logger.info("Selecting Credit Card payment method...")
                # Try finding by text or icon
                try:
                    page.locator("div.list-title", has_text="Credit Card").click(timeout=10000)
                except:
                    # Fallback or maybe it's already on the card page if specific params were used
                    logger.info("Could not find 'Credit Card' list item, checking if already on form...")
                    pass

                # Fill Card Details (Sandbox Data)
                logger.info("Filling card details...")

                # Card Number
                page.get_by_placeholder("Card number").fill("4485000000000000") # Common Sandbox Card

                # Expiry
                page.get_by_placeholder("MM / YY").fill("12/30")

                # CVV
                page.get_by_placeholder("123").fill("123")

                # Click Pay Now
                logger.info("Submitting payment...")
                page.get_by_text("Pay Now").click()

                # Handle 3DS Simulator if it appears
                try:
                    # Wait for iframe or 3DS modal
                    logger.info("Waiting for 3DS Simulator...")
                    # 3DS in sandbox is usually an iframe or redirection
                    # We look for the "Password" input or "OK" button in the simulator
                    # This part is tricky as it's often in an iframe

                    # Wait for a moment for 3DS to load
                    time.sleep(5)

                    # Sometimes it's a redirection to another page
                    if "api.sandbox.veritrans.co.id" in page.url or "api.sandbox.midtrans.com" in page.url:
                         page.get_by_placeholder("112233").fill("112233")
                         page.get_by_text("OK").click()
                         logger.info("Entered 3DS OTP.")
                    else:
                        # Check frames
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
                page.wait_for_selector("text=Transaction Successful", timeout=15000)
                logger.info("PAYMENT SUCCESSFUL!")

            except PlaywrightTimeoutError:
                logger.error("Timeout waiting for element. The flow might have changed or network is slow.")
                # Capture screenshot for debugging
                page.screenshot(path="error_screenshot.png")
                logger.info("Screenshot saved to error_screenshot.png")
                raise
            except Exception as e:
                logger.error(f"An error occurred during simulation: {e}")
                raise
            finally:
                browser.close()

if __name__ == "__main__":
    tester = MidtransTester()

    # Example usage:
    # 1. Create a transaction (Need valid keys)
    # order_id = f"test-order-{int(time.time())}"
    # try:
    #     url = tester.create_transaction_token(order_id, 10000)
    #     tester.simulate_payment(url)
    # except Exception as e:
    #     logger.error("Test failed.")

    logger.info("MidtransTester initialized. Set keys and uncomment usage code to run.")
