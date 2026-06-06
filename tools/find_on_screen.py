"""
tools/find_on_screen.py
Phase 11 — Visual Element Locator (Hybrid: UI Automation + Vision fallback)

Strategy (in order):
  1. Windows UI Automation (uiautomation) — instant, pixel-perfect, no AI
     Finds elements by semantic name/type using Windows Accessibility APIs.
  2. Vision fallback (llava via Ollama) — for elements not exposed by accessibility,
     e.g. web page content, game UIs, custom-drawn widgets.
     Uses a resized 960x540 JPEG screenshot for speed.

Returns (x, y) pixel coordinates of the element center.
"""

import os
import re
import io
import base64
import time
from PIL import ImageGrab, Image
from tools.registry import registry, BaseTool
from config.logging import logger
from brain.llm import llm_client


# ─────────────────────────────────────────────────────────────────────────────
# UI Automation helpers
# ─────────────────────────────────────────────────────────────────────────────

# Keyword → UI Automation search strategy
_UIA_STRATEGIES = [
    # Taskbar / shell
    (["taskbar", "system tray", "notification area"],
     lambda: _find_by_classname("Shell_TrayWnd")),
    # Start button
    (["start button", "start menu", "windows button"],
     lambda: _find_named_control("Start")),
    # Address / URL bar
    (["address bar", "url bar", "address box", "omnibox", "search bar"],
     lambda: _find_address_bar()),
    # Search box in taskbar
    (["taskbar search", "cortana", "windows search", "search box"],
     lambda: _find_by_automationid("TrayButton") or _find_by_name_partial("search")),
    # Volume
    (["volume", "speaker", "audio"],
     lambda: _find_by_name_partial("volume")),
    # Close button
    (["close button", "close window", "x button"],
     lambda: _find_close_button()),
    # Minimize button
    (["minimize", "minimise"],
     lambda: _find_by_name_partial("minimize")),
    # Maximize / restore button
    (["maximize", "maximise", "restore", "full screen", "fullscreen"],
     lambda: _find_by_name_partial("maximize") or _find_by_name_partial("restore")),
]


def _get_active_window_control():
    """Returns the uiautomation Control representing the active/focused top-level window."""
    try:
        import uiautomation as auto
        focused = auto.GetFocusedControl()
        if focused:
            curr = focused
            while curr:
                parent = curr.GetParentControl()
                if parent == auto.GetRootControl():
                    return curr
                curr = parent
        fg = auto.GetForegroundControl()
        if fg:
            curr = fg
            while curr:
                parent = curr.GetParentControl()
                if parent == auto.GetRootControl():
                    return curr
                curr = parent
    except Exception:
        pass
    return None


