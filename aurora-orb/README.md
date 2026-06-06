# Aurora Orb

This is Aurora's permanent desktop UI.

Built with:

- Tauri
- React
- TypeScript
- React Three Fiber

## Status

### Verified

- `npm run build` works
- the orb connects to Aurora's local WebSocket bridge
- the orb receives backend state updates
- the orb can send text commands back to the Python backend using `user_command`

## Role In The System

The orb is now the supported GUI path for Aurora.

The Python backend still handles:

- LLM orchestration
- voice wake mode
- tool execution
- memory
- speech input and output

The orb is the visual shell and command surface on top of that backend.

## Launch

Use the root launcher: [Launch Aurora.bat](D:/Aurora/Launch%20Aurora.bat)

## Remaining Weak Spots

- backend architecture is still too concentrated in `main.py`
- some functionality depends on optional Windows automation/audio packages being installed
- the legacy PySide6/QML UI still exists in the repo as dead weight
