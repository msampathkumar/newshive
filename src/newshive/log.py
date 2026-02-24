"""
Centralized colored logging for News Hive.

Each module gets a distinct color. RED is reserved for warnings and errors only.
Colors can be disabled globally via the NO_COLOR=1 env var or by passing use_color=False.
"""
import os
import logging
from datetime import datetime, timezone

# ANSI color codes
_COLORS = {
    "cyan":    "\033[96m",
    "blue":    "\033[94m",
    "magenta": "\033[95m",
    "green":   "\033[92m",
    "yellow":  "\033[93m",
    "red":     "\033[91m",
    "dim":     "\033[2m",
    "bold":    "\033[1m",
    "reset":   "\033[0m",
}

# Per-module color assignments
MODULE_COLORS: dict[str, str] = {
    "article_discoverer": "cyan",
    "storage":            "blue",
    "metadata_manager":   "magenta",
    "task_orchestrator":  "green",
    "content_processor":  "yellow",
    "cli":                "cyan",
}

# Log levels
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR

# Global level — can be changed at startup
_current_level: int = INFO

# Global color toggle — reads NO_COLOR env var by default
_use_color: bool = os.environ.get("NO_COLOR", "").strip() == ""


def set_level(level: int) -> None:
    """Set global log level (log.DEBUG or log.INFO)."""
    global _current_level
    _current_level = level


def set_color(enabled: bool) -> None:
    """Enable or disable ANSI color output globally."""
    global _use_color
    _use_color = enabled


def _colorize(text: str, color_name: str) -> str:
    if not _use_color:
        return text
    code = _COLORS.get(color_name, "")
    reset = _COLORS["reset"]
    return f"{code}{text}{reset}"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


class ColorLogger:
    """
    Lightweight colored logger tied to a named module.

    Usage:
        from newshive.log import ColorLogger
        log = ColorLogger("crawler")
        log.info("Fetching index page")
        log.debug("→ enter fetch_index_page(url='https://...')")
    """

    def __init__(self, module: str, use_color: bool | None = None):
        self.module = module
        self._color = MODULE_COLORS.get(module, "cyan")
        # None means inherit global setting
        self._use_color_override = use_color

    def _should_color(self) -> bool:
        if self._use_color_override is not None:
            return self._use_color_override
        return _use_color

    def _format(self, level_label: str, msg: str, color_name: str) -> str:
        ts = _timestamp()
        use = self._should_color()

        if use:
            ts_str    = _colorize(ts, "dim")
            mod_str   = _colorize(f"[{self.module.upper()}]", self._color)
            level_str = _colorize(f"{level_label:<7}", color_name)
        else:
            ts_str    = ts
            mod_str   = f"[{self.module.upper()}]"
            level_str = f"{level_label:<7}"

        return f"{ts_str} {mod_str} {level_str} {msg}"

    def debug(self, msg: str) -> None:
        if _current_level <= DEBUG:
            line = self._format("DEBUG", msg, "dim")
            print(line)

    def info(self, msg: str) -> None:
        if _current_level <= INFO:
            line = self._format("INFO", msg, self._color)
            print(line)

    def success(self, msg: str) -> None:
        """Info-level but always displayed in green to signal completion."""
        if _current_level <= INFO:
            use = self._should_color()
            ts = _timestamp()
            ts_str    = _colorize(ts, "dim") if use else ts
            mod_str   = _colorize(f"[{self.module.upper()}]", self._color) if use else f"[{self.module.upper()}]"
            check     = _colorize("✔ SUCCESS", "green") if use else "SUCCESS"
            print(f"{ts_str} {mod_str} {check} {msg}")

    def warning(self, msg: str) -> None:
        # Always RED, always shown
        line = self._format("WARNING", f"⚠  {msg}", "red")
        print(line)

    def error(self, msg: str) -> None:
        # Always RED, always shown
        line = self._format("ERROR", f"✖  {msg}", "red")
        print(line)

    def step(self, n: int, total: int, msg: str) -> None:
        """Progress indicator: [2/5] message."""
        if _current_level <= INFO:
            use = self._should_color()
            counter = f"[{n}/{total}]"
            if use:
                counter = _colorize(counter, self._color)
            print(f"  {counter} {msg}")
