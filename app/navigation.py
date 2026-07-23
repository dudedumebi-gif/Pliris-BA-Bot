from __future__ import annotations

from dataclasses import dataclass

from app.ui_config import UIMode


@dataclass(frozen=True)
class PageSpec:
    """Framework-independent Streamlit page declaration."""

    path: str
    title: str
    icon: str
    default: bool = False


PUBLIC_CHAT_PAGE = PageSpec(
    path="app/pages/1_Chat.py",
    title="Chat",
    icon="💬",
    default=True,
)

DEVELOPER_HOME_PAGE = PageSpec(
    path="app/developer_pages/0_Developer.py",
    title="Developer Console",
    icon="🛠️",
    default=True,
)


def navigation_manifest(
    mode: UIMode,
) -> list[PageSpec] | dict[str, list[PageSpec]]:
    """Return the pages available in the configured interface mode."""

    if mode is UIMode.PUBLIC:
        return [PUBLIC_CHAT_PAGE]

    return {
        "Developer": [DEVELOPER_HOME_PAGE],
        "Workspace": [
            PageSpec(
                path=PUBLIC_CHAT_PAGE.path,
                title=PUBLIC_CHAT_PAGE.title,
                icon=PUBLIC_CHAT_PAGE.icon,
            )
        ],
    }
