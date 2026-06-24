"""
EPMS Editor/IDE Activity Monitor.
Detects active editor windows across:
  - Visual Studio Code (Code.exe)
  - Visual Studio (devenv.exe)
  - Cursor (cursor.exe)
  - Windsurf (windsurf.exe)
  - PyCharm (pycharm64.exe)
  - IntelliJ IDEA (idea64.exe)
  - Android Studio (studio64.exe)
  - Eclipse (eclipse.exe)
  - Notepad++ (notepad++.exe)
  - Sublime Text (sublime_text.exe)

Extracts project name, file name, and session duration from window titles
and process metadata.
"""

import logging
import re
import os
from typing import Optional, Dict, Any, List, Pattern
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Editor/IDE detection patterns
# Each entry: process name, window title pattern, project/file extraction
EDITOR_PATTERNS: Dict[str, Dict[str, Any]] = {
    "Visual Studio Code": {
        "process_names": ["code.exe", "code", "code-insiders.exe", "code-oss.exe"],
        "title_pattern": re.compile(
            r"^(?:●\s*)?(?P<file>.*?)\s*[-–]\s*(?P<project>.*?)\s*[-–]\s*Visual Studio Code(?:\s*\(.*\))?$"
        ),
        "title_simple": re.compile(
            r"^(?:●\s*)?(?P<file>.*?)\s*[-–]\s*Visual Studio Code"
        ),
        "icon": "vscode",
        "category": "development",
    },
    "Visual Studio": {
        "process_names": ["devenv.exe", "devenv"],
        "title_pattern": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*(?P<project>.*?)\s*[-–]\s*(?:Microsoft\s+)?Visual Studio(?:\s*\(.*\))?$"
        ),
        "title_simple": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*(?:Microsoft\s+)?Visual Studio"
        ),
        "icon": "visualstudio",
        "category": "development",
    },
    "Cursor": {
        "process_names": ["cursor.exe", "cursor"],
        "title_pattern": re.compile(
            r"^(?:●\s*)?(?P<file>.*?)\s*[-–]\s*(?P<project>.*?)\s*[-–]\s*Cursor$"
        ),
        "title_simple": re.compile(
            r"^(?:●\s*)?(?P<file>.*?)\s*[-–]\s*Cursor"
        ),
        "icon": "cursor",
        "category": "development",
    },
    "Windsurf": {
        "process_names": ["windsurf.exe", "windsurf"],
        "title_pattern": re.compile(
            r"^(?:●\s*)?(?P<file>.*?)\s*[-–]\s*(?P<project>.*?)\s*[-–]\s*Windsurf$"
        ),
        "title_simple": re.compile(
            r"^(?:●\s*)?(?P<file>.*?)\s*[-–]\s*Windsurf"
        ),
        "icon": "windsurf",
        "category": "development",
    },
    "PyCharm": {
        "process_names": ["pycharm64.exe", "pycharm.exe", "pycharm", "charm.exe"],
        "title_pattern": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*(?P<project>.*?)\s*[-–]\s*(?:PyCharm\s+.*)$"
        ),
        "title_simple": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*PyCharm"
        ),
        "icon": "pycharm",
        "category": "development",
    },
    "IntelliJ IDEA": {
        "process_names": ["idea64.exe", "idea.exe", "idea"],
        "title_pattern": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*(?P<project>.*?)\s*[-–]\s*(?:IntelliJ\s+IDEA.*)$"
        ),
        "title_simple": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*(?:IntelliJ\s+IDEA)"
        ),
        "icon": "intellij",
        "category": "development",
    },
    "Android Studio": {
        "process_names": ["studio64.exe", "studio.exe", "android-studio", "androidstudio"],
        "title_pattern": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*(?P<project>.*?)\s*[-–]\s*(?:Android\s+Studio.*)$"
        ),
        "title_simple": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*(?:Android\s+Studio)"
        ),
        "icon": "androidstudio",
        "category": "development",
    },
    "Eclipse": {
        "process_names": ["eclipse.exe", "eclipse"],
        "title_pattern": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*(?P<project>.*?)\s*[-–]\s*Eclipse(?:\s+.*)?$"
        ),
        "title_simple": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*Eclipse"
        ),
        "icon": "eclipse",
        "category": "development",
    },
    "Notepad++": {
        "process_names": ["notepad++.exe", "notepad++"],
        "title_pattern": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*Notepad\+\+$"
        ),
        "title_simple": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*Notepad\+\+"
        ),
        "icon": "notepadplusplus",
        "category": "editing",
    },
    "Sublime Text": {
        "process_names": ["sublime_text.exe", "sublime_text", "subl.exe"],
        "title_pattern": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*(?P<project>.*?)\s*[-–]\s*Sublime Text(?:\s*\(.*\))?$"
        ),
        "title_simple": re.compile(
            r"^(?P<file>.*?)\s*[-–]\s*Sublime Text"
        ),
        "icon": "sublimetext",
        "category": "development",
    },
}

