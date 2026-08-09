"""Git diff parsing utilities for CodeLens."""

from dataclasses import dataclass
import re
from typing import List, Optional


@dataclass(frozen=True)
class ChangedRange:
    """A contiguous range of changed lines in the new file."""

    start_line: int
    end_line: int


@dataclass(frozen=True)
class ChangedFile:
    """A file affected by a Git diff."""

    file_path: str
    ranges: tuple[ChangedRange, ...]
    is_deleted: bool = False


_HUNK_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


def parse_git_diff(diff_text: str) -> List[ChangedFile]:
    """Parse unified Git diff text into changed new-file line ranges.

    Only lines that exist in the new version are represented. Therefore,
    deletion-only hunks produce a ChangedFile with an empty range tuple.
    """
    changed_files: List[ChangedFile] = []

    current_path: Optional[str] = None
    current_ranges: List[ChangedRange] = []
    current_deleted = False

    def finish_file() -> None:
        if current_path is None:
            return

        changed_files.append(
            ChangedFile(
                file_path=current_path,
                ranges=tuple(current_ranges),
                is_deleted=current_deleted,
            )
        )

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            finish_file()

            parts = line.split(" ", 3)
            current_path = None
            current_ranges = []
            current_deleted = False

            if len(parts) == 4:
                path_part = parts[3]
                if path_part.startswith("b/"):
                    current_path = path_part[2:]

        elif line.startswith("+++ "):
            path = line[4:]
            if path == "/dev/null":
                current_deleted = True
            elif path.startswith("b/"):
                current_path = path[2:]

        elif line.startswith("deleted file mode"):
            current_deleted = True

        elif line.startswith("@@ ") and current_path is not None:
            match = _HUNK_RE.match(line)
            if match is None:
                continue

            new_start = int(match.group("new_start"))
            new_count = int(match.group("new_count") or "1")

            if new_count > 0:
                current_ranges.append(
                    ChangedRange(
                        start_line=new_start,
                        end_line=new_start + new_count - 1,
                    )
                )

    finish_file()

    return changed_files
