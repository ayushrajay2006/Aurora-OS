import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useOrbStore } from '../state/orbStore'

const RIPPLE_COUNT = 4

export function OrbRipple() {
  const refs = Array.from({ length: RIPPLE_COUNT }, () => useRef<THREE.Mesh>(null))
  const currentState = useOrbStore(s => s.currentState)
  const amplitude = useOrbStore(s => s.amplitude)

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime()
    const isListening = currentState === 'LISTENING'
    const isSpeaking = currentState === 'SPEAKING'

    refs.forEach((ref, i) => {
      if (!ref.current) return
      const mat = ref.current.material as THREE.MeshBasicMaterial

      if (isListening) {
        // Expanding concentric shell waves
        const phase = (t * 0.5 + i * (1 / RIPPLE_COUNT)) % 1
        const scale = 1.0 + phase * 2.5
        ref.current.scale.setScalar(scale)
        mat.opacity = (1 - phase) * 0.35
        mat.color.set('#06B6D4')
        ref.current.visible = true
      } else if (isSpeaking) {
        // Jitter driven by tts_amplitude
        const jitter = 1.0 + amplitude * 0.5 * Math.sin(t * 30 + i * 1.2)
        const phase = (t * 0.8 + i * (1 / RIPPLE_COUNT)) % 1
        ref.current.scale.setScalar(jitter + phase * 1.2)
        mat.opacity = (1 - phase) * 0.2 * (0.5 + amplitude)
        mat.color.set('#F97316')
        ref.current.visible = true
      } else {
        ref.current.visible = false
      }
    })
  })

  return (
    <group>
      {refs.map((ref, i) => (
        <mesh key={i} ref={ref} visible={false}>
          <sphereGeometry args={[1.0, 24, 24]} />
          <meshBasicMaterial
            color="#06B6D4"
            transparent
            opacity={0}
            depthWrite={false}
            side={THREE.BackSide}
            wireframe={false}
          />
        </mesh>
      ))}
    </group>
  )
}
