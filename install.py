#!/usr/bin/env python3
"""
Kimi Web Folders Plugin Installer
=================================
Automatically patches kimi-cli to add folder organization support for the web UI.

Usage:
    python install.py

This script is idempotent: running it multiple times is safe.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def find_kimi_cli() -> Path:
    """Locate the installed kimi_cli package directory."""
    # Try several common interpreter paths (uv, pipx, system pip)
    candidates = [
        shutil.which("python3"),
        shutil.which("python"),
        str(Path.home() / ".local/share/uv/tools/kimi-cli/bin/python"),
    ]
    for exe in candidates:
        if not exe:
            continue
        try:
            import subprocess
            out = subprocess.run(
                [exe, "-c", "import kimi_cli, os; print(os.path.dirname(kimi_cli.__file__))"],
                capture_output=True, text=True, timeout=10, check=True,
            )
            path = Path(out.stdout.strip())
            if path.is_dir():
                return path
        except Exception:
            continue
    fail("Could not find kimi_cli installation. Is kimi installed?")


def replace_exact(content: str, old: str, new: str, filename: str) -> str:
    """Exact text replacement with clear error messages."""
    if old == new:
        return content
    if old not in content:
        # Maybe already patched? Check if new is present.
        if new in content:
            return content
        fail(
            f"Cannot patch {filename}: expected text block not found.\n"
            f"This usually means kimi-cli was upgraded and the source changed.\n"
            f"Please open an issue or update the plugin."
        )
    return content.replace(old, new, 1)


def write_if_changed(path: Path, content: str) -> bool:
    """Write file only if content changed. Returns True if written."""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def patch_session_state(base: Path) -> None:
    path = base / "session_state.py"
    old = (
        "    # Todo list state\n"
        "    todos: list[TodoItemState] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]\n"
    )
    new = (
        "    # Todo list state\n"
        "    todos: list[TodoItemState] = Field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]\n"
        "    # Folder organization (web UI only)\n"
        "    folder_id: str | None = Field(default=None, description=\"ID of the folder this session belongs to\")\n"
    )
    content = replace_exact(path.read_text(encoding="utf-8"), old, new, path.name)
    if write_if_changed(path, content):
        ok("Patched session_state.py")
    else:
        ok("session_state.py already patched (skipped)")


def patch_web_models(base: Path) -> None:
    path = base / "web" / "models.py"
    text = path.read_text(encoding="utf-8")

    # 1. Add folder_id to Session
    old1 = (
        "    session_dir: str | None = Field(default=None, description=\"Session directory path\")\n"
        "    archived: bool = Field(default=False, description=\"Whether the session is archived\")\n"
    )
    new1 = (
        "    session_dir: str | None = Field(default=None, description=\"Session directory path\")\n"
        "    archived: bool = Field(default=False, description=\"Whether the session is archived\")\n"
        "    folder_id: str | None = Field(default=None, description=\"Folder ID this session belongs to\")\n"
    )
    text = replace_exact(text, old1, new1, path.name)

    # 2. Add folder_id to UpdateSessionRequest + add Folder class
    old2 = (
        "class UpdateSessionRequest(BaseModel):\n"
        '    """Update session request."""\n\n'
        "    title: str | None = Field(default=None, min_length=1, max_length=200)\n"
        "    archived: bool | None = Field(default=None, description=\"Archive or unarchive the session\")\n"
    )
    new2 = (
        "class UpdateSessionRequest(BaseModel):\n"
        '    """Update session request."""\n\n'
        "    title: str | None = Field(default=None, min_length=1, max_length=200)\n"
        "    archived: bool | None = Field(default=None, description=\"Archive or unarchive the session\")\n"
        "    folder_id: str | None = Field(default=None, description=\"Move session to folder (set to empty string to remove)\")\n\n\n"
        "class Folder(BaseModel):\n"
        '    """Folder for organizing sessions."""\n\n'
        "    id: str = Field(..., description=\"Folder unique ID\")\n"
        "    name: str = Field(..., description=\"Folder display name\")\n"
        "    created_at: datetime = Field(..., description=\"Creation timestamp\")\n"
        "    updated_at: datetime = Field(..., description=\"Last update timestamp\")\n"
        "    sort_order: int = Field(default=0, description=\"Sort order\")\n"
    )
    text = replace_exact(text, old2, new2, path.name)

    if write_if_changed(path, text):
        ok("Patched web/models.py")
    else:
        ok("web/models.py already patched (skipped)")


def patch_web_store_sessions(base: Path) -> None:
    path = base / "web" / "store" / "sessions.py"
    text = path.read_text(encoding="utf-8")

    # 1. _build_joint_session add folder_id
    old1 = (
        "        session_dir=str(entry.session_dir),\n"
        "        kimi_cli_session=kimi_session,\n"
        "        archived=entry.state.archived,\n"
        "    )\n"
    )
    new1 = (
        "        session_dir=str(entry.session_dir),\n"
        "        kimi_cli_session=kimi_session,\n"
        "        archived=entry.state.archived,\n"
        "        folder_id=entry.state.folder_id,\n"
        "    )\n"
    )
    text = replace_exact(text, old1, new1, path.name)

    # 2. load_sessions_page signature + folder filter
    old2 = (
        "def load_sessions_page(\n"
        "    *,\n"
        "    limit: int = 100,\n"
        "    offset: int = 0,\n"
        "    query: str | None = None,\n"
        "    archived: bool | None = None,\n"
        ") -> list[JointSession]:\n"
        '    """Load a paginated list of sessions, optionally filtered by query and archived status.\n\n'
        "    Args:\n"
        "        limit: Maximum number of sessions to return.\n"
        "        offset: Number of sessions to skip.\n"
        "        query: Optional search query to filter by title or work_dir.\n"
        "        archived: Filter by archived status.\n"
        "            - None (default): Only return non-archived sessions.\n"
        "            - True: Only return archived sessions.\n"
        "            - False: Only return non-archived sessions.\n"
        "    \"\"\"\n"
        "    entries = list(_load_sessions_index_cached())\n\n"
        "    # Filter by archived status\n"
        "    if archived is None or archived is False:\n"
        "        entries = [e for e in entries if not e.state.archived]\n"
        "    else:\n"
        "        entries = [e for e in entries if e.state.archived]\n"
    )
    new2 = (
        "def load_sessions_page(\n"
        "    *,\n"
        "    limit: int = 100,\n"
        "    offset: int = 0,\n"
        "    query: str | None = None,\n"
        "    archived: bool | None = None,\n"
        "    folder_id: str | None = None,\n"
        ") -> list[JointSession]:\n"
        '    """Load a paginated list of sessions, optionally filtered by query and archived status.\n\n'
        "    Args:\n"
        "        limit: Maximum number of sessions to return.\n"
        "        offset: Number of sessions to skip.\n"
        "        query: Optional search query to filter by title or work_dir.\n"
        "        archived: Filter by archived status.\n"
        "            - None (default): Only return non-archived sessions.\n"
        "            - True: Only return archived sessions.\n"
        "            - False: Only return non-archived sessions.\n"
        "        folder_id: Filter by folder ID.\n"
        "            - None (default): Return all sessions regardless of folder.\n"
        "            - \"\": Only return sessions without a folder (unfiled).\n"
        "            - Any other value: Only return sessions in that folder.\n"
        "    \"\"\"\n"
        "    entries = list(_load_sessions_index_cached())\n\n"
        "    # Filter by archived status\n"
        "    if archived is None or archived is False:\n"
        "        entries = [e for e in entries if not e.state.archived]\n"
        "    else:\n"
        "        entries = [e for e in entries if e.state.archived]\n\n"
        "    # Filter by folder\n"
        "    if folder_id is not None:\n"
        '        if folder_id == "":\n'
        "            entries = [e for e in entries if e.state.folder_id is None or e.state.folder_id == \"\"]\n"
        "        else:\n"
        "            entries = [e for e in entries if e.state.folder_id == folder_id]\n"
    )
    text = replace_exact(text, old2, new2, path.name)

    if write_if_changed(path, text):
        ok("Patched web/store/sessions.py")
    else:
        ok("web/store/sessions.py already patched (skipped)")


