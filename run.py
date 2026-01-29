import requests
import base64
import json
import logging
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MidtransAutomator:
    def __init__(self):
        self.session = requests.Session()
        # Default user agent from logs
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
        })
        self.base_api_url = "https://api.midtrans.com"
        self.base_app_url = "https://app.midtrans.com"

    def fetch_transaction_details(self, snap_token: str) -> Dict[str, Any]:
        """
        Fetches transaction details using the Snap token.
        """
        url = f"{self.base_app_url}/snap/v1/transactions/{snap_token}"
        logger.info(f"Fetching transaction details from: {url}")
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            logger.info("Transaction details fetched successfully.")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching transaction details: {e}")
            raise

    def get_card_token(self, card_details: Dict[str, str], client_key: str) -> str:
        """
        Exchanges card details for a card token.
        """
        url = f"{self.base_api_url}/v2/token"
        logger.info(f"Requesting card token from: {url}")

        # Construct Basic Auth header with client_key + ":"
        auth_str = f"{client_key}:"
        auth_bytes = auth_str.encode('ascii')
        base64_bytes = base64.b64encode(auth_bytes)
        auth_header = f"Basic {base64_bytes.decode('ascii')}"

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": auth_header,
            "Origin": "https://app.midtrans.com",
            "Referer": "https://app.midtrans.com/"
        }

        # Payload matching the log analysis
        payload = {
            "card_number": card_details.get("card_number"),
            "card_cvv": card_details.get("card_cvv"),
            "card_exp_month": card_details.get("card_exp_month"),
            "card_exp_year": card_details.get("card_exp_year")
        }

        try:
            response = self.session.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if "token_id" in data:
                logger.info("Card token obtained successfully.")
                return data["token_id"]
            else:
                logger.error(f"Failed to get token_id. Response: {data}")
                raise ValueError("No token_id in response")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting card token: {e}")
            raise

    def charge_transaction(self, snap_token: str, card_token: str, transaction_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Performs the charge using the card token.
        """
        url = f"{self.base_app_url}/snap/v2/transactions/{snap_token}/charge"
        logger.info(f"Charging transaction at: {url}")

        # Extract necessary details from transaction_details for headers/cookies if needed
        # The logs showed cookies: locale=id; preferredPayment-{merchant_id}=credit_card
        merchant_id = transaction_details.get("merchant", {}).get("merchant_id")
        
        if merchant_id:
             self.session.cookies.set(f"preferredPayment-{merchant_id}", "credit_card", domain="app.midtrans.com")
        self.session.cookies.set("locale", "id", domain="app.midtrans.com")

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Source": "snap",
            "X-Source-App-Type": "redirection",
            "X-Source-Version": "2.3.0",
            "Referer": f"https://app.midtrans.com/snap/v4/redirection/{snap_token}",
            "Origin": "https://app.midtrans.com"
        }

        customer_details = transaction_details.get("customer_details", {})
        
        charge_payload = {
            "payment_type": "credit_card",
            "payment_params": {
                "card_token": card_token
            },
            "promo_details": None,
            "customer_details": {
                "email": customer_details.get("email"),
                "phone": customer_details.get("phone"),
                "full_name": f"{customer_details.get('first_name', '')} {customer_details.get('last_name', '')}".strip() or customer_details.get("last_name"),
            }
        }
        
        # Add address if available
        billing_addr = customer_details.get("billing_address", {})
        if billing_addr:
             charge_payload["customer_details"]["address"] = f"{billing_addr.get('address', '')}, {billing_addr.get('city', '')} {billing_addr.get('postal_code', '')}"

        try:
            response = self.session.post(url, headers=headers, json=charge_payload)
            # 201 Created is success, but we shouldn't raise for status immediately if we want to return the response even on failure
            if not response.ok:
                logger.error(f"Charge failed with status {response.status_code}")
                # We can still try to parse JSON error
            
            try:
                data = response.json()
            except ValueError:
                response.raise_for_status() # If not JSON, then raise error

            logger.info(f"Charge response status: {response.status_code}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error charging transaction: {e}")
            raise

    def process_payment(self, snap_token: str, card_details: Dict[str, str]) -> Dict[str, Any]:
        """
        Orchestrates the payment flow.
        """
        logger.info(f"Starting payment process for Snap Token: {snap_token}")
        
        # Step 1: Get Details
        details = self.fetch_transaction_details(snap_token)
        
        # Extract Client Key
        client_key = details.get("merchant", {}).get("client_key")
        if not client_key:
            raise ValueError("Could not find client_key in transaction details.")
            
        logger.info(f"Found Client Key: {client_key}")
        
        # Step 2: Get Card Token
        card_token = self.get_card_token(card_details, client_key)
        
        # Step 3: Charge
        charge_response = self.charge_transaction(snap_token, card_token, details)
        
        # Step 4: Check for Redirect (3DS)
        redirect_url = charge_response.get("redirect_url")
        if redirect_url:
            logger.warning("3D Secure Redirect Required!")
            logger.warning(f"Please visit: {redirect_url}")
            return {
                "status": "3ds_required",
                "redirect_url": redirect_url,
                "response": charge_response
            }
        
        status_code = charge_response.get("status_code")
        if status_code in ["200", "201"]:
             return {
                "status": "success",
                "response": charge_response
            }
        else:
             return {
                "status": "failed",
                "response": charge_response
            }

if __name__ == "__main__":
    
    SNAP_TOKEN = "a4ea6f12-beb3-495f-b1d0-9da6138996bd"
    CARD_DETAILS = {
        "card_number": "5154620021177025", 
        "card_cvv": "622",                
        "card_exp_month": "09",           
        "card_exp_year": "2028"           
    }
    
    automator = MidtransAutomator()
    try:
        result = automator.process_payment(SNAP_TOKEN, CARD_DETAILS)
        print(json.dumps(result, indent=2))
    except Exception as e:
        logger.error(f"Payment process failed: {e}")



