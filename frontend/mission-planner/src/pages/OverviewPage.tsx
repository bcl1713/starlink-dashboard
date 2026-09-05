import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import './OverviewPage.css';

function Globe() {
  return (
    <mesh>
      <sphereGeometry args={[2, 64, 64]} />
      <meshStandardMaterial color="#31506e" roughness={0.65} metalness={0.15} />
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
        <Globe />
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