def patch_web_api_sessions(base: Path) -> None:
    path = base / "web" / "api" / "sessions.py"
    text = path.read_text(encoding="utf-8")

    # 1. list_sessions signature + call
    old1 = (
        "async def list_sessions(\n"
        "    runner: KimiCLIRunner = Depends(get_runner),\n"
        "    limit: int = 100,\n"
        "    offset: int = 0,\n"
        "    q: str | None = None,\n"
        "    archived: bool | None = None,\n"
        ") -> list[Session]:\n"
        '    """List sessions with optional pagination and search.\n\n'
        "    Args:\n"
        "        limit: Maximum number of sessions to return (default 100, max 500).\n"
        "        offset: Number of sessions to skip (default 0).\n"
        "        q: Optional search query to filter by title or work_dir.\n"
        "        archived: Filter by archived status.\n"
        "            - None (default): Only return non-archived sessions.\n"
        "            - True: Only return archived sessions.\n"
        "    \"\"\"\n"
    )
    new1 = (
        "async def list_sessions(\n"
        "    runner: KimiCLIRunner = Depends(get_runner),\n"
        "    limit: int = 100,\n"
        "    offset: int = 0,\n"
        "    q: str | None = None,\n"
        "    archived: bool | None = None,\n"
        "    folder_id: str | None = None,\n"
        ") -> list[Session]:\n"
        '    """List sessions with optional pagination and search.\n\n'
        "    Args:\n"
        "        limit: Maximum number of sessions to return (default 100, max 500).\n"
        "        offset: Number of sessions to skip (default 0).\n"
        "        q: Optional search query to filter by title or work_dir.\n"
        "        archived: Filter by archived status.\n"
        "            - None (default): Only return non-archived sessions.\n"
        "            - True: Only return archived sessions.\n"
        "        folder_id: Filter by folder ID.\n"
        "            - None (default): Return all sessions.\n"
        "            - \"\": Only return unfiled sessions.\n"
        "            - Any other value: Only return sessions in that folder.\n"
        "    \"\"\"\n"
    )
    text = replace_exact(text, old1, new1, path.name)

    old1b = "    sessions = load_sessions_page(limit=limit, offset=offset, query=q, archived=archived)\n"
    new1b = "    sessions = load_sessions_page(limit=limit, offset=offset, query=q, archived=archived, folder_id=folder_id)\n"
    text = replace_exact(text, old1b, new1b, path.name)

    # 2. update_session folder_id handling
    old2 = (
        "    # Update archived status if provided\n"
        "    if request.archived is not None:\n"
        "        state.archived = request.archived\n"
        "        if request.archived:\n"
        "            state.archived_at = time.time()\n"
        "            state.auto_archive_exempt = False\n"
        "        else:\n"
        "            state.archived_at = None\n"
        "            state.auto_archive_exempt = True\n\n"
        "    save_session_state(state, session_dir)\n"
    )
    new2 = (
        "    # Update archived status if provided\n"
        "    if request.archived is not None:\n"
        "        state.archived = request.archived\n"
        "        if request.archived:\n"
        "            state.archived_at = time.time()\n"
        "            state.auto_archive_exempt = False\n"
        "        else:\n"
        "            state.archived_at = None\n"
        "            state.auto_archive_exempt = True\n\n"
        "    # Update folder_id if provided (empty string means remove from folder)\n"
        "    if request.folder_id is not None:\n"
        '        if request.folder_id == "":\n'
        "            state.folder_id = None\n"
        "        else:\n"
        "            state.folder_id = request.folder_id\n\n"
        "    save_session_state(state, session_dir)\n"
    )
    text = replace_exact(text, old2, new2, path.name)

    if write_if_changed(path, text):
        ok("Patched web/api/sessions.py")
    else:
        ok("web/api/sessions.py already patched (skipped)")


