import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useOrbStore, STATE_CONFIG } from '../state/orbStore'

export function OrbRings() {
  const ring1Ref = useRef<THREE.Mesh>(null)
  const ring2Ref = useRef<THREE.Mesh>(null)
  const ring3Ref = useRef<THREE.Mesh>(null)
  const progressRef = useRef<THREE.Mesh>(null)

  const currentState = useOrbStore(s => s.currentState)
  const taskProgress = useOrbStore(s => s.taskProgress)

  useFrame(({ clock }) => {
    const cfg = STATE_CONFIG[currentState]
    const t = clock.getElapsedTime()
    const spd = cfg.rotationSpeed

    // Ring 1 — tilted 30°, clockwise
    if (ring1Ref.current) {
      ring1Ref.current.rotation.z = t * spd * 0.8
      ring1Ref.current.rotation.x = Math.PI / 6
      ;(ring1Ref.current.material as THREE.MeshBasicMaterial).color.set(cfg.colors.ring)
      ;(ring1Ref.current.material as THREE.MeshBasicMaterial).opacity =
        currentState === 'SLEEPING' ? 0.1 : 0.6
    }

    // Ring 2 — tilted 60°, counter-clockwise at 1.6×
    if (ring2Ref.current) {
      ring2Ref.current.rotation.z = -t * spd * 1.6 * 0.8
      ring2Ref.current.rotation.x = Math.PI / 3
      ;(ring2Ref.current.material as THREE.MeshBasicMaterial).color.set(cfg.colors.ring)
      ;(ring2Ref.current.material as THREE.MeshBasicMaterial).opacity =
        currentState === 'SLEEPING' ? 0.05 : 0.4
    }

    // Ring 3 — horizontal, slow drift
    if (ring3Ref.current) {
      ring3Ref.current.rotation.y = t * spd * 0.3
      ;(ring3Ref.current.material as THREE.MeshBasicMaterial).color.set(cfg.colors.ring)
      ;(ring3Ref.current.material as THREE.MeshBasicMaterial).opacity =
        currentState === 'SLEEPING' ? 0.05 : 0.25
    }

    // Progress ring arc (EXECUTING state only)
    if (progressRef.current) {
      progressRef.current.visible = currentState === 'EXECUTING'
      if (currentState === 'EXECUTING') {
        progressRef.current.rotation.z = t * 0.5
        ;(progressRef.current.material as THREE.MeshBasicMaterial).color.set('#34d399')
      }
    }
  })

  return (
    <group>
      {/* Ring 1 */}
      <mesh ref={ring1Ref}>
        <torusGeometry args={[1.45, 0.008, 8, 80]} />
        <meshBasicMaterial color="#60a5fa" transparent opacity={0.6} depthWrite={false} />
      </mesh>

      {/* Ring 2 */}
      <mesh ref={ring2Ref}>
        <torusGeometry args={[1.65, 0.006, 8, 80]} />
        <meshBasicMaterial color="#60a5fa" transparent opacity={0.4} depthWrite={false} />
      </mesh>

      {/* Ring 3 — outer slow orbit */}
      <mesh ref={ring3Ref}>
        <torusGeometry args={[1.85, 0.004, 8, 80]} />
        <meshBasicMaterial color="#60a5fa" transparent opacity={0.2} depthWrite={false} />
      </mesh>

      {/* Progress arc ring */}
      <mesh ref={progressRef} visible={false}>
        <torusGeometry args={[1.55, 0.012, 8, 80, Math.PI * 2 * taskProgress]} />
        <meshBasicMaterial color="#34d399" transparent opacity={0.9} depthWrite={false} />
      </mesh>
    </group>
  )
}
