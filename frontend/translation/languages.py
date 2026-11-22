import json
import os

class Language:
    def load_language(code):
        with open(f"translation/{code}.json", encoding="utf-8") as f:
            return json.load(f)