def patch_web_api_init(base: Path) -> None:
    path = base / "web" / "api" / "__init__.py"
    old = (
        '"""API routes."""\n\n'
        "from kimi_cli.web.api import config, open_in, sessions\n\n"
        "config_router = config.router\n"
        "sessions_router = sessions.router\n"
        "work_dirs_router = sessions.work_dirs_router\n"
        "open_in_router = open_in.router\n\n"
        "__all__ = [\n"
        '    "config_router",\n'
        '    "open_in_router",\n'
        '    "sessions_router",\n'
        '    "work_dirs_router",\n'
        "]\n"
    )
    new = (
        '"""API routes."""\n\n'
        "from kimi_cli.web.api import config, folders, open_in, sessions\n\n"
        "config_router = config.router\n"
        "folders_router = folders.router\n"
        "sessions_router = sessions.router\n"
        "work_dirs_router = sessions.work_dirs_router\n"
        "open_in_router = open_in.router\n\n"
        "__all__ = [\n"
        '    "config_router",\n'
        '    "folders_router",\n'
        '    "open_in_router",\n'
        '    "sessions_router",\n'
        '    "work_dirs_router",\n'
        "]\n"
    )
    text = replace_exact(path.read_text(encoding="utf-8"), old, new, path.name)
    if write_if_changed(path, text):
        ok("Patched web/api/__init__.py")
    else:
        ok("web/api/__init__.py already patched (skipped)")


