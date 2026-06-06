import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useOrbStore, STATE_CONFIG } from '../state/orbStore'

import vertexShader from './shaders/orbVertex.glsl?raw'
import fragmentShader from './shaders/orbFragment.glsl?raw'

export function OrbMesh() {
  const meshRef = useRef<THREE.Mesh>(null)
  const materialRef = useRef<THREE.ShaderMaterial>(null)
  
  const currentState = useOrbStore(s => s.currentState)
  const amplitude = useOrbStore(s => s.amplitude)
  const cfg = STATE_CONFIG[currentState]
  
  const uniforms = useMemo(() => ({
    u_time: { value: 0 },
    u_amplitude: { value: 0 },
    u_pulseSpeed: { value: 1.0 },
    u_stateColor: { value: new THREE.Color() },
    u_glowColor: { value: new THREE.Color() },
    u_opacity: { value: 1.0 },
    u_isVerifying: { value: 0.0 }
  }), [])

  useFrame((state) => {
    if (materialRef.current) {
      const m = materialRef.current
      m.uniforms.u_time.value = state.clock.elapsedTime
      m.uniforms.u_amplitude.value = THREE.MathUtils.lerp(m.uniforms.u_amplitude.value, amplitude, 0.1)
      
      const targetPulse = cfg.pulseSpeed
      m.uniforms.u_pulseSpeed.value = THREE.MathUtils.lerp(m.uniforms.u_pulseSpeed.value, targetPulse, 0.05)
      
      const targetColor = new THREE.Color(cfg.colors.core)
      m.uniforms.u_stateColor.value.lerp(targetColor, 0.05)
      
      const targetGlow = new THREE.Color(cfg.colors.glow)
      m.uniforms.u_glowColor.value.lerp(targetGlow, 0.05)
      
      m.uniforms.u_isVerifying.value = currentState === 'VERIFYING' ? 1.0 : 0.0
    }
    
    if (meshRef.current) {
        meshRef.current.rotation.y += cfg.rotationSpeed * 0.01
        meshRef.current.rotation.x += cfg.rotationSpeed * 0.005
    }
  })

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[1.5, 64, 64]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={vertexShader}
        fragmentShader={fragmentShader}
        uniforms={uniforms}
        transparent={true}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  )
}
