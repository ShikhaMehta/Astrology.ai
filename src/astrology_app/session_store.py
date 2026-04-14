class SessionStore:
    """In-memory session store (no persistent storage)."""

    def __init__(self) -> None:
        self._data: dict[str, object] = {}

    def set(self, key: str, value: object) -> None:
        self._data[key] = value

    def get(self, key: str) -> object | None:
        return self._data.get(key)

    def clear(self) -> None:
        self._data.clear()
