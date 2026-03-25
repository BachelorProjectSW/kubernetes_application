from locust import HttpUser, task, between

TARGET_HOST = "http://127.0.0.1:8020"
REQUESTS_PER_USER = 20
QUESTION = "What is your favorit food?"

MIN_WAIT = 0.1
MAX_WAIT = 5

class APIUser(HttpUser):
    host = TARGET_HOST
    wait_time = between(MIN_WAIT, MAX_WAIT)

    def on_start(self):
        self.requests_sent = 0

    @task
    def send_request(self):
        if self.requests_sent >= REQUESTS_PER_USER:
            return

        # Include full path here
        self.client.post("/handle_llm_question", json={"question": QUESTION})
        self.requests_sent += 1
