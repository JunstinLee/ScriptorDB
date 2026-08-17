from __future__ import annotations

# Shared browser helpers live in tools/browser_common.py and are re-exported here
# for backward compatibility. All browser tool implementations live in
# tools/browser_tools/* and are re-exported here as a facade.
from tools.browser_common import (  # noqa: E402
    _check_blocked,
    _click_next,
    _require_browser,
    _settle_after_click,
)
from tools.browser_tools.cookies import (  # noqa: E402
    browser_clear_cookies,
    browser_get_cookies,
    browser_set_cookies,
)
from tools.browser_tools.dom import (  # noqa: E402
    browser_click,
    browser_evaluate,
    browser_fill,
    browser_get_text,
    browser_press_key,
    browser_query,
    browser_scroll,
    browser_wait_for_selector,
)
from tools.browser_tools.download import browser_download  # noqa: E402
from tools.browser_tools.filter_apply import browser_apply_filter  # noqa: E402
from tools.browser_tools.filter_detect import browser_detect_filters  # noqa: E402
from tools.browser_tools.inspect import browser_inspect_structure  # noqa: E402
from tools.browser_tools.links import browser_extract_links  # noqa: E402
from tools.browser_tools.navigation import (  # noqa: E402
    browser_get_url,
    browser_go_back,
    browser_go_forward,
    browser_launch,
    browser_load_state,
    browser_navigate,
)
from tools.browser_tools.table import browser_extract_rows, browser_extract_table  # noqa: E402
from tools.browser_tools.tabs import browser_get_tabs, browser_switch_tab  # noqa: E402
from tools.browser_tools.visual import browser_screenshot  # noqa: E402

__all__ = [
    "browser_apply_filter",
    "browser_clear_cookies",
    "browser_click",
    "browser_detect_filters",
    "browser_download",
    "browser_evaluate",
    "browser_extract_links",
    "browser_extract_rows",
    "browser_extract_table",
    "browser_fill",
    "browser_get_cookies",
    "browser_get_tabs",
    "browser_get_text",
    "browser_get_url",
    "browser_go_back",
    "browser_go_forward",
    "browser_inspect_structure",
    "browser_launch",
    "browser_load_state",
    "browser_navigate",
    "browser_press_key",
    "browser_query",
    "browser_screenshot",
    "browser_scroll",
    "browser_set_cookies",
    "browser_switch_tab",
    "browser_wait_for_selector",
]
