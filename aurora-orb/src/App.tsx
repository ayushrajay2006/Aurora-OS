import { useEffect } from 'react'
import { OrbScene } from './three/OrbScene'
import { InputOverlay } from './components/InputOverlay'
import { DiagnosticDrawer } from './components/DiagnosticDrawer'
import { useAuroraSocket } from './ws/useAuroraSocket'
import { useOrbStore, STATE_CONFIG } from './state/orbStore'
import './App.css'

function App() {
  useAuroraSocket()

  const currentState = useOrbStore(s => s.currentState)
  const cfg = STATE_CONFIG[currentState]

  // Update title for debugging
  useEffect(() => {
    document.title = `Aurora — ${cfg.label}`
  }, [currentState, cfg])

  return (
    <div
      className="app-root"
      style={{
        width: '100vw',
        height: '100vh',
        position: 'relative',
        overflow: 'hidden',
        background: '#000000',
      }}
    >
      {/* 3D Orb */}
      <OrbScene />

      {/* UI Overlay — click zones, input, status */}
      <InputOverlay />
      
      {/* Expanded Diagnostics Panel */}
      <DiagnosticDrawer />
    </div>
  )
}

export default App
