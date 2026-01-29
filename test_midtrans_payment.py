import unittest
from unittest.mock import MagicMock, patch
import json
from midtrans_payment import MidtransAutomator

class TestMidtransAutomator(unittest.TestCase):
    def setUp(self):
        self.automator = MidtransAutomator()
        self.snap_token = "dummy-snap-token"
        self.client_key = "dummy-client-key"
        self.merchant_id = "dummy-merchant-id"
        self.card_details = {
            "card_number": "1234567890123456",
            "card_cvv": "123",
            "card_exp_month": "12",
            "card_exp_year": "2030"
        }

    @patch('requests.Session.get')
    def test_fetch_transaction_details(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "token": self.snap_token,
            "merchant": {"client_key": self.client_key, "merchant_id": self.merchant_id},
            "customer_details": {"email": "test@example.com"}
        }
        mock_get.return_value = mock_response

        details = self.automator.fetch_transaction_details(self.snap_token)

        self.assertEqual(details["token"], self.snap_token)
        mock_get.assert_called_with(f"https://app.midtrans.com/snap/v1/transactions/{self.snap_token}")

    @patch('requests.Session.post')
    def test_get_card_token(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token_id": "dummy-card-token"}
        mock_post.return_value = mock_response

        token = self.automator.get_card_token(self.card_details, self.client_key)

        self.assertEqual(token, "dummy-card-token")

        # Check URL
        self.assertTrue(mock_post.call_args[0][0].endswith("/v2/token"))

        # Check Headers (Auth)
        headers = mock_post.call_args[1]['headers']
        self.assertIn("Authorization", headers)
        self.assertTrue(headers["Authorization"].startswith("Basic "))

        # Check Payload
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload["card_number"], self.card_details["card_number"])

    @patch('requests.Session.post')
    def test_charge_transaction(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.ok = True
        mock_response.json.return_value = {"status_code": "201", "transaction_status": "pending"}
        mock_post.return_value = mock_response

        card_token = "dummy-card-token"
        transaction_details = {
            "merchant": {"merchant_id": self.merchant_id},
            "customer_details": {
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "User",
                "billing_address": {"address": "Street", "city": "City", "postal_code": "12345"}
            }
        }

        response = self.automator.charge_transaction(self.snap_token, card_token, transaction_details)

        self.assertEqual(response["status_code"], "201")

        # Check URL
        self.assertTrue(mock_post.call_args[0][0].endswith(f"/snap/v2/transactions/{self.snap_token}/charge"))

        # Check Headers
        headers = mock_post.call_args[1]['headers']
        self.assertEqual(headers["X-Source"], "snap")
        self.assertEqual(headers["Referer"], f"https://app.midtrans.com/snap/v4/redirection/{self.snap_token}")

        # Check Cookies
        # Cookie verification is a bit trickier with requests.Session mock, but we can check if cookie jar was updated
        self.assertEqual(self.automator.session.cookies.get("locale", domain="app.midtrans.com"), "id")
        self.assertEqual(self.automator.session.cookies.get(f"preferredPayment-{self.merchant_id}", domain="app.midtrans.com"), "credit_card")

        # Check Payload
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload["payment_params"]["card_token"], card_token)
        self.assertEqual(payload["customer_details"]["email"], "test@example.com")
        self.assertIn("address", payload["customer_details"])

    @patch('midtrans_payment.MidtransAutomator.fetch_transaction_details')
    @patch('midtrans_payment.MidtransAutomator.get_card_token')
    @patch('midtrans_payment.MidtransAutomator.charge_transaction')
    def test_process_payment_3ds(self, mock_charge, mock_get_token, mock_get_details):
        mock_get_details.return_value = {"merchant": {"client_key": self.client_key}}
        mock_get_token.return_value = "dummy-card-token"
        mock_charge.return_value = {
            "status_code": "201",
            "redirect_url": "https://api.midtrans.com/3ds",
            "transaction_status": "pending"
        }

        result = self.automator.process_payment(self.snap_token, self.card_details)

        self.assertEqual(result["status"], "3ds_required")
        self.assertEqual(result["redirect_url"], "https://api.midtrans.com/3ds")

if __name__ == '__main__':
    unittest.main()