# File extensions mapped to programming languages
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    # Web
    ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".sass": "SASS", ".less": "LESS",
    # Scripting
    ".js": "JavaScript", ".jsx": "JSX", ".ts": "TypeScript", ".tsx": "TSX",
    ".py": "Python", ".rb": "Ruby", ".php": "PHP", ".pl": "Perl",
    ".sh": "Shell", ".bash": "Bash", ".ps1": "PowerShell",
    ".lua": "Lua", ".r": "R",
    # Compiled
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".cs": "C#", ".cpp": "C++", ".c": "C", ".h": "C/C++ Header",
    ".hpp": "C++ Header", ".go": "Go", ".rs": "Rust",
    ".swift": "Swift", ".scala": "Scala",
    # Data/Config
    ".json": "JSON", ".xml": "XML", ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML", ".ini": "INI", ".cfg": "Config",
    ".md": "Markdown", ".rst": "reStructuredText",
    ".sql": "SQL", ".graphql": "GraphQL",
    # Other
    ".dart": "Dart", ".ex": "Elixir", ".exs": "Elixir",
    ".clj": "Clojure", ".erl": "Erlang",
    ".vue": "Vue", ".svelte": "Svelte",
}


@dataclass
class EditorSessionInfo:
    """Information about an active editor session."""
    editor_name: str = ""
    editor_version: str = ""
    project_name: str = ""
    project_path: str = ""
    file_name: str = ""
    file_path: str = ""
    file_extension: str = ""
    language: str = ""
    line_count: int = 0
    is_focused: bool = True
    is_debugging: bool = False
    duration_seconds: float = 0.0
    session_start: str = ""
    timestamp: str = ""


def detect_editor_from_process(process_name: str) -> Optional[Dict[str, Any]]:
    """Detect which editor/IDE a process name belongs to."""
    if not process_name:
        return None
    proc_lower = process_name.lower()

    for editor_name, config in EDITOR_PATTERNS.items():
        for pn in config["process_names"]:
            if proc_lower == pn.lower() or proc_lower.endswith(os.sep + pn.lower()):
                return config
    return None


def is_editor_process(process_name: str) -> bool:
    """Check if a process name corresponds to a known editor/IDE."""
    return detect_editor_from_process(process_name) is not None


def get_file_extension(file_name: str) -> str:
    """Extract file extension from a file name."""
    if not file_name:
        return ""
    _, ext = os.path.splitext(file_name)
    return ext.lower()


def get_language_from_extension(extension: str) -> str:
    """Map a file extension to a programming language name."""
    return EXTENSION_LANGUAGE_MAP.get(extension.lower(), "")


def extract_project_from_path(path: str) -> str:
    """Extract project name from a file path."""
    if not path:
        return ""
    # Common project root indicators
    indicators = [".git", "src", "node_modules", "package.json", ".project", ".idea"]
    parts = path.replace("\\", "/").split("/")

    # Return the deepest directory that looks like a project
    for i, part in enumerate(parts):
        if part in (".git", ".idea", ".vscode"):
            if i > 0:
                return parts[i - 1]

    # Default: return the second-to-last meaningful directory
    meaningful = [p for p in parts if p and not p.startswith(".")]
    if meaningful:
        return meaningful[-1] if len(meaningful) == 1 else meaningful[-2]
    return ""


def parse_editor_window_title(window_title: str, process_name: str) -> EditorSessionInfo:
    """Parse an editor window title to extract file/project info."""
    info = EditorSessionInfo()

    editor_config = detect_editor_from_process(process_name)
    if not editor_config:
        return info

    # Find the editor name by matching process name
    for editor_name, config in EDITOR_PATTERNS.items():
        if config is editor_config:
            info.editor_name = editor_name
            break

    if not info.editor_name:
        return info

    # Try to match the full title pattern (file + project)
    match = editor_config["title_pattern"].search(window_title)
    if match:
        info.file_name = match.group("file").strip()
        if "project" in match.groupdict():
            info.project_name = match.group("project").strip()

    # Fallback: try the simple pattern
    if not info.file_name:
        match = editor_config["title_simple"].search(window_title)
        if match:
            info.file_name = match.group("file").strip()

    # Clean up file name (remove leading dots from modified indicators)
    if info.file_name:
        info.file_name = re.sub(r'^[●○●]\s*', '', info.file_name).strip()
        info.file_extension = get_file_extension(info.file_name)
        info.language = get_language_from_extension(info.file_extension)

    # Extract project from path if we have it
    if not info.project_name and info.file_name:
        # Try to get project from the window title itself
        project_match = re.search(r'\(([^)]+)\)', window_title)
        if project_match:
            info.project_name = project_match.group(1)

    # Set timestamp
    info.timestamp = datetime.now(timezone.utc).isoformat()

    return info


def get_editor_activity_data(window_title: str, process_name: str) -> Dict[str, Any]:
    """Get structured editor activity data for API transmission."""
    session_info = parse_editor_window_title(window_title, process_name)

    return {
        "timestamp": session_info.timestamp,
        "editor_name": session_info.editor_name,
        "editor_version": session_info.editor_version,
        "project_name": session_info.project_name,
        "file_name": session_info.file_name,
        "file_extension": session_info.file_extension,
        "language": session_info.language,
        "is_focused": session_info.is_focused,
        "is_debugging": session_info.is_debugging,
    }


# List of all supported editors for reference
SUPPORTED_EDITORS = [
    "Visual Studio Code",
    "Visual Studio",
    "Cursor",
    "Windsurf",
    "PyCharm",
    "IntelliJ IDEA",
    "Android Studio",
    "Eclipse",
    "Notepad++",
    "Sublime Text",
]
