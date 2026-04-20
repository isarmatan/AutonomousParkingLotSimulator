import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, useGLTF, useTexture, Html, Text } from "@react-three/drei";
import { Suspense, useMemo, useRef } from "react";
import * as THREE from "three";
import { ErrorBoundary } from "./ErrorBoundary";

// Types
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

interface Timestep {
  t: number;
  cars: Record<string, [number, number, number]>; // car_id -> [x, y, is_initial]
}

interface Simulation3DProps {
  grid: GridDTO;
  timesteps: Timestep[];
  currentStepIndex: number;
  stepProgress: number;
}

const CELL_SIZE = 2; 

// --- Asset Components (Reused from Scene3D) ---

function Asset({ 
  url, 
  x, 
  y, 
  scale = 1, 
  rotation = [0, 0, 0], 
  color,
  opacity,
  texture
}: { 
  url: string; 
  x: number; 
  y: number; 
  scale?: number | [number, number, number]; 
  rotation?: [number, number, number];
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

  return (
    <primitive 
      object={clonedScene} 
      position={position} 
      scale={Array.isArray(scale) ? scale : [scale, scale, scale]} 
      rotation={rotation}
    />
  );
}

function Wall({ x, y, texture }: { x: number, y: number, texture: THREE.Texture }) {
  const position: [number, number, number] = [x * CELL_SIZE, 0.95, y * CELL_SIZE];
  
  return (
    <mesh position={position} scale={[1.9, 1.9, 1.9]}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#777777" />
    </mesh>
  );
}

function Road({ x, y, texture }: { x: number, y: number, texture: THREE.Texture }) {
  return <Asset url="/assets/models/floor.glb" x={x} y={y} scale={[1.9, 0.2, 1.9]} texture={texture} />;
}

function Parking({ x, y, texture }: { x: number, y: number, texture: THREE.Texture }) {
  return (
    <group>
      <Asset url="/assets/models/floor.glb" x={x} y={y} scale={[1.9, 0.2, 1.9]} texture={texture} />
      <mesh position={[x * CELL_SIZE, 0.1, y * CELL_SIZE]} rotation={[-Math.PI/2, 0, 0]}>
        <planeGeometry args={[1.5, 1.5]} />
        <meshBasicMaterial color="#4ade80" transparent opacity={0.4} />
      </mesh>
    </group>
  );
}

function Entry({ x, y, gridWidth, gridHeight, texture }: { x: number, y: number, gridWidth: number, gridHeight: number, texture: THREE.Texture }) {
  let rotation: [number, number, number] = [0, 0, 0];
  if (x === 0) rotation = [0, 0, 0];
  else if (x === gridWidth - 1) rotation = [0, Math.PI, 0];
  else if (y === 0) rotation = [0, -Math.PI/2, 0];
  else if (y === gridHeight - 1) rotation = [0, Math.PI/2, 0];

  return (
    <group>
      <Asset url="/assets/models/wall-doorway-garage.glb" x={x} y={y} scale={[1.5, 1.5, 1.5]} rotation={rotation} texture={texture} />
      <mesh position={[x * CELL_SIZE, 1.5, y * CELL_SIZE]}>
        <boxGeometry args={[0.5, 0.5, 0.5]} />
        <meshBasicMaterial color="green" />
      </mesh>
    </group>
  );
}

function Exit({ x, y, gridWidth, gridHeight, texture }: { x: number, y: number, gridWidth: number, gridHeight: number, texture: THREE.Texture }) {
  let rotation: [number, number, number] = [0, 0, 0];
  if (x === 0) rotation = [0, Math.PI, 0];
  else if (x === gridWidth - 1) rotation = [0, 0, 0];
  else if (y === 0) rotation = [0, Math.PI/2, 0];
  else if (y === gridHeight - 1) rotation = [0, -Math.PI/2, 0];

  return (
    <group>
      <Asset url="/assets/models/wall-doorway-garage.glb" x={x} y={y} scale={[1.5, 1.5, 1.5]} rotation={rotation} texture={texture} />
      <mesh position={[x * CELL_SIZE, 1.5, y * CELL_SIZE]}>
        <boxGeometry args={[0.5, 0.5, 0.5]} />
        <meshBasicMaterial color="red" />
      </mesh>
    </group>
  );
}

// --- Car Component ---

function Car({ x, y, rotation, id, color }: { x: number, y: number, rotation: number, id: string, color: string }) {
  // Use the convertible car model
  const { scene } = useGLTF("/assets/models/car-convertible.glb");
  
  // Clone scene for each car instance
  const clonedScene = useMemo(() => {
    const s = scene.clone(true);
    
    // Apply color to the car body
    s.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        // We clone the material so we don't affect other cars
        const mat = mesh.material as THREE.MeshStandardMaterial;
        const clonedMat = mat.clone();
        
        // Tint the car
        clonedMat.color.set(color);
        mesh.material = clonedMat;
      }
    });

    return s;
  }, [scene, color]);

  const position: [number, number, number] = [x * CELL_SIZE, 0.2, y * CELL_SIZE];

  return (
    <group position={position}>
      <primitive 
        object={clonedScene} 
        scale={[1.5, 1.5, 1.5]} 
        rotation={[0, rotation, 0]} 
      />
      {/* ID Label */}
      <Html position={[0, 2, 0]} center>
        <div style={{ 
          background: 'rgba(0,0,0,0.6)', 
          color: 'white', 
          padding: '2px 4px', 
          borderRadius: '4px',
          fontSize: '10px',
          fontFamily: 'monospace'
        }}>
          {id.slice(0, 3)}
        </div>
      </Html>
    </group>
  );
}

