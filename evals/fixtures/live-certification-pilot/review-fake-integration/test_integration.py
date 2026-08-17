import unittest

from integration import BillingClient


class BillingClientTests(unittest.TestCase):
    def test_returns_paid(self) -> None:
        self.assertEqual(BillingClient().charge("customer", 500), {"status": "paid"})