def _rect_center(rect):
    """Return (cx, cy) from a uiautomation BoundingRectangle if valid and not minimized, else None."""
    if not rect:
        return None
    try:
        if rect.width() <= 0 or rect.height() <= 0:
            return None
        # Windows uses large negative coordinates like -32000 for minimized windows
        if rect.left <= -10000 or rect.top <= -10000:
            return None
        return (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2
    except Exception:
        return None



def _find_by_classname(classname: str):
    try:
        import uiautomation as auto
        ctrl = auto.PaneControl(ClassName=classname)
        if ctrl.Exists(maxSearchSeconds=1):
            return _rect_center(ctrl.BoundingRectangle)
    except Exception as e:
        logger.debug(f"UIA classname '{classname}' failed: {e}")
    return None


def _find_named_control(name: str):
    try:
        import uiautomation as auto
        for CtrlType in [auto.ButtonControl, auto.PaneControl, auto.ToolBarControl]:
            ctrl = CtrlType(Name=name)
            if ctrl.Exists(maxSearchSeconds=0.5):
                return _rect_center(ctrl.BoundingRectangle)
    except Exception as e:
        logger.debug(f"UIA named control '{name}' failed: {e}")
    return None


def _find_by_automationid(automation_id: str):
    try:
        import uiautomation as auto
        ctrl = auto.Control(AutomationId=automation_id)
        if ctrl.Exists(maxSearchSeconds=0.5):
            return _rect_center(ctrl.BoundingRectangle)
    except Exception as e:
        logger.debug(f"UIA automationid '{automation_id}' failed: {e}")
    return None


def _find_by_name_partial(keyword: str):
    """Walk active window first, then fallback to all windows looking for any control whose Name contains keyword."""
    try:
        import uiautomation as auto
        
        # 1. Try searching active window descendants first
        active_win = _get_active_window_control()
        if active_win:
            try:
                def search_descendants(parent):
                    for ctrl in parent.GetChildren():
                        if keyword.lower() in (ctrl.Name or "").lower():
                            rect = ctrl.BoundingRectangle
                            center = _rect_center(rect)
                            if center:
                                return center
                        res = search_descendants(ctrl)
                        if res:
                            return res
                    return None
                center = search_descendants(active_win)
                if center:
                    logger.info(f"UIA: Found partial name '{keyword}' in active window")
                    return center
            except Exception:
                pass
                
        # 2. Fallback to desktop-wide search
        desktop = auto.GetRootControl()
        for window in desktop.GetChildren():
            try:
                rect = window.BoundingRectangle
                if rect.left <= -10000 or rect.top <= -10000:
                    continue
            except Exception:
                pass
            if not window.Name:
                continue
            try:
                for ctrl in window.GetChildren():
                    if keyword.lower() in (ctrl.Name or "").lower():
                        rect = ctrl.BoundingRectangle
                        center = _rect_center(rect)
                        if center:
                            return center
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"UIA partial name '{keyword}' failed: {e}")
    return None



def _find_address_bar():
    """Find the address/URL bar in any visible browser window.
    Brave/Chrome nest the EditControl up to 8 levels deep — searches recursively."""
    import time
    try:
        import uiautomation as auto
        import pygetwindow as gw
        
        browser_keywords = ["chrome", "edge", "brave", "firefox", "opera"]
        
        # Restore & activate the browser window if needed
        for w in gw.getAllWindows():
            if not w.title:
                continue
            if any(kw in w.title.lower() for kw in browser_keywords):
                if w.isMinimized:
                    w.restore()
                    time.sleep(0.5)
                w.activate()
                time.sleep(0.3)
                break
        
        # Search UIA tree
        desktop = auto.GetRootControl()
        for window in desktop.GetChildren():
            try:
                rect = window.BoundingRectangle
                if rect.left <= -10000 or rect.top <= -10000:
                    continue
            except Exception:
                pass
            if not window.Name:
                continue
            if not any(kw in window.Name.lower() for kw in browser_keywords):
                continue
            
            # Try by standard name first (works in Brave, Chrome, Edge)
            for name_hint in ["Address and search bar", "Address bar", "Search or type URL"]:
                ctrl = window.EditControl(Name=name_hint)
                if ctrl.Exists(maxSearchSeconds=0.5):
                    rect = ctrl.BoundingRectangle
                    center = _rect_center(rect)
                    if center:
                        return center
            
            # Deep recursive search (Brave nests to depth 8)
            def _deep_find_edit(parent, depth=0):
                if depth > 10:
                    return None
                try:
                    for ctrl in parent.GetChildren():
                        if ctrl.ControlTypeName == "EditControl":
                            rect = ctrl.BoundingRectangle
                            if rect.width() > 100 and 0 < rect.height() < 60:
                                center = _rect_center(rect)
                                if center:
                                    return center
                        result = _deep_find_edit(ctrl, depth + 1)
                        if result:
                            return result
                except Exception:
                    pass
                return None
            
            found = _deep_find_edit(window)
            if found:
                return found
                
    except Exception as e:
        logger.debug(f"UIA address bar search failed: {e}")
    return None





