import { create } from 'zustand'

export type OrbState =
  | 'SLEEPING'
  | 'IDLE'
  | 'QUEUED'
  | 'LISTENING'
  | 'THINKING'
  | 'EXECUTING'
  | 'VERIFYING'
  | 'RECOVERING'
  | 'SPEAKING'
  | 'ERROR'

export interface OrbColors {
  core: string
  glow: string
  ring: string
}

export const STATE_CONFIG: Record<OrbState, {
  colors: OrbColors
  pulseSpeed: number
  rotationSpeed: number
  particleCount: number
  label: string
}> = {
  SLEEPING:  { colors: { core: '#475569', glow: '#1e293b', ring: '#334155' }, pulseSpeed: 0.3,  rotationSpeed: 0.04, particleCount: 40,  label: 'Sleeping'  },
  IDLE:      { colors: { core: '#3B82F6', glow: '#1d4ed8', ring: '#60a5fa' }, pulseSpeed: 0.5,  rotationSpeed: 0.12, particleCount: 120, label: 'Idle'      },
  QUEUED:    { colors: { core: '#60A5FA', glow: '#2563EB', ring: '#93C5FD' }, pulseSpeed: 0.6,  rotationSpeed: 0.08, particleCount: 150, label: 'Queued'    },
  LISTENING: { colors: { core: '#06B6D4', glow: '#0e7490', ring: '#22d3ee' }, pulseSpeed: 1.2,  rotationSpeed: 0.25, particleCount: 200, label: 'Listening' },
  THINKING:  { colors: { core: '#A855F7', glow: '#7e22ce', ring: '#c084fc' }, pulseSpeed: 1.5,  rotationSpeed: 0.65, particleCount: 350, label: 'Thinking'  },
  EXECUTING: { colors: { core: '#10B981', glow: '#065f46', ring: '#34d399' }, pulseSpeed: 2.0,  rotationSpeed: 0.33, particleCount: 400, label: 'Executing' },
  VERIFYING: { colors: { core: '#FACC15', glow: '#CA8A04', ring: '#FEF08A' }, pulseSpeed: 1.5,  rotationSpeed: 0.50, particleCount: 300, label: 'Verifying' },
  RECOVERING:{ colors: { core: '#F97316', glow: '#C2410C', ring: '#FDBA74' }, pulseSpeed: 3.5,  rotationSpeed: 1.20, particleCount: 450, label: 'Recovering'},
  SPEAKING:  { colors: { core: '#F97316', glow: '#c2410c', ring: '#fb923c' }, pulseSpeed: 3.0,  rotationSpeed: 0.17, particleCount: 280, label: 'Speaking'  },
  ERROR:     { colors: { core: '#EF4444', glow: '#7f1d1d', ring: '#f87171' }, pulseSpeed: 5.0,  rotationSpeed: 0.08, particleCount: 80,  label: 'Error'     },
}

interface OrbStore {
  currentState: OrbState
  amplitude: number       // 0.0–1.0 from audio/tts events
  taskProgress: number    // 0.0–1.0 from task_progress events
  connected: boolean      // WebSocket connected
  statusLabel: string
  lastError: string | null  // most recent backend error message
  
  confidenceScore: number | null
  memoryFlashTrigger: number
  eventHistory: any[]
  queuedTasks: any[]
  activeTask: any | null

  setState: (s: OrbState) => void
  setAmplitude: (v: number) => void
  setProgress: (v: number) => void
  setConnected: (v: boolean) => void
  setLastError: (msg: string | null) => void
  setConfidence: (v: number | null) => void
  triggerMemoryFlash: () => void
  mergeSnapshot: (payload: any) => void
  appendEvent: (event: any) => void
}

export const useOrbStore = create<OrbStore>((set) => ({
  currentState: 'SLEEPING',
  amplitude: 0,
  taskProgress: 0,
  connected: false,
  statusLabel: 'Sleeping',
  lastError: null,
  confidenceScore: null,
  memoryFlashTrigger: 0,
  eventHistory: [],
  queuedTasks: [],
  activeTask: null,

  setState: (s) => set({ currentState: s, statusLabel: STATE_CONFIG[s].label }),
  setAmplitude: (v) => set({ amplitude: v }),
  setProgress: (v) => set({ taskProgress: v }),
  setConnected: (v) => set({ connected: v }),
  setLastError: (msg) => set({ lastError: msg }),
  setConfidence: (v) => set({ confidenceScore: v }),
  triggerMemoryFlash: () => {
    const now = Date.now()
    set((state) => {
      if (now - state.memoryFlashTrigger > 1000) {
        return { memoryFlashTrigger: now }
      }
      return {}
    })
  },
  mergeSnapshot: (payload) => set({ 
    eventHistory: payload.event_history || [],
    queuedTasks: payload.queued_tasks || [],
    activeTask: payload.active_task || null
  }),
  appendEvent: (event) => set((state) => ({
    eventHistory: [...state.eventHistory, event].slice(-100)
  }))
}))
