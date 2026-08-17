import unittest
from decimal import Decimal

from pricing import discounted_total


class PricingTests(unittest.TestCase):
    def test_twenty_percent_discount(self) -> None:
        self.assertEqual(discounted_total(Decimal("100"), Decimal("20")), Decimal("80"))
