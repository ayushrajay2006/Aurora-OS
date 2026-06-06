import { useEffect, useRef } from 'react'
import { useOrbStore } from '../state/orbStore'

const WS_URL = 'ws://localhost:8765'
const RECONNECT_DELAY = 2000

export function useAuroraSocket() {
  const setState = useOrbStore(s => s.setState)
  const setAmplitude = useOrbStore(s => s.setAmplitude)
  const setProgress = useOrbStore(s => s.setProgress)
  const setConnected = useOrbStore(s => s.setConnected)
  const setLastError = useOrbStore(s => s.setLastError)
  const setConfidence = useOrbStore(s => s.setConfidence)
  const triggerMemoryFlash = useOrbStore(s => s.triggerMemoryFlash)
  const mergeSnapshot = useOrbStore(s => s.mergeSnapshot)
  const appendEvent = useOrbStore(s => s.appendEvent)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        setLastError(null)
        console.log('[Aurora WS] Connected')
        // Request hybrid snapshot
        ws.send(JSON.stringify({ event: 'get_diagnostics' }))
      }

      ws.onmessage = ({ data }) => {
        try {
          const frame = JSON.parse(data) as { event: string; ts: number; payload: Record<string, unknown> }

          switch (frame.event) {
            case 'diagnostics_snapshot':
              mergeSnapshot(frame.payload)
              break
            case 'connected':
              setState('SLEEPING')
              break
            case 'system_ready':
              setState('IDLE')
              break
            case 'system_shutdown':
              setState('SLEEPING')
              break
            case 'wake_status':
              setState((frame.payload.active as boolean) ? 'IDLE' : 'SLEEPING')
              break
            case 'listening_started':
              setState('LISTENING')
              break
            case 'listening_finished':
              setState('IDLE')
              break
            case 'thinking_started':
              setState('THINKING')
              break
            case 'thinking_finished':
              setState('IDLE')
              break
            case 'tool_started':
              setState('EXECUTING')
              break
            case 'task_queued':
              setState('QUEUED')
              break
            case 'task_verifying':
              setState('VERIFYING')
              break
            case 'task_recovering':
              setState('RECOVERING')
              break
            case 'task_completed':
              setState('IDLE')
              if (frame.payload.confidence !== undefined) {
                setConfidence(frame.payload.confidence as number)
                setTimeout(() => setConfidence(null), 3000)
              }
              break
            case 'task_failed':
              setState('ERROR')
              setTimeout(() => setState('IDLE'), 3000)
              break
            case 'memory_written':
              triggerMemoryFlash()
              break
            case 'speech_started':
              setState('SPEAKING')
              break
            case 'speech_completed':
              setState('IDLE')
              break
            case 'audio_amplitude':
            case 'tts_amplitude':
              setAmplitude(frame.payload.value as number)
              break
            case 'task_progress':
              setProgress(frame.payload.pct as number)
              break

            // ── Command acknowledgement from backend ──────────────────────
            case 'command_ack': {
              const accepted = frame.payload.accepted as boolean
              const errorMsg = frame.payload.error as string | undefined
              if (!accepted) {
                const reason = errorMsg ?? 'Command was rejected by the backend.'
                console.warn('[Aurora WS] Command rejected:', frame.payload.text, '—', reason)
                setLastError(reason)
                setState('ERROR')
                setTimeout(() => {
                  setState('IDLE')
                  setLastError(null)
                }, 3000)
              } else {
                // Command accepted — clear any previous error
                setLastError(null)
                console.log('[Aurora WS] Command accepted:', frame.payload.text)
              }
              break
            }

            // ── Backend errors ────────────────────────────────────────────
            case 'error_occurred': {
              const errorMsg = (frame.payload.error as string) ?? 'Unknown backend error.'
              const source = (frame.payload.source as string) ?? 'unknown'
              console.error(`[Aurora WS] Backend error (${source}):`, errorMsg)
              setLastError(`[${source}] ${errorMsg}`)
              setState('ERROR')
              // Auto-recover: clear error state after 4 seconds
              setTimeout(() => {
                setState('IDLE')
                setLastError(null)
              }, 4000)
              break
            }
            default:
              // For event tracking
              if (['task_queued', 'task_started', 'task_verifying', 'task_recovering', 'task_completed', 'task_failed', 'memory_written'].includes(frame.event)) {
                appendEvent(frame)
              }
              break
          }
        } catch (e) {
          console.error('[Aurora WS] Parse error:', e)
        }
      }

      ws.onerror = (e) => {
        console.error('[Aurora WS] Connection error:', e)
        setConnected(false)
        setState('SLEEPING')
      }

      ws.onclose = () => {
        setConnected(false)
        setState('SLEEPING')
        console.log('[Aurora WS] Disconnected — reconnecting...')
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY)
      }
    }

    connect()

    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [])
}
