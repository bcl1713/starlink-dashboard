import { Suspense, useEffect, useMemo } from 'react';
import { Canvas, useLoader } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import './OverviewPage.css';

function Globe() {
  const sourceTexture = useLoader(THREE.TextureLoader, '/earth-night.jpg');

  const colorMap = useMemo(() => {
    const texture = sourceTexture.clone();

    texture.colorSpace = THREE.SRGBColorSpace;
    texture.needsUpdate = true;
    return texture;
  }, [sourceTexture]);

  useEffect(() => {
    return () => {
      colorMap.dispose();
    };
  }, [colorMap]);

  return (
    <mesh>
      <sphereGeometry args={[2, 64, 64]} />
      <meshStandardMaterial
        map={colorMap}
        emissive="#ffffff"
        emissiveMap={colorMap}
        emissiveIntensity={0.75}
        roughness={0.8}
        metalness={0.05}
      />
    </mesh>
  );
}

export function OverviewPage() {
  return (
    <main className="overview-page">
      <Canvas camera={{ position: [0, 0, 6], fov: 45 }}>
        <color attach="background" args={['#030307']} />
        <ambientLight intensity={0.35} />
        <directionalLight position={[5, 3, 5]} intensity={1.4} />
        <Suspense fallback={null}>
          <Globe />
        </Suspense>
        <OrbitControls
          enablePan={false}
          enableDamping
          dampingFactor={0.05}
          minDistance={3}
          maxDistance={10}
        />
      </Canvas>
    </main>
  );
}
