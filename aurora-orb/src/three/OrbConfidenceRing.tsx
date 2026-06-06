import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useOrbStore } from '../state/orbStore'

export function OrbConfidenceRing() {
  const meshRef = useRef<THREE.Mesh>(null)
  const materialRef = useRef<THREE.MeshBasicMaterial>(null)
  const confidenceScore = useOrbStore(s => s.confidenceScore)
  
  // Create a torus geometry
  const geometry = useMemo(() => new THREE.TorusGeometry(2.5, 0.02, 16, 100), [])
  
  useFrame((_state, delta) => {
    if (!meshRef.current || !materialRef.current) return
    
    // Smoothly fade in and out based on if confidenceScore is null or not
    const targetOpacity = confidenceScore !== null ? 0.8 : 0.0
    materialRef.current.opacity = THREE.MathUtils.lerp(materialRef.current.opacity, targetOpacity, 0.1)
    
    // Scale ring based on confidence (e.g. 90% confidence = arc length or we can just color it)
    // To make it simple, we'll draw the full ring but rotate it, and maybe color it green/red based on score
    if (confidenceScore !== null) {
        const isHigh = confidenceScore > 0.8
        const targetColor = isHigh ? new THREE.Color('#34d399') : new THREE.Color('#facc15')
        materialRef.current.color.lerp(targetColor, 0.1)
    }
    
    // Rotate ring
    meshRef.current.rotation.z += delta * 0.5
    meshRef.current.rotation.x = Math.PI / 2 // Flat ring
  })

  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshBasicMaterial 
        ref={materialRef}
        color="#ffffff" 
        transparent={true} 
        opacity={0} 
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </mesh>
  )
}
