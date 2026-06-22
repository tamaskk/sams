import { Html, RoundedBox } from "@react-three/drei";

// A placeable office decoration. Rendered at [x, 0, z]; shows a delete button
// while the layout editor is on.
export function Decor3D({ type, position, editing, onRemove, onPointerDown }: {
  type: string;
  position: [number, number, number];
  editing: boolean;
  onRemove: () => void;
  onPointerDown: (e: any) => void;
}) {
  return (
    <group
      position={position}
      onPointerDown={onPointerDown}
      onPointerOver={() => { if (editing) document.body.style.cursor = "grab"; }}
      onPointerOut={() => { document.body.style.cursor = "auto"; }}
    >
      {type === "plant" && <PlantDecor />}
      {type === "tree" && <TreeDecor />}
      {type === "lamp" && <LampDecor />}
      {type === "sofa" && <SofaDecor />}
      {type === "rug" && <RugDecor />}
      {type === "cabinet" && <CabinetDecor />}
      {type === "water" && <WaterDecor />}
      {editing && (
        <Html position={[0, 1.4, 0]} center>
          <button
            onClick={(e) => { e.stopPropagation(); onRemove(); }}
            onPointerDown={(e) => e.stopPropagation()}
            style={{
              width: 22, height: 22, borderRadius: 11, border: "none", cursor: "pointer",
              background: "#EF4444", color: "#fff", fontWeight: 700, fontSize: 15, lineHeight: "22px",
              padding: 0, boxShadow: "0 2px 6px rgba(0,0,0,.3)",
            }}
            aria-label="Remove decoration"
          >×</button>
        </Html>
      )}
    </group>
  );
}

function PlantDecor() {
  return (
    <group>
      <mesh position={[0, 0.18, 0]} castShadow><cylinderGeometry args={[0.18, 0.14, 0.36, 16]} /><meshStandardMaterial color="#475569" /></mesh>
      {[[0, 0.7, 0], [0.12, 0.62, 0.4], [-0.13, 0.6, -0.35], [0.05, 0.66, 0.9]].map((p, i) => (
        <mesh key={i} position={[p[0], p[1], 0]} rotation={[0, 0, p[2]]} castShadow>
          <coneGeometry args={[0.14, 0.7, 6]} /><meshStandardMaterial color={["#15803D", "#16A34A", "#22C55E", "#16A34A"][i]} />
        </mesh>
      ))}
    </group>
  );
}

function TreeDecor() {
  return (
    <group>
      <mesh position={[0, 0.2, 0]} castShadow><cylinderGeometry args={[0.22, 0.18, 0.4, 16]} /><meshStandardMaterial color="#64748B" /></mesh>
      <mesh position={[0, 0.55, 0]} castShadow><cylinderGeometry args={[0.05, 0.06, 0.5, 8]} /><meshStandardMaterial color="#92400E" /></mesh>
      {[[0, 1.0, 0.34], [0, 1.25, 0.28], [0, 1.45, 0.2]].map((c, i) => (
        <mesh key={i} position={[c[0], c[1], 0]} castShadow><sphereGeometry args={[c[2] as number, 12, 12]} /><meshStandardMaterial color={["#166534", "#15803D", "#16A34A"][i]} /></mesh>
      ))}
    </group>
  );
}

function LampDecor() {
  return (
    <group>
      <mesh position={[0, 0.03, 0]} castShadow><cylinderGeometry args={[0.18, 0.2, 0.06, 16]} /><meshStandardMaterial color="#334155" /></mesh>
      <mesh position={[0, 0.7, 0]}><cylinderGeometry args={[0.02, 0.02, 1.3, 8]} /><meshStandardMaterial color="#475569" /></mesh>
      <mesh position={[0, 1.4, 0]} castShadow><coneGeometry args={[0.22, 0.26, 20, 1, true]} /><meshStandardMaterial color="#F8FAFC" side={2} /></mesh>
      <mesh position={[0, 1.36, 0]}><sphereGeometry args={[0.07, 12, 12]} /><meshStandardMaterial color="#FFFBEB" emissive="#FDE68A" emissiveIntensity={1.4} toneMapped={false} /></mesh>
      <pointLight position={[0, 1.3, 0]} color="#FFF3D6" intensity={2} distance={4} decay={2} />
    </group>
  );
}

function SofaDecor() {
  return (
    <group>
      <RoundedBox args={[1.3, 0.28, 0.6]} radius={0.08} position={[0, 0.3, 0]} castShadow><meshStandardMaterial color="#C7B8E8" roughness={0.9} /></RoundedBox>
      <RoundedBox args={[1.3, 0.4, 0.16]} radius={0.07} position={[0, 0.5, -0.25]} castShadow><meshStandardMaterial color="#B7A6DE" roughness={0.9} /></RoundedBox>
      {[-0.62, 0.62].map((x) => (
        <RoundedBox key={x} args={[0.14, 0.4, 0.6]} radius={0.06} position={[x, 0.42, 0]} castShadow><meshStandardMaterial color="#B7A6DE" roughness={0.9} /></RoundedBox>
      ))}
    </group>
  );
}

function RugDecor() {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0]} receiveShadow>
        <circleGeometry args={[0.95, 40]} /><meshStandardMaterial color="#FDE68A" roughness={0.95} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <ringGeometry args={[0.6, 0.7, 40]} /><meshBasicMaterial color="#F59E0B" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <circleGeometry args={[0.3, 32]} /><meshBasicMaterial color="#FB923C" />
      </mesh>
    </group>
  );
}

function CabinetDecor() {
  return (
    <group>
      <RoundedBox args={[0.7, 0.9, 0.5]} radius={0.03} position={[0, 0.45, 0]} castShadow><meshStandardMaterial color="#94A3B8" metalness={0.3} roughness={0.6} /></RoundedBox>
      {[0.66, 0.36].map((y, i) => (
        <group key={i} position={[0, y, 0.26]}>
          <mesh><boxGeometry args={[0.6, 0.24, 0.02]} /><meshStandardMaterial color="#CBD5E1" /></mesh>
          <mesh position={[0, 0, 0.02]}><boxGeometry args={[0.16, 0.03, 0.02]} /><meshStandardMaterial color="#475569" /></mesh>
        </group>
      ))}
      <mesh position={[0, 0.95, 0]}><boxGeometry args={[0.72, 0.04, 0.52]} /><meshStandardMaterial color="#64748B" /></mesh>
    </group>
  );
}

function WaterDecor() {
  return (
    <group>
      <mesh position={[0, 0.45, 0]} castShadow><boxGeometry args={[0.36, 0.9, 0.36]} /><meshStandardMaterial color="#E2E8F0" /></mesh>
      <mesh position={[0, 1.1, 0]}><cylinderGeometry args={[0.16, 0.18, 0.36, 16]} /><meshStandardMaterial color="#7DD3FC" transparent opacity={0.7} /></mesh>
      <mesh position={[0, 0.5, 0.19]}><boxGeometry args={[0.16, 0.1, 0.02]} /><meshStandardMaterial color="#0EA5E9" /></mesh>
    </group>
  );
}