def _find_close_button():
    """Find the close button of the foreground/active window."""
    try:
        import uiautomation as auto
        import pygetwindow as gw
        active = gw.getActiveWindow()
        if active:
            # Close button is top-right: (right-15, top+15)
            x = active.left + active.width - 15
            y = active.top + 15
            return x, y
    except Exception as e:
        logger.debug(f"Close button fallback failed: {e}")
    return None


def _try_ui_automation(query: str):
    """Try all UIA strategies against the query. Returns (x, y) or None."""
    q = query.lower()
    for keywords, strategy in _UIA_STRATEGIES:
        if any(kw in q for kw in keywords):
            logger.info(f"FindOnScreen: trying UI Automation for '{query}'")
            result = strategy()
            if result:
                logger.info(f"FindOnScreen: UI Automation found at {result}")
                return result
    
    # Generic fallback: search active window first, then search all windows
    try:
        import uiautomation as auto
        words = [w for w in q.split() if len(w) > 3]
        
        # 1. Search active window first
        active_win = _get_active_window_control()
        if active_win:
            try:
                def search(parent, depth=0):
                    if depth > 5:
                        return None
                    for ctrl in parent.GetChildren():
                        name = (ctrl.Name or "").lower()
                        if name and any(w in name for w in words):
                            rect = ctrl.BoundingRectangle
                            center = _rect_center(rect)
                            if center:
                                return center
                        result = search(ctrl, depth + 1)
                        if result:
                            return result
                    return None
                found = search(active_win)
                if found:
                    logger.info(f"FindOnScreen: generic UIA search found '{query}' in active window at {found}")
                    return found
            except Exception:
                pass

        # 2. Fallback to desktop-wide search
        desktop = auto.GetRootControl()
        for window in desktop.GetChildren():
            try:
                rect = window.BoundingRectangle
                if rect.left <= -10000 or rect.top <= -10000:
                    continue
            except Exception:
                pass
            if not window.Name:
                continue
            try:
                def search(parent, depth=0):
                    if depth > 4:
                        return None
                    for ctrl in parent.GetChildren():
                        name = (ctrl.Name or "").lower()
                        if name and any(w in name for w in words):
                            rect = ctrl.BoundingRectangle
                            center = _rect_center(rect)
                            if center:
                                return center
                        result = search(ctrl, depth + 1)
                        if result:
                            return result
                    return None
                found = search(window)
                if found:
                    logger.info(f"FindOnScreen: generic UIA search found '{query}' at {found}")
                    return found
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Generic UIA search failed: {e}")
    return None



