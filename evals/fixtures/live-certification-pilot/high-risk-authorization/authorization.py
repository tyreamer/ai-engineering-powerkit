def can_delete(user_id: str, acting_role: str, role_store: dict[str, str]) -> bool:
    del user_id, role_store
    return acting_role == "admin"
