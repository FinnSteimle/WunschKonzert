import random
import uuid


def generate_room_id() -> str:
    return str(uuid.uuid4())


def generate_join_code(length: int = 6) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choices(alphabet, k=length))


def generate_queue_entry_id() -> str:
    return f"QENTRY{uuid.uuid4().hex[:8].upper()}"
