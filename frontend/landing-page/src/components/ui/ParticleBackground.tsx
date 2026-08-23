"use client";

import { Canvas } from "@react-three/fiber";
import { GPGPUParticles } from "./particles/GPGPUParticles";

export function ParticleBackground() {
  return (
    <div className="fixed inset-0 z-0 pointer-events-none">
      <Canvas camera={{ position: [0, 0, 5], fov: 60 }} gl={{ antialias: false, alpha: true }}>
        <color attach="background" args={["#000000"]} />
        <GPGPUParticles />
      </Canvas>
    </div>
  );
}