def patch_web_app(base: Path) -> None:
    path = base / "web" / "app.py"
    text = path.read_text(encoding="utf-8")

    old1 = (
        "from kimi_cli.web.api import (\n"
        "    config_router,\n"
        "    open_in_router,\n"
        "    sessions_router,\n"
        "    work_dirs_router,\n"
        ")\n"
    )
    new1 = (
        "from kimi_cli.web.api import (\n"
        "    config_router,\n"
        "    folders_router,\n"
        "    open_in_router,\n"
        "    sessions_router,\n"
        "    work_dirs_router,\n"
        ")\n"
    )
    text = replace_exact(text, old1, new1, path.name)

    old2 = (
        "    application.include_router(config_router)\n"
        "    application.include_router(sessions_router)\n"
    )
    new2 = (
        "    application.include_router(config_router)\n"
        "    application.include_router(folders_router)\n"
        "    application.include_router(sessions_router)\n"
    )
    text = replace_exact(text, old2, new2, path.name)

    if write_if_changed(path, text):
        ok("Patched web/app.py")
    else:
        ok("web/app.py already patched (skipped)")


def patch_index_html(base: Path) -> None:
    path = base / "web" / "static" / "index.html"
    text = path.read_text(encoding="utf-8")

    # Make sure we only patch the vanilla index.html, not an already patched one
    if "kimi-folder-link" in text:
        ok("web/static/index.html already patched (skipped)")
        return

    old = (
        "  <body>\n"
        '    <div id="root"></div>\n'
        "  </body>\n"
        "</html>\n"
    )
    new = (
        "  <body>\n"
        '    <div id="root"></div>\n'
        "    <!-- Folder management quick entry -->\n"
        '    <a href="./folders.html" id="kimi-folder-link" title="会话文件夹管理" style="position:fixed;bottom:16px;right:16px;z-index:9999;width:44px;height:44px;border-radius:50%;background:#58a6ff;color:#fff;display:flex;align-items:center;justify-content:center;font-size:20px;text-decoration:none;box-shadow:0 4px 12px rgba(0,0,0,0.4);transition:transform .2s,background .2s;">📁</a>\n'
        "    <style>#kimi-folder-link:hover{transform:scale(1.1);background:#79b8ff}</style>\n"
        "    <script>(function(){var t=new URLSearchParams(location.search).get('token');var el=document.getElementById('kimi-folder-link');if(el&&t)el.href='./folders.html?token='+encodeURIComponent(t);})();</script>\n"
        "  </body>\n"
        "</html>\n"
    )
    text = replace_exact(text, old, new, path.name)
    if write_if_changed(path, text):
        ok("Patched web/static/index.html")
    else:
        ok("web/static/index.html already patched (skipped)")