function Loader() {
  return (
    <Html center>
      <div style={{ color: 'white', background: 'rgba(0,0,0,0.8)', padding: '10px', borderRadius: '5px' }}>
        Loading Simulation...
      </div>
    </Html>
  );
}

function SceneContent({ grid, timesteps, currentStepIndex, stepProgress }: { grid: GridDTO, timesteps: Timestep[], currentStepIndex: number, stepProgress: number }) {
  const texture = useTexture("/assets/models/Textures/colormap.png");
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.flipY = false;

  const currentStep = timesteps[currentStepIndex];
  
  // Identify cars that were present at t=0
  const initialCarIds = useMemo(() => {
    if (!timesteps || timesteps.length === 0) return new Set<string>();
    return new Set(Object.keys(timesteps[0].cars || {}));
  }, [timesteps]);
  
  // Keep track of car rotations to handle stops or lack of movement data
  const carRotations = useRef<Record<string, number>>({});

  return (
    <group>
      {/* Static Grid */}
      {grid.cells.map((cell) => {
         const key = `${cell.x}-${cell.y}`;
         const props = { x: cell.x, y: cell.y, texture };

         switch (cell.type) {
           case "WALL": return <Wall key={key} {...props} />;
           case "ROAD": return <Road key={key} {...props} />;
           case "PARKING": return <Parking key={key} {...props} />;
           case "ENTRY": return <Entry key={key} {...props} gridWidth={grid.width} gridHeight={grid.height} />;
           case "EXIT": return <Exit key={key} {...props} gridWidth={grid.width} gridHeight={grid.height} />;
           default: return null;
         }
      })}

      {/* Dynamic Cars */}
      {currentStep && currentStep.cars && Object.entries(currentStep.cars).map(([id, [x, y]]) => {
        // Calculate Interpolated Position
        let interpX = x;
        let interpY = y;

        // Try to look ahead (current -> next)
        const nextStep = timesteps[currentStepIndex + 1];
        let dx = 0;
        let dy = 0;

        if (nextStep && nextStep.cars && nextStep.cars[id]) {
            const [nx, ny] = nextStep.cars[id];
            dx = nx - x;
            dy = ny - y;
            
            // Linear Interpolation
            interpX = x + dx * stepProgress;
            interpY = y + dy * stepProgress;
        } 
        
        // If no future movement, look behind (prev -> current) for rotation only
        if (dx === 0 && dy === 0 && currentStepIndex > 0) {
            const prevStep = timesteps[currentStepIndex - 1];
            if (prevStep && prevStep.cars && prevStep.cars[id]) {
                const [px, py] = prevStep.cars[id];
                dx = x - px;
                dy = y - py;
            }
        }

        // Calculate Rotation
        let rotation = carRotations.current[id] ?? Math.PI; // Default

        if (dx !== 0 || dy !== 0) {
            // We need to offset by PI/2 to align with the observed model orientation:
            rotation = Math.atan2(dx, dy) + Math.PI / 2; 
            carRotations.current[id] = rotation;
        }

        // Determine Color
        const color = initialCarIds.has(id) ? "red" : "yellow";

        return <Car key={id} id={id} x={interpX} y={interpY} rotation={rotation} color={color} />;
      })}
    </group>
  );
}

// Preload
useGLTF.preload("/assets/models/floor.glb");
useGLTF.preload("/assets/models/wall-doorway-garage.glb");
useGLTF.preload("/assets/models/car-convertible.glb");
useTexture.preload("/assets/models/Textures/colormap.png");

export default function Simulation3D({ grid, timesteps, currentStepIndex, stepProgress }: Simulation3DProps) {
  console.log("Simulation3D rendering", { gridWidth: grid?.width, gridHeight: grid?.height, step: currentStepIndex });

  if (!grid) {
    console.error("Simulation3D: No grid provided");
    return null;
  }

  const centerX = (grid.width * CELL_SIZE) / 2;
  const centerZ = (grid.height * CELL_SIZE) / 2;

  // Camera looking from top-down
  const cameraPosition: [number, number, number] = [centerX, 40, centerZ + 20];

  return (
    <ErrorBoundary fallback={<div style={{color:'red', padding:'20px'}}>Error loading 3D Scene. Check console.</div>}>
      <div style={{ width: "100%", height: "100%", background: "transparent" }}>
        <Canvas 
          dpr={[1, 1.5]} 
          camera={{ position: cameraPosition, fov: 40 }}
          style={{ width: '100%', height: '100%' }}
        >
          {/* Simple Lighting */}
          <ambientLight intensity={0.8} />
          <directionalLight position={[50, 50, 25]} intensity={1} />
          
          <Suspense fallback={<Loader />}>
            <SceneContent grid={grid} timesteps={timesteps} currentStepIndex={currentStepIndex} stepProgress={stepProgress} />
            
            {/* Ground Plane - Removed opaque plane to let CSS background show through */}
            {/* <mesh rotation={[-Math.PI / 2, 0, 0]} position={[centerX, -0.1, centerZ]}>
              <planeGeometry args={[100, 100]} />
              <meshBasicMaterial color="#333" />
            </mesh> */}
          </Suspense>
          
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
