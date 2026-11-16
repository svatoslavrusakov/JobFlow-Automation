"""Читает каталог Gemini без генерации и передачи резюме."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ai.settings import read_text


def list_models(values):
    """Каталог не подтверждает наличие квоты на генерацию выбранной модели."""
    key = read_text(values["key_file"])
    names = set()
    token = ""
    while True:
        query = {"pageSize": 1000}
        if token:
            query["pageToken"] = token
        request = Request(
            "https://generativelanguage.googleapis.com/v1beta/models?" + urlencode(query),
            headers={"x-goog-api-key": key},
        )
        try:
            with urlopen(request, timeout=values["timeout"]) as response:
                data = json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"Каталог Gemini вернул HTTP {error.code}.") from None
        except (URLError, ValueError):
            raise RuntimeError("Не удалось прочитать каталог Gemini.") from None
        for model in data.get("models", []):
            name = model.get("name", "").removeprefix("models/")
            if name.startswith("gemini-"):
                names.add(name)
        token = data.get("nextPageToken", "")
        if not token:
            return sorted(names)
