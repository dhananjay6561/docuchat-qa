"""Load test for DocuChat: a realistic mix of questions, ramped up in stages.

Run through perf/run_load_test.sh, which starts the app with the mock LLM so no API credits are
spent, then summarises latency, errors and cost per query (from the logged token counts).
"""

import random
import uuid

from locust import HttpUser, LoadTestShape, between, task

GROUNDED = [
    "How many days of paid annual leave do full-time employees get?",
    "How long do refunds take?",
    "Which countries does Lumen Home ship to?",
    "How much does express shipping cost?",
    "Does the Lumen Hub work with 5 GHz Wi-Fi?",
    "What warranty do Lumen products have?",
    "How do I factory reset the Lumen Hub?",
    "When is payment due for invoice INV-2026-0042?",
]
UNANSWERABLE = [
    "What is the CEO's name?",
    "Does Lumen offer a student discount?",
    "What is the weather today?",
]
ORDERS = ["ORD-1001", "ORD-1002", "ORD-1003", "ORD-1005", "ORD-9999"]


class ChatUser(HttpUser):
    """One simulated customer: keeps a session and pauses 1-3 s between messages, like a person."""

    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.session_id = f"load-{uuid.uuid4().hex[:8]}"

    def _chat(self, message: str, label: str) -> None:
        # `name` groups requests by kind in the stats instead of one row per unique question.
        with self.client.post(
            "/chat",
            json={"session_id": self.session_id, "message": message},
            name=f"/chat [{label}]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
            elif not response.json().get("answer"):
                response.failure("empty answer")

    @task(6)
    def grounded_question(self) -> None:
        self._chat(random.choice(GROUNDED), "grounded")

    @task(2)
    def unanswerable_question(self) -> None:
        self._chat(random.choice(UNANSWERABLE), "refusal")

    @task(2)
    def order_status(self) -> None:
        self._chat(f"Where is my order {random.choice(ORDERS)}?", "tool")

    @task(1)
    def health(self) -> None:
        self.client.get("/health", name="/health")


class RampStages(LoadTestShape):
    """Ramp 10 -> 25 -> 50 concurrent users, then hold, so latency can be read at each level."""

    stages = [(20, 10), (40, 25), (90, 50)]  # (ends at second, users)
    spawn_rate = 5

    def tick(self) -> tuple[int, float] | None:
        run_time = self.get_run_time()
        for ends_at, users in self.stages:
            if run_time < ends_at:
                return users, self.spawn_rate
        return None  # stop the test
