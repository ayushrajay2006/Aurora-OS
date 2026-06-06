import { useState, useRef, KeyboardEvent } from 'react'
import { getCurrentWindow } from '@tauri-apps/api/window'
import { useOrbStore, STATE_CONFIG } from '../state/orbStore'

const WS_COMMAND_URL = 'ws://localhost:8765'

export function InputOverlay() {
  const [expanded, setExpanded] = useState(false)
  const [text, setText] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const currentState = useOrbStore(s => s.currentState)
  const connected = useOrbStore(s => s.connected)
  const statusLabel = useOrbStore(s => s.statusLabel)

  const cfg = STATE_CONFIG[currentState]

  const handleOrbClick = () => {
    setExpanded(prev => !prev)
    if (!expanded) {
      setTimeout(() => inputRef.current?.focus(), 150)
    }
  }

  const handlePointerDown = (e: React.PointerEvent) => {
    if (e.button === 0) {
      getCurrentWindow().startDragging()
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && text.trim()) {
      // Send command via a separate WebSocket message
      try {
        const ws = new WebSocket(WS_COMMAND_URL)
        ws.onopen = () => {
          ws.send(JSON.stringify({ event: 'user_command', payload: { text: text.trim() } }))
          ws.close()
        }
      } catch {}
      setText('')
      setExpanded(false)
    }
    if (e.key === 'Escape') {
      setExpanded(false)
      setText('')
    }
  }

  return (
    <>
      {/* Invisible orb click zone */}
      <div
        onClick={handleOrbClick}
        onPointerDown={handlePointerDown}
        style={{
          position: 'absolute',
          inset: 0,
          cursor: 'pointer',
          zIndex: 1,
          background: 'transparent',
        }}
      />

      {/* Status label */}
      <div style={{
        position: 'absolute',
        top: 18,
        left: 0,
        right: 0,
        textAlign: 'center',
        color: cfg.colors.core,
        fontFamily: '"Segoe UI", system-ui, sans-serif',
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        opacity: 0.7,
        zIndex: 10,
        pointerEvents: 'none',
        textShadow: `0 0 12px ${cfg.colors.glow}`,
        transition: 'color 0.6s ease',
      }}>
        {connected ? statusLabel : 'Connecting...'}
      </div>

      {/* Connection dot */}
      <div style={{
        position: 'absolute',
        top: 18,
        right: 24,
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: connected ? '#34d399' : '#475569',
        boxShadow: connected ? '0 0 8px #34d399' : 'none',
        zIndex: 10,
        pointerEvents: 'none',
        transition: 'background 0.3s',
      }} />

      {/* Expandable text input panel */}
      <div style={{
        position: 'absolute',
        bottom: 24,
        left: '50%',
        width: 320,
        opacity: expanded ? 1 : 0,
        transform: expanded
          ? 'translateX(-50%) translateY(0)'
          : 'translateX(-50%) translateY(8px)',
        transition: 'opacity 0.2s ease, transform 0.2s ease',
        pointerEvents: expanded ? 'all' : 'none',
        zIndex: 20,
      }}>
        <div style={{
          background: 'rgba(10, 14, 26, 0.88)',
          border: `1px solid ${cfg.colors.core}40`,
          borderRadius: 14,
          padding: '10px 16px',
          backdropFilter: 'blur(12px)',
          boxShadow: `0 0 24px ${cfg.colors.glow}60, 0 4px 24px rgba(0,0,0,0.6)`,
        }}>
          <input
            ref={inputRef}
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command and press Enter..."
            style={{
              width: '100%',
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: '#f1f5f9',
              fontFamily: '"Segoe UI", system-ui, sans-serif',
              fontSize: 13,
              caretColor: cfg.colors.core,
            }}
          />
        </div>
        <div style={{
          textAlign: 'center',
          marginTop: 6,
          color: '#64748b',
          fontSize: 10,
          fontFamily: 'monospace',
        }}>
          Enter to send · Esc to close
        </div>
      </div>
    </>
  )
}
