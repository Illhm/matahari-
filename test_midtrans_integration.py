import unittest
from unittest.mock import MagicMock, patch
from midtrans_integration import MidtransTester

class TestMidtransTester(unittest.TestCase):
    @patch('midtrans_integration.midtransclient.Snap')
    def test_create_transaction_token(self, MockSnap):
        # Setup mock
        mock_snap_instance = MockSnap.return_value
        expected_url = "https://app.sandbox.midtrans.com/snap/v2/vtweb/test-token"
        mock_snap_instance.create_transaction.return_value = {
            'token': 'test-token',
            'redirect_url': expected_url
        }

        # Initialize
        tester = MidtransTester()

        # Call method
        url = tester.create_transaction_token("order-123", 10000)

        # Verify
        self.assertEqual(url, expected_url)
        mock_snap_instance.create_transaction.assert_called_once()
        args, _ = mock_snap_instance.create_transaction.call_args
        self.assertEqual(args[0]['transaction_details']['order_id'], "order-123")

    def test_security_check(self):
        tester = MidtransTester()
        # Mocking os.getenv is not needed since we check logic inside simulate_payment

        unsafe_url = "https://app.midtrans.com/snap/v2/vtweb/production-token"

        with self.assertRaises(ValueError) as cm:
            tester.simulate_payment(unsafe_url)

        self.assertIn("restricted to Midtrans Sandbox", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