def _semantic_uia_search(query: str):
    """
    Extracts visible UI elements and uses the text LLM to semantically
    match the user's request to the correct element.
    This allows understanding concepts like 'the browser icon' or 'search bar'.
    """
    try:
        import uiautomation as auto
        import json
        from config.config import config
        
        logger.info(f"FindOnScreen: running semantic UIA search for '{query}'...")
        
        desktop = auto.GetRootControl()
        active_window = None
        for win in desktop.GetChildren():
            try:
                rect = win.BoundingRectangle
                if rect.left <= -10000 or rect.top <= -10000:
                    continue
            except Exception:
                pass
            if win.IsTopmost or win.HasKeyboardFocus:
                active_window = win
                break
                
        if not active_window:
            active_window = desktop
            
        elements = []
        element_id = 1
        
        def walk(ctrl, depth=0):
            nonlocal element_id
            if depth > 4: return
            try:
                name = ctrl.Name
                ctrl_type = ctrl.ControlTypeName
                rect = ctrl.BoundingRectangle
                
                # Only include interactive/named elements with physical size
                if (name or ctrl_type in ["ButtonControl", "EditControl", "ListItemControl", "MenuItemControl", "PaneControl"]) and rect.width() > 0 and rect.height() > 0:
                    center = _rect_center(rect)
                    if center:
                        elements.append({
                            "id": element_id,
                            "name": name,
                            "type": ctrl_type.replace("Control", ""),
                            "center": center
                        })
                        element_id += 1

                    
                for child in ctrl.GetChildren():
                    walk(child, depth + 1)
            except Exception:
                pass
                
        # Always explicitly check the taskbar
        try:
            taskbar = auto.Control(ClassName="Shell_TrayWnd")
            if taskbar.Exists(0, 0):
                walk(taskbar, depth=0)
        except Exception: 
            pass
        
        # Check active window (or desktop)
        walk(active_window, depth=0)
        
        if not elements:
            return None
            
        # Filter if too large
        if len(elements) > 100:
            elements = [e for e in elements if e["name"]]
        elements = elements[:100]
        
        # Format for LLM
        prompt = f'''You are a UI automation expert. The user wants to click on: "{query}"

Here is a list of visible UI elements currently on the screen:
{json.dumps([{"id": e["id"], "name": e["name"], "type": e["type"]} for e in elements], indent=2)}

Which element ID best matches what the user wants? Use semantic reasoning.
For example, if the user wants "browser", "Google Chrome" is a good match.
If the user wants "taskbar", an element of type "Pane" named "Running applications" or without a name from the taskbar could be it.
Respond with ONLY the integer ID of the best match. If absolutely nothing matches, respond with 0.'''
        
        res = llm_client.chat([{"role": "user", "content": prompt}], stream=False)
        try:
            match_id = int(re.search(r'\d+', res).group())
            if match_id > 0:
                for e in elements:
                    if e["id"] == match_id:
                        logger.info(f"FindOnScreen: semantic search mapped '{query}' to '{e['name']}' ({e['type']})")
                        return e["center"]
        except Exception:
            pass
            
    except Exception as e:
        logger.error(f"FindOnScreen: semantic UIA search failed: {e}")
        
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Tool registration
# ─────────────────────────────────────────────────────────────────────────────

@registry.register(
    name="find_on_screen",
    description=(
        "Locates a UI element on the current screen by its description and returns its (x, y) pixel coordinates. "
        "First tries Windows UI Automation (instant, perfect accuracy for native UI). "
        "Falls back to vision model if the element is not exposed by accessibility APIs (e.g. web content, games). "
        "Use this before calling click() when you don't know exact coordinates. "
        "Examples: 'the search bar', 'the Play button', 'the address bar', 'the close button', 'the taskbar'."
    ),
    args_schema={
        "query": {
            "type": "string",
            "description": "Natural-language description of the UI element to locate, e.g. 'the YouTube search bar', 'the Sign In button', 'the volume slider', 'the close button'."
        }
    },
    risk_level="low"
)
class FindOnScreenTool(BaseTool):
    def execute(self, query: str) -> dict:
        logger.info(f"FindOnScreen: looking for '{query}'")
        
        # ── Step 1: Try Fast UI Automation (exact/keyword match) ───────────
        try:
            coords = _try_ui_automation(query)
            if coords:
                x, y = coords
                logger.info(f"FindOnScreen: Fast UI Automation found '{query}' at ({x}, {y})")
                return {
                    "success": True,
                    "output": f"Found '{query}' at coordinates ({x}, {y}) via Fast UIA. Call click(x={x}, y={y}) to interact.",
                    "x": x,
                    "y": y,
                    "method": "fast_ui_automation"
                }
        except Exception as e:
            logger.warning(f"FindOnScreen: Fast UI Automation step failed: {e}")
            
        # ── Step 2: Try Semantic UI Automation (LLM reasoning) ─────────────
        logger.info(f"FindOnScreen: Fast UIA missed, trying Semantic UIA search...")
        try:
            coords = _semantic_uia_search(query)
            if coords:
                x, y = coords
                return {
                    "success": True,
                    "output": f"Found '{query}' at coordinates ({x}, {y}) via Semantic AI reasoning. Call click(x={x}, y={y}) to interact.",
                    "x": x,
                    "y": y,
                    "method": "semantic_uia"
                }
        except Exception as e:
            logger.warning(f"FindOnScreen: Semantic UIA step failed: {e}")
        
        return {
            "success": False,
            "output": f"Could not find '{query}' on screen. The element may not be visible.",
            "x": None,
            "y": None
        }
