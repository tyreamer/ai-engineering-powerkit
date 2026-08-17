import unittest

from greeting import greeting


class GreetingTests(unittest.TestCase):
    def test_requested_capitalization(self) -> None:
        self.assertEqual(greeting(), "Hello")
