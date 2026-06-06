import { Suspense, useEffect, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { EffectComposer, Bloom, ChromaticAberration } from '@react-three/postprocessing'
import { BlendFunction } from 'postprocessing'
import * as THREE from 'three'
import { OrbMesh } from './OrbMesh'
import { OrbParticles } from './OrbParticles'
import { OrbConfidenceRing } from './OrbConfidenceRing'
import { useOrbStore } from '../state/orbStore'

function PostProcessing() {
  const memoryFlashTrigger = useOrbStore(s => s.memoryFlashTrigger)
  const currentState = useOrbStore(s => s.currentState)
  const [bloomIntensity, setBloomIntensity] = useState(1.2)

  useEffect(() => {
    if (memoryFlashTrigger > 0) {
      setBloomIntensity(3.5)
      
      const interval = setInterval(() => {
        setBloomIntensity(prev => {
          if (prev <= 1.2) {
            clearInterval(interval)
            return 1.2
          }
          return prev * 0.85
        })
      }, 30)
      return () => clearInterval(interval)
    } else {
        setBloomIntensity(currentState === 'THINKING' ? 1.8 : currentState === 'SLEEPING' ? 0.4 : 1.2)
    }
  }, [memoryFlashTrigger, currentState])

  return (
    <EffectComposer>
      <Bloom 
        luminanceThreshold={0.6} 
        luminanceSmoothing={0.9} 
        intensity={bloomIntensity * 0.4} 
      />
      <ChromaticAberration 
        blendFunction={BlendFunction.NORMAL} 
        offset={new THREE.Vector2(0.002, 0.002)} 
      />
    </EffectComposer>
  )
}

export function OrbScene() {
  return (
    <Canvas
      camera={{ position: [0, 0, 6], fov: 60 }}
      gl={{ alpha: true, antialias: true }}
      style={{ 
        background: 'transparent',
        position: 'absolute',
        inset: 0,
      }}
    >
      <ambientLight intensity={0.05} />
      <pointLight position={[0, 0, 0]} intensity={0.5} distance={6} decay={2} color="#ffffff" />
      
      <Suspense fallback={null}>
        <OrbMesh />
        <OrbParticles />
        <OrbConfidenceRing />
      </Suspense>

      <PostProcessing />
    </Canvas>
  )
}