def create_folders_store(base: Path) -> None:
    content = (
        '"""Folder storage for organizing sessions in the web UI."""\n\n'
        "from __future__ import annotations\n\n"
        "import time\n"
        "from pathlib import Path\n"
        "from uuid import uuid4\n\n"
        "from pydantic import BaseModel, Field\n\n"
        "from kimi_cli.utils.io import atomic_json_write\n"
        "from kimi_cli.utils.logging import logger\n\n"
        'FOLDERS_FILE = Path.home() / ".kimi" / "web_folders.json"\n\n\n'
        "class Folder(BaseModel):\n"
        '    """A folder for organizing sessions."""\n\n'
        "    id: str = Field(default_factory=lambda: str(uuid4()))\n"
        '    name: str = Field(..., min_length=1, max_length=100)\n'
        "    created_at: float = Field(default_factory=time.time)\n"
        "    updated_at: float = Field(default_factory=time.time)\n"
        '    sort_order: int = Field(default=0, description="Manual sort order")\n\n\n'
        "class FoldersData(BaseModel):\n"
        '    """Root data structure stored in web_folders.json."""\n\n'
        "    version: int = 1\n"
        '    folders: list[Folder] = Field(default_factory=list)\n\n\n'
        "def _load_data() -> FoldersData:\n"
        "    if not FOLDERS_FILE.exists():\n"
        "        return FoldersData()\n"
        "    try:\n"
        "        import json\n\n"
        "        with open(FOLDERS_FILE, encoding=\"utf-8\") as f:\n"
        "            return FoldersData.model_validate(json.load(f))\n"
        "    except Exception as e:\n"
        '        logger.warning("Failed to load folders data: {e}", e=e)\n'
        "        return FoldersData()\n\n\n"
        "def _save_data(data: FoldersData) -> None:\n"
        "    FOLDERS_FILE.parent.mkdir(parents=True, exist_ok=True)\n"
        "    atomic_json_write(data.model_dump(mode=\"json\"), FOLDERS_FILE)\n\n\n"
        "def list_folders() -> list[Folder]:\n"
        '    """List all folders, sorted by sort_order then created_at."""\n'
        "    data = _load_data()\n"
        '    return sorted(data.folders, key=lambda f: (f.sort_order, f.created_at))\n\n\n'
        "def get_folder(folder_id: str) -> Folder | None:\n"
        '    """Get a single folder by ID."""\n'
        "    data = _load_data()\n"
        "    for folder in data.folders:\n"
        "        if folder.id == folder_id:\n"
        "            return folder\n"
        "    return None\n\n\n"
        "def create_folder(name: str) -> Folder:\n"
        '    """Create a new folder."""\n'
        "    data = _load_data()\n"
        '    folder = Folder(name=name.strip())\n'
        "    data.folders.append(folder)\n"
        "    _save_data(data)\n"
        "    return folder\n\n\n"
        "def update_folder(folder_id: str, name: str | None = None, sort_order: int | None = None) -> Folder | None:\n"
        '    """Update folder name or sort_order."""\n'
        "    data = _load_data()\n"
        "    for folder in data.folders:\n"
        "        if folder.id == folder_id:\n"
        "            if name is not None:\n"
        "                folder.name = name.strip()\n"
        "            if sort_order is not None:\n"
        "                folder.sort_order = sort_order\n"
        "            folder.updated_at = time.time()\n"
        "            _save_data(data)\n"
        "            return folder\n"
        "    return None\n\n\n"
        "def delete_folder(folder_id: str) -> bool:\n"
        '    """Delete a folder. Sessions in this folder are NOT deleted."""\n'
        "    data = _load_data()\n"
        "    original_len = len(data.folders)\n"
        '    data.folders = [f for f in data.folders if f.id != folder_id]\n'
        "    if len(data.folders) == original_len:\n"
        "        return False\n"
        "    _save_data(data)\n"
        "    return True\n"
    )
    path = base / "web" / "store" / "folders.py"
    if write_if_changed(path, content):
        ok("Created web/store/folders.py")
    else:
        ok("web/store/folders.py already exists (skipped)")


