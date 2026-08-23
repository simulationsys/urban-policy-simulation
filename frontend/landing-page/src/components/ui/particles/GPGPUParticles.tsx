"use client";

import * as THREE from 'three';
import { useMemo, useRef } from 'react';
import { createPortal, useFrame } from '@react-three/fiber';
import { useFBO } from '@react-three/drei';
import { SimulationMaterial } from './SimulationMaterial';
import { RenderMaterial } from './RenderMaterial';

export function GPGPUParticles() {
  const size = 128; // 128 * 128 = 16,384 particles

  // Setup FBO
  const renderTarget = useFBO(size, size, {
    minFilter: THREE.NearestFilter,
    magFilter: THREE.NearestFilter,
    format: THREE.RGBAFormat,
    type: THREE.FloatType,
  });

  // Setup another render target for ping-ponging if needed, but since we use SimulationMaterial which updates positions based on time, a single FBO might require ping-pong, but actually standard FBOs in R3F are often set up to read from their own texture or we use two FBOs.
  // We'll ping-pong between two FBOs to read previous frame's positions and write new ones.
  const renderTargetClone = renderTarget.clone();
  let renderTargetCurrent = renderTarget;
  let renderTargetNext = renderTargetClone;

  // Scene for simulation (imperative)
  const { scene, camera, simulationMaterial } = useMemo(() => {
    const simScene = new THREE.Scene();
    const simCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 1 / Math.pow(2, 53), 1);
    
    const mat = new SimulationMaterial();
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
    simScene.add(mesh);
    
    return { scene: simScene, camera: simCamera, simulationMaterial: mat };
  }, []);

  // Initial random positions
  const positions = useMemo(() => {
    const length = size * size * 4;
    const data = new Float32Array(length);
    for (let i = 0; i < length; i += 4) {
      data[i] = (Math.random() - 0.5) * 4.0;     // x
      data[i + 1] = (Math.random() - 0.5) * 4.0; // y
      data[i + 2] = (Math.random() - 0.5) * 4.0; // z
      data[i + 3] = 1.0;                         // w
    }
    const texture = new THREE.DataTexture(data, size, size, THREE.RGBAFormat, THREE.FloatType);
    texture.needsUpdate = true;
    return texture;
  }, [size]);

  // Points setup
  const particles = useMemo(() => {
    const length = size * size;
    const vertices = new Float32Array(length * 3);
    for (let i = 0; i < length; i++) {
      let i3 = i * 3;
      vertices[i3] = (i % size) / size;
      vertices[i3 + 1] = i / size / size;
      vertices[i3 + 2] = 0;
    }
    return vertices;
  }, [size]);
  
  const renderMaterial = useRef<InstanceType<typeof RenderMaterial>>(null);

  const isInitialized = useRef(false);

  useFrame((state) => {
    const { gl, clock } = state;
    
    // Update simulation material
    simulationMaterial.uniforms.uTime.value = clock.elapsedTime;
    
    if (!isInitialized.current) {
      simulationMaterial.uniforms.positions.value = positions;
      isInitialized.current = true;
    } else {
      simulationMaterial.uniforms.positions.value = renderTargetCurrent.texture;
    }

    // Render to FBO
    gl.setRenderTarget(renderTargetNext);
    gl.clear();
    gl.render(scene, camera);
    gl.setRenderTarget(null);

    // Update render material to use the new texture
    if (renderMaterial.current) {
      renderMaterial.current.uniforms.positions.value = renderTargetNext.texture;
    }

    // Ping-pong
    const temp = renderTargetCurrent;
    renderTargetCurrent = renderTargetNext;
    renderTargetNext = temp;
  });

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[particles, 3]}
        />
      </bufferGeometry>
      <primitive object={new RenderMaterial()} ref={renderMaterial} attach="material" />
    </points>
  );
}
