import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html, RoundedBox } from "@react-three/drei";
import * as THREE from "three";
import type { Primitive } from "../../types";
import { useStore } from "../../store";

// Each primitive is a recognizable 3D object so its function is readable at a
// glance (spec 7.11). Active primitives intensify their edge glow.
export function Primitive3D({ prim }: { prim: Primitive }) {
  const select = useStore((s) => s.select);
  const glow = useRef<THREE.Mesh>(null);
  const [x, , z] = prim.transform.position;
  const color = prim.appearance.color;

  useFrame((state) => {
    if (glow.current) {
      const mat = glow.current.material as THREE.MeshStandardMaterial;
      const base = prim.active ? 0.9 : prim.appearance.edgeGlow ? 0.3 : 0;
      mat.emissiveIntensity = base + (prim.active ? Math.sin(state.clock.elapsedTime * 5) * 0.3 : 0);
    }
  });

  return (
    <group position={[x, 0, z]} onClick={(e) => { e.stopPropagation(); select("primitive", prim.id); }}>
      <Geometry prim={prim} glowRef={glow} color={color} />
      <Html position={[0, geomHeight(prim.type) + 0.3, 0]} center style={{ pointerEvents: "none" }}>
        <div style={{
          font: "500 10px var(--font-ui)", color: "var(--text-muted)",
          background: "rgba(255,255,255,.7)", padding: "0 6px", borderRadius: 6, whiteSpace: "nowrap",
        }}>{prim.name}</div>
      </Html>
    </group>
  );
}

function geomHeight(type: string): number {
  return { Desk: 0.55, Vault: 0.9, Whiteboard: 1.4, "Kanban Wall": 1.4, "Security Gate": 1.2, Lounge: 0.5, "Event Stream": 1.6, Terminal: 0.6 }[type] ?? 0.6;
}

function Geometry({ prim, glowRef, color }: { prim: Primitive; glowRef: any; color: string }) {
  const glassMat = (
    <meshStandardMaterial
      ref={glowRef as any}
      color={color}
      emissive={color}
      emissiveIntensity={0.3}
      transparent
      opacity={prim.appearance.opacity}
      roughness={0.1}
      metalness={0.1}
      toneMapped={false}
    />
  );

  switch (prim.type) {
    case "Desk":
      return (
        <group>
          <RoundedBox args={[1.3, 0.08, 0.7]} radius={0.03} position={[0, 0.5, 0]} castShadow receiveShadow>
            <meshStandardMaterial color="#C8A876" roughness={0.7} />
          </RoundedBox>
          {[-0.55, 0.55].map((dx) => (
            <mesh key={dx} position={[dx, 0.25, 0.25]}><boxGeometry args={[0.06, 0.5, 0.06]} /><meshStandardMaterial color="#A98B5E" /></mesh>
          ))}
          {/* monitor */}
          <mesh ref={glowRef} position={[0, 0.78, -0.2]}><boxGeometry args={[0.5, 0.32, 0.03]} /><meshStandardMaterial color="#1E293B" emissive={color} emissiveIntensity={0.3} toneMapped={false} /></mesh>
          {/* mug + plant accents */}
          <mesh position={[0.4, 0.6, 0.1]}><cylinderGeometry args={[0.05, 0.05, 0.1, 12]} /><meshStandardMaterial color="#3B82F6" /></mesh>
        </group>
      );
    case "Vault":
      return (
        <group>
          <RoundedBox ref={glowRef} args={[0.9, 0.9, 0.8]} radius={0.06} position={[0, 0.45, 0]} castShadow>
            <meshStandardMaterial color="#94A3B8" emissive={color} emissiveIntensity={0.3} roughness={0.35} metalness={0.7} toneMapped={false} />
          </RoundedBox>
          <mesh position={[0, 0.45, 0.42]}><cylinderGeometry args={[0.16, 0.16, 0.06, 24]} /><meshStandardMaterial color="#CBD5E1" metalness={0.9} roughness={0.2} /></mesh>
        </group>
      );
    case "Whiteboard":
    case "Kanban Wall":
      return (
        <group>
          <mesh ref={glowRef} position={[0, 1.0, 0]} castShadow><boxGeometry args={[1.7, 1.2, 0.05]} />{glassMat}</mesh>
          {prim.type === "Kanban Wall" &&
            [0, 1, 2, 3].map((c) =>
              [0, 1].map((r) => (
                <mesh key={`${c}-${r}`} position={[-0.6 + c * 0.4, 1.25 - r * 0.35, 0.04]}>
                  <boxGeometry args={[0.28, 0.22, 0.02]} />
                  <meshStandardMaterial color={["#FEF3C7", "#DCFCE7", "#FCE7F3", "#DBEAFE"][c]} />
                </mesh>
              ))
            )}
          {/* posts */}
          {[-0.85, 0.85].map((dx) => (<mesh key={dx} position={[dx, 0.5, 0]}><cylinderGeometry args={[0.04, 0.04, 1, 12]} /><meshStandardMaterial color="#94A3B8" metalness={0.6} /></mesh>))}
        </group>
      );
    case "Security Gate":
      return (
        <group>
          {[-0.5, 0.5].map((dx) => (<mesh key={dx} position={[dx, 0.6, 0]} castShadow><boxGeometry args={[0.18, 1.2, 0.18]} /><meshStandardMaterial color="#64748B" metalness={0.7} roughness={0.3} /></mesh>))}
          <mesh ref={glowRef} position={[0, 0.5, 0]} rotation={[0, 0.3, 0]}><boxGeometry args={[0.9, 0.06, 0.06]} /><meshStandardMaterial color="#94A3B8" emissive={prim.active ? "#F59E0B" : "#22C55E"} emissiveIntensity={0.6} toneMapped={false} /></mesh>
          <mesh position={[0, 1.25, 0]}><sphereGeometry args={[0.08, 16, 16]} /><meshStandardMaterial color={prim.active ? "#F59E0B" : "#22C55E"} emissive={prim.active ? "#F59E0B" : "#22C55E"} emissiveIntensity={1.2} toneMapped={false} /></mesh>
        </group>
      );
    case "Lounge":
      return (
        <group>
          <RoundedBox args={[1.0, 0.3, 0.7]} radius={0.1} position={[0, 0.2, 0]} castShadow><meshStandardMaterial color="#C7B8F0" roughness={0.9} /></RoundedBox>
          <RoundedBox args={[1.0, 0.4, 0.15]} radius={0.08} position={[0, 0.45, -0.27]}><meshStandardMaterial color="#B7A6E8" roughness={0.9} /></RoundedBox>
          <mesh position={[0.6, 0.35, 0.3]}><coneGeometry args={[0.12, 0.4, 8]} /><meshStandardMaterial color="#22C55E" /></mesh>
        </group>
      );
    case "Event Stream":
      return <mesh ref={glowRef} position={[0, 0.9, 0]} castShadow><boxGeometry args={[0.9, 1.6, 0.05]} />{glassMat}</mesh>;
    case "Terminal":
      return <RoundedBox ref={glowRef} args={[0.9, 0.6, 0.05]} radius={0.03} position={[0, 0.55, 0]} castShadow><meshStandardMaterial color="#0F172A" emissive={color} emissiveIntensity={0.3} transparent opacity={0.9} toneMapped={false} /></RoundedBox>;
    default:
      return <RoundedBox ref={glowRef} args={[0.7, 0.7, 0.7]} radius={0.06} position={[0, 0.35, 0]}>{glassMat}</RoundedBox>;
  }
}
