from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app_v2.registry import ACTION_LOOKUP

RECENT_LIMIT = 12


def _default_preferences_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return root / "IT Toolkit" / "preferences.json"


class ToolPreferences(QObject):
    favorites_changed = Signal()
    recents_changed = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        path: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.path = path or _default_preferences_path()
        self._favorites: list[str] = []
        self._recents: list[str] = []
        self._load()

    @property
    def favorites(self) -> tuple[str, ...]:
        return tuple(self._favorites)

    @property
    def recents(self) -> tuple[str, ...]:
        return tuple(self._recents)

    def is_favorite(self, action_key: str) -> bool:
        return action_key in self._favorites

    def toggle_favorite(self, action_key: str) -> bool:
        if action_key not in ACTION_LOOKUP:
            return False
        if action_key in self._favorites:
            self._favorites.remove(action_key)
            selected = False
        else:
            self._favorites.append(action_key)
            selected = True
        self._save()
        self.favorites_changed.emit()
        return selected

    def remove_favorite(self, action_key: str) -> None:
        if action_key not in self._favorites:
            return
        self._favorites.remove(action_key)
        self._save()
        self.favorites_changed.emit()

    def move_favorite(self, action_key: str, offset: int) -> None:
        if action_key not in self._favorites:
            return
        index = self._favorites.index(action_key)
        target = max(0, min(len(self._favorites) - 1, index + offset))
        if target == index:
            return
        self._favorites.insert(target, self._favorites.pop(index))
        self._save()
        self.favorites_changed.emit()

    def record_recent(self, action_key: str) -> None:
        if action_key not in ACTION_LOOKUP:
            return
        if action_key in self._recents:
            self._recents.remove(action_key)
        self._recents.insert(0, action_key)
        del self._recents[RECENT_LIMIT:]
        self._save()
        self.recents_changed.emit()

    def clear_recents(self) -> None:
        if not self._recents:
            return
        self._recents.clear()
        self._save()
        self.recents_changed.emit()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return
            favorites = payload.get("favorites", [])
            recents = payload.get("recents", [])
            self._favorites = self._valid_keys(favorites)
            self._recents = self._valid_keys(recents)[:RECENT_LIMIT]
        except (OSError, ValueError, TypeError):
            self._favorites = []
            self._recents = []

    @staticmethod
    def _valid_keys(values: object) -> list[str]:
        if not isinstance(values, list):
            return []
        result: list[str] = []
        for value in values:
            if (
                isinstance(value, str)
                and value in ACTION_LOOKUP
                and value not in result
            ):
                result.append(value)
        return result

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    {
                        "favorites": self._favorites,
                        "recents": self._recents,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError:
            return
