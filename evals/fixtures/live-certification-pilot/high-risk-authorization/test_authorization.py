import unittest

from authorization import can_delete


class AuthorizationTests(unittest.TestCase):
    def test_caller_cannot_escalate_role(self) -> None:
        roles = {"member-1": "member"}
        self.assertFalse(can_delete("member-1", "admin", roles))

    def test_trusted_admin_is_allowed(self) -> None:
        roles = {"admin-1": "admin"}
        self.assertTrue(can_delete("admin-1", "member", roles))
