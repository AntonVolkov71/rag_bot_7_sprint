import os
import requests
import logging

log = logging.getLogger("rag")

YANDEX_GPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


class YandexGptClient:
    def __init__(self):
        self.iam_token = os.getenv("YANDEX_IAM_TOKEN")
        self.folder_id = os.getenv("YANDEX_FOLDER_ID")
        self.model = os.getenv("YANDEX_GPT_MODEL", "yandexgpt-lite")

        self.temperature = float(os.getenv("YANDEX_GPT_TEMPERATURE", "0.2"))
        self.max_tokens = int(os.getenv("YANDEX_GPT_MAX_TOKENS", "800"))
        self.stream = env_bool("YANDEX_GPT_STREAM", False)

        if not self.iam_token or not self.folder_id:
            raise RuntimeError("YANDEX_IAM_TOKEN or YANDEX_FOLDER_ID not set")

        log.info(
            "YandexGPT config: model=%s temp=%s max_tokens=%s stream=%s",
            self.model,
            self.temperature,
            self.max_tokens,
            self.stream,
        )

    def generate(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.iam_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "modelUri": f"gpt://{self.folder_id}/{self.model}",
            "completionOptions": {
                "stream": self.stream,
                "temperature": self.temperature,
                "maxTokens": self.max_tokens,
            },
            "messages": [
                {
                    "role": "user",
                    "text": prompt,
                }
            ],
        }

        log.info("Sending prompt to YandexGPT (chars=%s)", len(prompt))

        resp = requests.post(
            YANDEX_GPT_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if resp.status_code != 200:
            msg = f"YandexGPT HTTP {resp.status_code}: {resp.text}"
            log.error(msg)
            raise RuntimeError(msg)

        data = resp.json()

        try:
            return data["result"]["alternatives"][0]["message"]["text"]
        except Exception:
            log.error("Unexpected YandexGPT response: %s", data)
            raise
