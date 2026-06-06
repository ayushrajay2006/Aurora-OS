import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useOrbStore, STATE_CONFIG } from '../state/orbStore'

export function OrbParticles() {
  const pointsRef = useRef<THREE.Points>(null)
  const materialRef = useRef<THREE.PointsMaterial>(null)
  
  const currentState = useOrbStore(s => s.currentState)
  const amplitude = useOrbStore(s => s.amplitude)
  const cfg = STATE_CONFIG[currentState]
  
  // Create 500 max particles, but we will dynamically adjust visibility
  const maxParticles = 500
  const [positions, phases] = useMemo(() => {
    const pos = new Float32Array(maxParticles * 3)
    const ph = new Float32Array(maxParticles)
    for (let i = 0; i < maxParticles; i++) {
      // Random spherical distribution around radius 1.8 to 3.0
      const radius = 1.8 + Math.random() * 1.2
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos((Math.random() * 2) - 1)
      
      pos[i * 3] = radius * Math.sin(phi) * Math.cos(theta)
      pos[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta)
      pos[i * 3 + 2] = radius * Math.cos(phi)
      
      ph[i] = Math.random() * Math.PI * 2
    }
    return [pos, ph]
  }, [])
  
  const particleColor = useMemo(() => new THREE.Color(), [])

  useFrame((state) => {
    if (!pointsRef.current || !materialRef.current) return
    
    // Rotate entire cloud
    pointsRef.current.rotation.y += cfg.rotationSpeed * 0.003
    pointsRef.current.rotation.x += cfg.rotationSpeed * 0.002
    
    // Keep background stars pure white against the black void
    particleColor.lerp(new THREE.Color('#ffffff'), 0.05)
    materialRef.current.color.copy(particleColor)
    
    // Adjust size based on amplitude
    materialRef.current.size = 0.04 * (1.0 + amplitude * 1.5)
    
    // Animate positions slightly
    const pos = pointsRef.current.geometry.attributes.position.array as Float32Array
    for (let i = 0; i < maxParticles; i++) {
        // If i is > current config particle count, shrink it to 0 or hide it by moving it inside
        if (i > cfg.particleCount) {
            pos[i*3] *= 0.95 // pull inside
        } else {
            // Push back out to original radius roughly, or add some jitter
            const jitter = Math.sin(state.clock.elapsedTime * 2.0 + phases[i]) * 0.005
            pos[i*3] += pos[i*3] * jitter
            pos[i*3+1] += pos[i*3+1] * jitter
            pos[i*3+2] += pos[i*3+2] * jitter
        }
    }
    pointsRef.current.geometry.attributes.position.needsUpdate = true
  })

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        ref={materialRef}
        size={0.04}
        transparent={true}
        opacity={0.6}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  )
}
