import { Canvas } from "@react-three/fiber";
import { OrbitControls, useGLTF, useTexture, Html } from "@react-three/drei";
import { Suspense, useMemo } from "react";
import * as THREE from "three";
import { ErrorBoundary } from "./ErrorBoundary";

// Types derived from Editor.tsx
type CellType = "WALL" | "ROAD" | "PARKING" | "ENTRY" | "EXIT";

interface CellDTO {
  x: number;
  y: number;
  type: CellType;
  metadata: Record<string, any>;
}

interface GridDTO {
  width: number;
  height: number;
  cells: CellDTO[];
}

interface Scene3DProps {
  grid: GridDTO | null;
  onCellClick?: (x: number, y: number) => void;
}

const CELL_SIZE = 2; 

// --- Asset Components ---

function Asset({ 
  url, 
  x, 
  y, 
  scale = 1, 
  rotation = [0, 0, 0], 
  onClick,
  color,
  opacity,
  texture
}: { 
  url: string; 
  x: number; 
  y: number; 
  scale?: number | [number, number, number]; 
  rotation?: [number, number, number];
  onClick?: () => void;
  color?: string;
  opacity?: number;
  texture: THREE.Texture;
}) {
  const { scene } = useGLTF(url);
  
  const clonedScene = useMemo(() => {
    const s = scene.clone(true);
    
    s.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        // Performance: Disable shadows
        child.castShadow = false;
        child.receiveShadow = false;
        
        const mat = (child as THREE.Mesh).material as THREE.MeshStandardMaterial;
        // Clone material to avoid shared state issues
        const clonedMat = mat.clone();
        clonedMat.map = texture;
        
        if (color) {
            clonedMat.color.set(color);
        }
        if (opacity !== undefined) {
             clonedMat.transparent = true;
             clonedMat.opacity = opacity;
        }
        
        (child as THREE.Mesh).material = clonedMat;
      }
    });
    return s;
  }, [scene, color, opacity, texture]);

  const position: [number, number, number] = [x * CELL_SIZE, 0, y * CELL_SIZE];
  
  const handlePointerDown = (e: any) => {
    e.stopPropagation();
    if (onClick) onClick();
  };

  return (
    <primitive 
      object={clonedScene} 
      position={position} 
      scale={Array.isArray(scale) ? scale : [scale, scale, scale]} 
      rotation={rotation}
      onClick={handlePointerDown} 
    />
  );
}

function Wall({ x, y, onClick, texture }: { x: number, y: number, onClick?: () => void, texture: THREE.Texture }) {
  // Using a primitive cube since shape-cube.glb was not found
  // Center is at (0,0,0) for boxGeometry, so we lift it up by half height (1.9/2 = 0.95)
  const position: [number, number, number] = [x * CELL_SIZE, 0.95, y * CELL_SIZE];
  
  const handlePointerDown = (e: any) => {
    e.stopPropagation();
    if (onClick) onClick();
  };

  return (
    <mesh 
      position={position}
      scale={[1.9, 1.9, 1.9]}
      onClick={handlePointerDown}
    >
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#777777" />
    </mesh>
  );
}

function Road({ x, y, onClick, texture }: { x: number, y: number, onClick?: () => void, texture: THREE.Texture }) {
  return <Asset url="/assets/models/floor.glb" x={x} y={y} scale={[1.9, 0.2, 1.9]} onClick={onClick} texture={texture} />;
}

function Parking({ x, y, onClick, texture }: { x: number, y: number, onClick?: () => void, texture: THREE.Texture }) {
  return (
    <group>
      <Asset url="/assets/models/floor.glb" x={x} y={y} scale={[1.9, 0.2, 1.9]} onClick={onClick} texture={texture} />
      {/* Visual Marker for Parking - Simplified geometry */}
      <mesh position={[x * CELL_SIZE, 0.1, y * CELL_SIZE]} rotation={[-Math.PI/2, 0, 0]} onClick={(e) => { e.stopPropagation(); onClick?.(); }}>
        <planeGeometry args={[1.5, 1.5]} />
        <meshBasicMaterial color="#4ade80" transparent opacity={0.4} />
      </mesh>
    </group>
  );
}

function Entry({ x, y, onClick, gridWidth, gridHeight, texture }: { x: number, y: number, onClick?: () => void, gridWidth: number, gridHeight: number, texture: THREE.Texture }) {
  let rotation: [number, number, number] = [0, 0, 0];
  if (x === 0) rotation = [0, 0, 0];
  else if (x === gridWidth - 1) rotation = [0, Math.PI, 0];
  else if (y === 0) rotation = [0, -Math.PI/2, 0];
  else if (y === gridHeight - 1) rotation = [0, Math.PI/2, 0];

  return (
    <group>
      <Asset url="/assets/models/wall-doorway-garage.glb" x={x} y={y} scale={[1.5, 1.5, 1.5]} rotation={rotation} onClick={onClick} texture={texture} />
      <mesh position={[x * CELL_SIZE, 1.5, y * CELL_SIZE]}>
        <boxGeometry args={[0.5, 0.5, 0.5]} />
        <meshBasicMaterial color="green" />
      </mesh>
    </group>
  );
}

