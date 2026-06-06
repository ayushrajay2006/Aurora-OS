# Aurora

Aurora is a Windows desktop assistant project with a Python backend and a Tauri orb frontend.

The permanent supported interface is now the Tauri orb launched by [Launch Aurora.bat](D:/Aurora/Launch%20Aurora.bat).

## Supported UI

- Permanent UI: Tauri orb in [aurora-orb](D:/Aurora/aurora-orb)
- Legacy UI: old PySide6/QML path still exists in code, but it is no longer the primary interface

## Current Launch Path

Use [Launch Aurora.bat](D:/Aurora/Launch%20Aurora.bat).

That launcher now starts `main.py`, and `main.py` defaults to the Tauri orb path unless `--gui` is explicitly passed for the legacy UI.

## What Works Now

- Aurora starts in the Tauri orb path by default
- the WebSocket bridge broadcasts backend state to the orb
- the orb can send text commands back to Aurora using inbound `user_command` messages
- voice wake mode, backend planning, tool execution, and TTS/STT continue to run through the Python backend
- the orb frontend build works with `npm run build`

## What Still Matters

This is closer to a real Jarvis-style shell, but it is still not magically complete.

Important realities:

- the backend remains heavily concentrated in `main.py`
- missing Python packages will still disable related features until installed
- some tools depend on Windows-specific automation libraries and local model/runtime setup
- the legacy UI code is still present, even though the orb is now the supported path

## Required Python Dependencies

The current backend expects more than the original requirements list.

Notable runtime dependencies now include:

- `pyautogui`
- `pyperclip`
- `PyGetWindow`
- `SpeechRecognition`
- `pyttsx3`
- `PyAudio`
- `websockets`

Install from [requirements.txt](D:/Aurora/requirements.txt).

## Recommended Usage

1. Install Python dependencies from [requirements.txt](D:/Aurora/requirements.txt).
2. Build the orb frontend in [aurora-orb](D:/Aurora/aurora-orb) if needed.
3. Launch Aurora with [Launch Aurora.bat](D:/Aurora/Launch%20Aurora.bat).

## Project Direction

The chosen product direction is now:

- Python backend for agent logic, voice, memory, and tools
- Tauri orb as the permanent desktop UI

The old PySide6/QML interface is no longer the main path and should be treated as legacy.
