from locust import HttpUser, task, between

class MyUser(HttpUser):
    wait_time = between(1, 5)  # wait 1-5 seconds between tasks

    @task
    def test_llm(self):
        with self.client.post("/llm", json={"question": "What is 12+13"}, catch_response=True) as response:
            try:
                print(response.json())
            except Exception:
                print("FAILED")
                    