function Exit({ x, y, onClick, gridWidth, gridHeight, texture }: { x: number, y: number, onClick?: () => void, gridWidth: number, gridHeight: number, texture: THREE.Texture }) {
  let rotation: [number, number, number] = [0, 0, 0];
  if (x === 0) rotation = [0, Math.PI, 0];
  else if (x === gridWidth - 1) rotation = [0, 0, 0];
  else if (y === 0) rotation = [0, Math.PI/2, 0];
  else if (y === gridHeight - 1) rotation = [0, -Math.PI/2, 0];

  return (
    <group>
      <Asset url="/assets/models/wall-doorway-garage.glb" x={x} y={y} scale={[1.5, 1.5, 1.5]} rotation={rotation} onClick={onClick} texture={texture} />
      <mesh position={[x * CELL_SIZE, 1.5, y * CELL_SIZE]}>
        <boxGeometry args={[0.5, 0.5, 0.5]} />
        <meshBasicMaterial color="red" />
      </mesh>
    </group>
  );
}

function Loader() {
  return (
    <Html center>
      <div style={{ color: 'white', background: 'rgba(0,0,0,0.8)', padding: '10px', borderRadius: '5px' }}>
        Loading 3D Assets...
      </div>
    </Html>
  );
}

function SceneContent({ grid, onCellClick }: { grid: GridDTO, onCellClick?: (x: number, y: number) => void }) {
  const texture = useTexture("/assets/models/Textures/colormap.png");
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.flipY = false;

  return (
    <group>
      {grid.cells.map((cell) => {
         const key = `${cell.x}-${cell.y}`;
         const props = { x: cell.x, y: cell.y, onClick: () => onCellClick?.(cell.x, cell.y), texture };

         switch (cell.type) {
           case "WALL": return <Wall key={key} {...props} />;
           case "ROAD": return <Road key={key} {...props} />;
           case "PARKING": return <Parking key={key} {...props} />;
           case "ENTRY": return <Entry key={key} {...props} gridWidth={grid.width} gridHeight={grid.height} />;
           case "EXIT": return <Exit key={key} {...props} gridWidth={grid.width} gridHeight={grid.height} />;
           default: return null;
         }
      })}
    </group>
  );
}

// Preload
useGLTF.preload("/assets/models/floor.glb");
useGLTF.preload("/assets/models/wall-doorway-garage.glb");
useGLTF.preload("/assets/models/car.glb");
useTexture.preload("/assets/models/Textures/colormap.png");

export default function Scene3D({ grid, onCellClick }: Scene3DProps) {
  if (!grid) return null;

  const centerX = (grid.width * CELL_SIZE) / 2;
  const centerZ = (grid.height * CELL_SIZE) / 2;

  // Camera looking from top-down, slightly angled for 3D effect but static
  // Higher Y (40) and Z offset (20) for a good overview
  const cameraPosition: [number, number, number] = [centerX, 40, centerZ + 20];

  return (
    <ErrorBoundary fallback={<div style={{color:'red', padding:'20px'}}>Error loading 3D Scene. Check console.</div>}>
      <div style={{ width: "100%", height: "100%", background: "transparent" }}>
        {/* Performance: dpr restricted, shadows disabled, static camera */}
        <Canvas 
          dpr={[1, 1.5]} 
          camera={{ position: cameraPosition, fov: 40 }}
          style={{ width: '100%', height: '100%' }}
        >
          {/* Simple Lighting - No Shadows */}
          <ambientLight intensity={0.8} />
          <directionalLight position={[50, 50, 25]} intensity={1} />
          
          <Suspense fallback={<Loader />}>
            <SceneContent grid={grid} onCellClick={onCellClick} />
            
            {/* Ground Plane - Removed opaque plane to let CSS background show through */}
            {/* <mesh rotation={[-Math.PI / 2, 0, 0]} position={[centerX, -0.1, centerZ]}>
              <planeGeometry args={[100, 100]} />
              <meshBasicMaterial color="#333" />
            </mesh> */}
            <gridHelper args={[100, 50, 0x38bdf8, 0x334155]} position={[centerX, -0.05, centerZ]} />
          </Suspense>
          
          {/* Interactive Camera Controls */}
          <OrbitControls 
            target={[centerX, 0, centerZ]} 
            enableRotate={true} 
            enablePan={true} 
            enableZoom={true} 
          />
        </Canvas>
      </div>
    </ErrorBoundary>
  );
}
