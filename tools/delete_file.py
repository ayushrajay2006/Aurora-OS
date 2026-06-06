import os
import shutil
from tools.registry import registry, BaseTool
from config.logging import logger

# ─── Protected path prefixes ─────────────────────────────────────────────────
# Deletion is silently blocked for anything inside these directories,
# regardless of what the LLM requests. This prevents hallucinated paths from
# wiping system directories or the Aurora installation itself.

_AURORA_ROOT = os.path.normpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_BLOCKED_PREFIXES = [
    os.path.normpath("C:\\Windows"),
    os.path.normpath("C:\\Program Files"),
    os.path.normpath("C:\\Program Files (x86)"),
    os.path.normpath("C:\\ProgramData"),
    os.path.normpath("C:\\System Volume Information"),
    _AURORA_ROOT,  # Never delete Aurora's own directory
]

# Also block paths shorter than a meaningful depth (e.g. C:\, D:\) to prevent
# accidental root-level deletions.
_MIN_PATH_DEPTH = 3  # At least 3 path components: drive + dir + filename


def _is_path_blocked(path: str) -> tuple[bool, str]:
    """Return (blocked, reason) for the given absolute path."""
    norm = os.path.normpath(path)

    # Block root-level paths (too short)
    parts = norm.replace("/", "\\").split("\\")
    if len(parts) < _MIN_PATH_DEPTH:
        return True, f"Refusing to delete root-level path '{norm}' (too shallow — minimum depth is {_MIN_PATH_DEPTH})."

    # Block protected prefixes
    for blocked in _BLOCKED_PREFIXES:
        if norm.lower().startswith(blocked.lower()):
            if norm.lower() == blocked.lower():
                label = "Aurora root" if blocked == _AURORA_ROOT else "system directory"
            else:
                label = "Aurora installation" if blocked == _AURORA_ROOT else "system directory"
            return True, (
                f"Refusing to delete '{norm}' — it is inside a protected {label} "
                f"('{blocked}'). This action was blocked for safety."
            )

    return False, ""


@registry.register(
    name="delete_file",
    description=(
        "Deletes a file or folder at the specified absolute path. "
        "System directories, Aurora's own installation, and root-level paths are protected and cannot be deleted. "
        "Always confirm the exact path before calling this tool."
    ),
    args_schema={
        "path": {
            "type": "string",
            "description": "Absolute path to the file or directory/folder to delete."
        }
    },
    risk_level="critical"
)
class DeleteFileTool(BaseTool):
    def execute(self, path: str) -> dict:
        logger.info(f"Received request to delete path: '{path}'")

        target_path = os.path.abspath(path.strip())

        # Safety check before anything else
        blocked, reason = _is_path_blocked(target_path)
        if blocked:
            logger.warning(f"DeleteFile: BLOCKED — {reason}")
            return {"success": False, "output": reason}

        if not os.path.exists(target_path):
            msg = f"Path '{target_path}' does not exist."
            logger.error(msg)
            return {"success": False, "output": msg}

        try:
            if os.path.isdir(target_path):
                shutil.rmtree(target_path)
                msg = f"Successfully deleted directory and all its contents: '{target_path}'"
            else:
                os.remove(target_path)
                msg = f"Successfully deleted file: '{target_path}'"

            logger.info(msg)
            return {"success": True, "output": msg}
        except Exception as e:
            msg = f"Failed to delete '{target_path}': {e}"
            logger.error(msg)
            return {"success": False, "output": msg}
