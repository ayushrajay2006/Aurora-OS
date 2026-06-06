import { useState } from 'react'
import { useOrbStore } from '../state/orbStore'

export function DiagnosticDrawer() {
  const [isOpen, setIsOpen] = useState(false)
  const eventHistory = useOrbStore(s => s.eventHistory)
  const queuedTasks = useOrbStore(s => s.queuedTasks)
  const activeTask = useOrbStore(s => s.activeTask)
  const currentState = useOrbStore(s => s.currentState)

  // Filter events to find recent memory writes
  const memoryEvents = eventHistory.filter(e => e.event === 'memory_written').reverse().slice(0, 5)
  
  // Build a timeline for the active task
  const activeTaskEvents = activeTask 
    ? eventHistory.filter(e => e.payload && e.payload.task_id === activeTask.task_id)
    : []

  return (
    <>
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          position: 'absolute',
          top: 20,
          right: 20,
          background: 'rgba(15, 23, 42, 0.6)',
          border: '1px solid rgba(148, 163, 184, 0.2)',
          color: '#f8fafc',
          padding: '6px 12px',
          borderRadius: '8px',
          cursor: 'pointer',
          zIndex: 50,
          backdropFilter: 'blur(8px)',
          fontFamily: '"Segoe UI", system-ui, sans-serif',
          fontSize: '12px'
        }}
      >
        {isOpen ? 'Close Diagnostics' : 'Expand Diagnostics'}
      </button>

      {/* Drawer Panel */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          right: 0,
          width: '320px',
          height: '100vh',
          background: 'rgba(15, 23, 42, 0.85)',
          backdropFilter: 'blur(16px)',
          borderLeft: '1px solid rgba(148, 163, 184, 0.1)',
          transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          zIndex: 40,
          color: '#f8fafc',
          fontFamily: '"Segoe UI", system-ui, sans-serif',
          padding: '60px 20px 20px',
          boxSizing: 'border-box',
          overflowY: 'auto'
        }}
      >
        <h2 style={{ fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px', color: '#94a3b8', marginBottom: '16px' }}>System State</h2>
        <div style={{ background: 'rgba(255,255,255,0.05)', padding: '12px', borderRadius: '8px', marginBottom: '24px' }}>
          <div style={{ fontSize: '12px', color: '#cbd5e1' }}>Primary State: <strong style={{ color: '#fff' }}>{currentState}</strong></div>
          <div style={{ fontSize: '12px', color: '#cbd5e1', marginTop: '4px' }}>Active Task: <strong style={{ color: '#fff' }}>{activeTask ? activeTask.tool_call.tool_name : 'None'}</strong></div>
        </div>

        {activeTask && (
          <>
            <h2 style={{ fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px', color: '#94a3b8', marginBottom: '16px' }}>Task Timeline</h2>
            <div style={{ marginBottom: '24px', borderLeft: '2px solid rgba(148, 163, 184, 0.2)', paddingLeft: '12px', marginLeft: '6px' }}>
              {activeTaskEvents.map((evt, idx) => (
                <div key={idx} style={{ position: 'relative', marginBottom: '12px' }}>
                  <div style={{
                    position: 'absolute',
                    left: '-17px',
                    top: '4px',
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: evt.event.includes('failed') || evt.event.includes('error') ? '#ef4444' 
                              : evt.event.includes('completed') ? '#10b981' 
                              : '#3b82f6'
                  }} />
                  <div style={{ fontSize: '13px', fontWeight: 600 }}>{evt.event.replace('task_', '').toUpperCase()}</div>
                  <div style={{ fontSize: '11px', color: '#94a3b8' }}>{new Date(evt.ts * 1000).toLocaleTimeString()}</div>
                </div>
              ))}
            </div>
          </>
        )}

        {queuedTasks.length > 0 && (
          <>
            <h2 style={{ fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px', color: '#94a3b8', marginBottom: '16px' }}>Queued Tasks ({queuedTasks.length})</h2>
            <div style={{ marginBottom: '24px' }}>
              {queuedTasks.map((t, idx) => (
                <div key={idx} style={{ background: 'rgba(255,255,255,0.05)', padding: '8px 12px', borderRadius: '6px', marginBottom: '8px', fontSize: '12px' }}>
                  {t.tool_call.tool_name}
                </div>
              ))}
            </div>
          </>
        )}

        <h2 style={{ fontSize: '14px', textTransform: 'uppercase', letterSpacing: '1px', color: '#94a3b8', marginBottom: '16px' }}>Recent Memory</h2>
        <div>
          {memoryEvents.length === 0 ? <div style={{ fontSize: '12px', color: '#64748b' }}>No recent memory writes.</div> : null}
          {memoryEvents.map((evt, idx) => (
            <div key={idx} style={{ background: 'rgba(255,255,255,0.05)', padding: '8px 12px', borderRadius: '6px', marginBottom: '8px' }}>
              <div style={{ fontSize: '11px', color: '#3b82f6', marginBottom: '4px' }}>{evt.payload.key}</div>
              <div style={{ fontSize: '12px', color: '#e2e8f0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {evt.payload.value}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
