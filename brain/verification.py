import time
import psutil
from typing import Dict, Any, Tuple
from config.logging import logger
from brain.schemas import VerificationResult

class VerifierEngine:
    """
    Goal Verification Layer.
    Validates whether the intent of a tool call actually succeeded in the OS.
    """
    
    def verify(self, tool_name: str, args: Dict[str, Any], execution_result: str) -> VerificationResult:
        start_time = time.time()
        
        # If the execution itself returned a blatant traceback/error string, fail early.
        if "traceback" in execution_result.lower() or "error" in execution_result.lower() and "success" not in execution_result.lower():
            return VerificationResult(
                success=False,
                confidence=0.9,
                evidence=f"Tool execution returned an error string: {execution_result[:100]}...",
                verification_time=time.time() - start_time
            )
            
        # Dispatch to specific verification logic based on tool
        verify_method = getattr(self, f"_verify_{tool_name}", self._verify_default)
        
        try:
            result = verify_method(args, execution_result)
        except Exception as e:
            logger.error(f"Verification engine crashed during {tool_name} verification: {e}")
            result = VerificationResult(
                success=False,
                confidence=0.5,
                evidence=f"Verification logic crashed: {e}",
                verification_time=time.time() - start_time
            )
            
        result.verification_time = time.time() - start_time
        return result
        
    def _verify_default(self, args: Dict[str, Any], execution_result: str) -> VerificationResult:
        """Fallback for tools without custom verification logic."""
        return VerificationResult(
            success=True,
            confidence=0.5, # Low confidence because we couldn't explicitly verify OS state
            evidence="Default verification: assumed success based on lack of execution errors.",
            verification_time=0.0
        )
        
    def _verify_open_app(self, args: Dict[str, Any], execution_result: str) -> VerificationResult:
        app_name = args.get("app_name", "").lower().replace(".exe", "")
        
        # Some apps have different executable names than their common names
        aliases = {
            "chrome": ["chrome.exe"],
            "notepad": ["notepad.exe"],
            "vs code": ["code.exe"],
            "vscode": ["code.exe"],
            "spotify": ["spotify.exe"],
            "discord": ["discord.exe"],
            "explorer": ["explorer.exe"]
        }
        
        targets = aliases.get(app_name, [f"{app_name}.exe"])
        
        # Poll for up to 3 seconds to let the process start
        for _ in range(3):
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() in targets:
                        return VerificationResult(
                            success=True,
                            confidence=0.95,
                            evidence=f"Process '{proc.info['name']}' detected running in the OS.",
                            verification_time=0.0
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            time.sleep(1)
            
        return VerificationResult(
            success=False,
            confidence=0.8,
            evidence=f"Could not find any running process matching {targets} after 3 seconds.",
            verification_time=0.0
        )
        
verifier = VerifierEngine()