def create_folders_api(base: Path) -> None:
    content = (
        '"""Folders API routes for organizing sessions."""\n\n'
        "from __future__ import annotations\n\n"
        "from datetime import UTC, datetime\n\n"
        "from fastapi import APIRouter, HTTPException, status\n"
        "from pydantic import BaseModel\n\n"
        "from kimi_cli.web.models import Folder, Session\n"
        "from kimi_cli.web.store.folders import (\n"
        "    create_folder as store_create_folder,\n"
        "    delete_folder as store_delete_folder,\n"
        "    get_folder as store_get_folder,\n"
        "    list_folders as store_list_folders,\n"
        "    update_folder as store_update_folder,\n"
        ")\n"
        "from kimi_cli.web.store.sessions import invalidate_sessions_cache\n\n"
        'router = APIRouter(prefix="/api/folders", tags=["folders"])\n\n\n'
        "class CreateFolderRequest(BaseModel):\n"
        '    """Create folder request."""\n\n'
        "    name: str\n\n\n"
        "class UpdateFolderRequest(BaseModel):\n"
        '    """Update folder request."""\n\n'
        "    name: str | None = None\n"
        "    sort_order: int | None = None\n\n\n"
        '@router.get("/", summary="List all folders")\n'
        "async def list_folders() -> list[Folder]:\n"
        '    """List all folders sorted by sort_order and created_at."""\n'
        "    folders = store_list_folders()\n"
        "    return [\n"
        "        Folder(\n"
        "            id=f.id,\n"
        "            name=f.name,\n"
        "            created_at=datetime.fromtimestamp(f.created_at, tz=UTC),\n"
        "            updated_at=datetime.fromtimestamp(f.updated_at, tz=UTC),\n"
        "            sort_order=f.sort_order,\n"
        "        )\n"
        "        for f in folders\n"
        "    ]\n\n\n"
        '@router.post("/", summary="Create a new folder", status_code=status.HTTP_201_CREATED)\n'
        "async def create_folder(request: CreateFolderRequest) -> Folder:\n"
        '    """Create a new folder for organizing sessions."""\n'
        "    folder = store_create_folder(request.name)\n"
        "    return Folder(\n"
        "        id=folder.id,\n"
        "        name=folder.name,\n"
        "        created_at=datetime.fromtimestamp(folder.created_at, tz=UTC),\n"
        "        updated_at=datetime.fromtimestamp(folder.updated_at, tz=UTC),\n"
        "        sort_order=folder.sort_order,\n"
        "    )\n\n\n"
        '@router.patch("/{folder_id}", summary="Update a folder")\n'
        "async def update_folder(folder_id: str, request: UpdateFolderRequest) -> Folder:\n"
        '    """Update folder name or sort_order."""\n'
        "    folder = store_update_folder(folder_id, name=request.name, sort_order=request.sort_order)\n"
        '    if folder is None:\n'
        '        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")\n'
        "    return Folder(\n"
        "        id=folder.id,\n"
        "        name=folder.name,\n"
        "        created_at=datetime.fromtimestamp(folder.created_at, tz=UTC),\n"
        "        updated_at=datetime.fromtimestamp(folder.updated_at, tz=UTC),\n"
        "        sort_order=folder.sort_order,\n"
        "    )\n\n\n"
        '@router.delete("/{folder_id}", summary="Delete a folder")\n'
        "async def delete_folder(folder_id: str) -> None:\n"
        '    """Delete a folder. Sessions in the folder become unfiled."""\n'
        "    # Clear folder_id from all sessions in this folder\n"
        "    from kimi_cli.session_state import load_session_state, save_session_state\n"
        "    from kimi_cli.web.store.sessions import _build_sessions_index\n\n"
        "    entries = _build_sessions_index()\n"
        "    for entry in entries:\n"
        "        if entry.state.folder_id == folder_id:\n"
        "            entry.state.folder_id = None\n"
        "            save_session_state(entry.state, entry.session_dir)\n\n"
        "    if not store_delete_folder(folder_id):\n"
        '        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")\n\n'
        "    invalidate_sessions_cache()\n\n\n"
        '@router.get("/{folder_id}/sessions", summary="List sessions in a folder")\n'
        "async def list_folder_sessions(folder_id: str) -> list[Session]:\n"
        '    """List all sessions that belong to a specific folder."""\n'
        "    from kimi_cli.web.store.sessions import load_sessions_page\n\n"
        "    if store_get_folder(folder_id) is None:\n"
        '        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")\n\n'
        "    return load_sessions_page(folder_id=folder_id, limit=500)\n"
    )
    path = base / "web" / "api" / "folders.py"
    if write_if_changed(path, content):
        ok("Created web/api/folders.py")
    else:
        ok("web/api/folders.py already exists (skipped)")


def copy_folders_html(base: Path) -> None:
    src = Path(__file__).parent / "static" / "folders.html"
    if not src.exists():
        fail(f"Cannot find {src}. Make sure you run install.py from the repo root.")
    dst = base / "web" / "static" / "folders.html"
    shutil.copy2(src, dst)
    ok("Copied static/folders.html")


def main() -> None:
    print("Kimi Web Folders Plugin Installer")
    print("=================================\n")

    base = find_kimi_cli()
    print(f"Detected kimi_cli at: {base}\n")

    patch_session_state(base)
    patch_web_models(base)
    patch_web_store_sessions(base)
    patch_web_api_sessions(base)
    patch_web_api_init(base)
    patch_web_app(base)
    patch_index_html(base)
    create_folders_store(base)
    create_folders_api(base)
    copy_folders_html(base)

    print("\n=================================")
    print("Done! Please restart 'kimi web' for changes to take effect.")
    print("=================================")


if __name__ == "__main__":
    main()
