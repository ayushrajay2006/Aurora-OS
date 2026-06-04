import webbrowser
import urllib.parse
from typing import Dict, Any, Optional
from tools.registry import registry, BaseTool
from config.logging import logger

# Friendly shortcuts mapping to absolute URLs
WEBSITE_ALIASES = {
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "leetcode": "https://leetcode.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "realpage": "https://www.realpage.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://www.wikipedia.org",
    "instagram": "https://www.instagram.com",
    "goindigo": "https://www.goindigo.in",
    "indigo": "https://www.goindigo.in",
    "irctc": "https://www.irctc.co.in",
    "flipkart": "https://www.flipkart.com"
}

@registry.register(
    name="open_website",
    description="Launches a website URL or searches Google. Can optionally target a specific browser if requested.",
    args_schema={
        "url": {
            "type": "string",
            "description": "The website URL, shortcut (e.g., youtube, gmail, leetcode), or a search query."
        },
        "browser": {
            "type": "string",
            "description": "Optional browser name to launch the website in (e.g., 'chrome', 'edge', 'firefox', 'brave'). If not specified, the system default browser will be used.",
            "enum": ["chrome", "edge", "firefox", "brave"]
        }
    },
    risk_level="medium"
)
class OpenWebsiteTool(BaseTool):
    def execute(self, url: str, browser: Optional[str] = None) -> dict:
        logger.info(f"Received request to open website or query: '{url}' in browser: '{browser}'")
        
        target_url = url.strip()
        app_name_clean = target_url.lower()
        
        # 1. Resolve Friendly Shortcut Aliases
        alias_key = app_name_clean.replace(" ", "").replace("-", "").replace(".", "").replace("com", "").replace("in", "").replace("org", "").replace("co", "")
        if alias_key in WEBSITE_ALIASES:
            target_url = WEBSITE_ALIASES[alias_key]
            logger.debug(f"Resolved friendly website shortcut: '{alias_key}' -> {target_url}")
            
        # 2. Check for absolute local paths or file URIs
        import os
        import pathlib
        if os.path.isabs(target_url) or target_url.startswith("\\\\"):
            target_url = pathlib.Path(target_url).as_uri()
            logger.info(f"Resolved absolute local path to file URI: {target_url}")
            
        elif target_url.startswith("file://"):
            # Local file protocol, keep as is
            logger.debug(f"Identified file URI: {target_url}")
            
        # 3. Check for absolute protocols (http, https)
        elif not target_url.startswith("http://") and not target_url.startswith("https://"):
            # If it contains a dot and no spaces, treat it as a domain (e.g. google.com)
            if "." in target_url and " " not in target_url:
                target_url = "https://" + target_url
                logger.debug(f"Prefixed domain with HTTPS: {target_url}")
            else:
                # 4. Google Search Fallback: Treat as a search query
                encoded_query = urllib.parse.quote(target_url)
                target_url = f"https://www.google.com/search?q={encoded_query}"
                logger.info(f"Treating non-URL query as Google Search: '{url}' -> {target_url}")
                
        # 4. Handle Specific Browser Launch
        if browser:
            browser_clean = browser.lower().strip()
            browser_map = {
                "edge": "edge",
                "microsoft edge": "edge",
                "chrome": "chrome",
                "google chrome": "chrome",
                "brave": "brave",
                "firefox": "firefox"
            }
            app_key = browser_map.get(browser_clean, browser_clean)
            
            from tools.open_app import search_common_paths, search_registry_app_paths, search_start_menu
            import subprocess
            import os
            
            resolved_path = search_common_paths(app_key)
            if not resolved_path:
                resolved_path = search_registry_app_paths(app_key)
            if not resolved_path:
                resolved_path = search_start_menu(app_key)
                
            if resolved_path:
                try:
                    if os.path.isabs(resolved_path):
                        subprocess.Popen([resolved_path, target_url])
                    else:
                        subprocess.Popen(f'start {resolved_path} "{target_url}"', shell=True)
                    logger.info(f"Successfully opened {target_url} in specific browser '{browser}'")
                    return {"success": True, "output": f"Successfully opened website in {browser}: {target_url}"}
                except Exception as e:
                    logger.warning(f"Failed to launch website in specific browser '{browser}': {e}. Falling back to default browser.")
            else:
                logger.warning(f"Could not resolve path for specific browser '{browser}'. Falling back to default browser.")
                
        try:
            # Open in user's default configured browser (Chrome, Brave, Edge, etc.)
            webbrowser.open(target_url)
            logger.info(f"Successfully opened website: {target_url}")
            return {"success": True, "output": f"Successfully opened website: {target_url}"}
        except Exception as e:
            msg = f"Failed to open website '{target_url}': {e}"
            logger.error(msg)
            return {"success": False, "output": msg}
