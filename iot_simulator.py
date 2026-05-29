import random
import time

import requests

API_URL = "http://127.0.0.1:8000/iot/rooms"
ROOM_IDS = ["DOC-101", "THR-201", "EQP-301", "DOC-102", "THR-202"]
STATUSES = ["available", "busy"]


def run_simulator(interval_seconds: int = 5) -> None:
    while True:
        room_id = random.choice(ROOM_IDS)
        status = random.choice(STATUSES)
        response = requests.patch(f"{API_URL}/{room_id}", json={"status": status}, timeout=10)
        response.raise_for_status()
        print(f"{room_id} -> {status}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_simulator()
