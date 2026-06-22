import { RoundedBox } from "@react-three/drei";

// The office shell: a warm wood floor, two walls with windows, a rug, plants,
// pendant lamps and a few decorations — so the space reads as a real office.
export function Office({ width, depth }: { width: number; depth: number }) {
  const cx = width / 2;
  const cz = depth / 2;
  const planks = Array.from({ length: Math.ceil(depth / 0.6) }, (_, i) => i * 0.6);

  return (
    <group>
      {/* floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[cx, 0, cz]} receiveShadow>
        <planeGeometry args={[width + 2, depth + 2]} />
        <meshStandardMaterial color="#E7D2B0" roughness={0.85} />
      </mesh>
      {/* plank seams */}
      {planks.map((z) => (
        <mesh key={z} rotation={[-Math.PI / 2, 0, 0]} position={[cx, 0.011, z]}>
          <planeGeometry args={[width + 2, 0.015]} />
          <meshBasicMaterial color="#C9AD82" transparent opacity={0.5} />
        </mesh>
      ))}
      {/* soft rug under the workstations */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[cx, 0.02, cz - 0.3]}>
        <planeGeometry args={[width * 0.8, depth * 0.62]} />
        <meshStandardMaterial color="#EEF2F9" roughness={0.95} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[cx, 0.025, cz - 0.3]}>
        <ringGeometry args={[width * 0.32, width * 0.34, 48]} />
        <meshBasicMaterial color="#C7D2FE" />
      </mesh>

      {/* two walls (back: z=0, left: x=0) */}
      <Wall position={[cx, 1.5, -0.15]} size={[width + 0.3, 3, 0.3]} />
      <Wall position={[-0.15, 1.5, cz]} size={[0.3, 3, depth + 0.3]} />
      {/* baseboards */}
      <mesh position={[cx, 0.08, -0.02]}><boxGeometry args={[width, 0.16, 0.08]} /><meshStandardMaterial color="#CBD5E1" /></mesh>
      <mesh position={[-0.02, 0.08, cz]}><boxGeometry args={[0.08, 0.16, depth]} /><meshStandardMaterial color="#CBD5E1" /></mesh>

      {/* windows distributed along the back wall (z=0) and left wall (x=0) */}
      {spread(width, clampi(Math.round(width / 4.5), 2, 5), 1.8).map((x, i) => (
        <Window key={`wz${i}`} position={[x, 1.7, 0.02]} facing="z" />
      ))}
      {spread(depth, clampi(Math.round(depth / 4.5), 2, 5), 1.8).map((z, i) => (
        <Window key={`wx${i}`} position={[0.02, 1.7, z]} facing="x" />
      ))}

      {/* wall clock + framed posters */}
      <group position={[cx, 2.35, 0.04]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.28, 0.28, 0.06, 24]} /><meshStandardMaterial color="#fff" /></mesh>
        <mesh position={[0, 0, 0.04]}><circleGeometry args={[0.25, 24]} /><meshStandardMaterial color="#F8FAFC" /></mesh>
        <mesh position={[0, 0.06, 0.05]}><boxGeometry args={[0.018, 0.13, 0.005]} /><meshStandardMaterial color="#0F172A" /></mesh>
        <mesh position={[0.05, 0, 0.05]} rotation={[0, 0, Math.PI / 2]}><boxGeometry args={[0.018, 0.09, 0.005]} /><meshStandardMaterial color="#0F172A" /></mesh>
      </group>
      <Poster position={[cx + 1.0, 1.9, 0.03]} color="#3B82F6" />
      <Poster position={[0.03, 1.9, cz + 0.8]} color="#F43F5E" facing="x" />

      {/* plants in all four corners */}
      {[[0.7, 0.7], [width - 0.7, 0.7], [0.7, depth - 0.7], [width - 0.7, depth - 0.7]].map((p, i) => (
        <FloorPlant key={i} position={[p[0], 0, p[1]]} />
      ))}

      {/* pendant lamps on a grid so the whole room is lit */}
      {spread(width, clampi(Math.round(width / 6), 2, 3), 2.6).flatMap((x) =>
        spread(depth, clampi(Math.round(depth / 6), 2, 3), 2.6).map((z) => (
          <Pendant key={`p${x.toFixed(1)}-${z.toFixed(1)}`} position={[x, 0, z]} />
        ))
      )}
    </group>
  );
}

// Evenly spaced positions within [margin, L-margin] (used for windows + lamps).
function spread(L: number, n: number, margin: number): number[] {
  if (n <= 1) return [L / 2];
  const a = margin, b = L - margin;
  const out: number[] = [];
  for (let i = 0; i < n; i++) out.push(a + (b - a) * (i / (n - 1)));
  return out;
}
function clampi(v: number, lo: number, hi: number): number { return Math.max(lo, Math.min(hi, v)); }

function Wall({ position, size }: { position: [number, number, number]; size: [number, number, number] }) {
  return (
    <mesh position={position} receiveShadow>
      <boxGeometry args={size} />
      <meshStandardMaterial color="#F1F5F9" roughness={0.95} />
    </mesh>
  );
}

function Window({ position, facing }: { position: [number, number, number]; facing: "z" | "x" }) {
  const rot: [number, number, number] = facing === "x" ? [0, Math.PI / 2, 0] : [0, 0, 0];
  return (
    <group position={position} rotation={rot}>
      {/* sky beyond */}
      <mesh position={[0, 0, -0.05]}><planeGeometry args={[1.5, 1.4]} /><meshBasicMaterial color="#BAE6FD" /></mesh>
      <mesh position={[0, 0.45, -0.04]}><planeGeometry args={[1.5, 0.5]} /><meshBasicMaterial color="#E0F2FE" /></mesh>
      {/* glass */}
      <mesh><planeGeometry args={[1.5, 1.4]} /><meshStandardMaterial color="#DBEAFE" transparent opacity={0.25} roughness={0.1} /></mesh>
      {/* frame */}
      {[[0, 0.72, 1.62, 0.08], [0, -0.72, 1.62, 0.08], [-0.78, 0, 0.08, 1.5], [0.78, 0, 0.08, 1.5], [0, 0, 1.5, 0.05], [0, 0, 0.05, 1.4]].map((f, i) => (
        <mesh key={i} position={[f[0], f[1], 0.01]}><planeGeometry args={[f[2], f[3]]} /><meshStandardMaterial color="#F8FAFC" /></mesh>
      ))}
    </group>
  );
}

function Poster({ position, color, facing = "z" }: { position: [number, number, number]; color: string; facing?: "z" | "x" }) {
  const rot: [number, number, number] = facing === "x" ? [0, Math.PI / 2, 0] : [0, 0, 0];
  return (
    <group position={position} rotation={rot}>
      <mesh><planeGeometry args={[0.7, 0.9]} /><meshStandardMaterial color="#0F172A" /></mesh>
      <mesh position={[0, 0, 0.01]}><planeGeometry args={[0.62, 0.82]} /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.1} /></mesh>
      <mesh position={[0, 0.12, 0.02]}><circleGeometry args={[0.16, 24]} /><meshBasicMaterial color="#fff" transparent opacity={0.85} /></mesh>
    </group>
  );
}

function FloorPlant({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.18, 0]} castShadow><cylinderGeometry args={[0.18, 0.14, 0.36, 16]} /><meshStandardMaterial color="#475569" /></mesh>
      {[[0, 0.7, 0], [0.12, 0.62, 0.4], [-0.13, 0.6, -0.35], [0.05, 0.66, 0.9]].map((p, i) => (
        <mesh key={i} position={[p[0], p[1], 0]} rotation={[0, 0, p[2]]} castShadow>
          <coneGeometry args={[0.14, 0.7, 6]} /><meshStandardMaterial color={["#15803D", "#16A34A", "#22C55E", "#16A34A"][i]} />
        </mesh>
      ))}
    </group>
  );
}

function Pendant({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh position={[0, 2.9, 0]}><cylinderGeometry args={[0.005, 0.005, 0.4, 6]} /><meshStandardMaterial color="#1E293B" /></mesh>
      <mesh position={[0, 2.66, 0]} castShadow><coneGeometry args={[0.22, 0.22, 20, 1, true]} /><meshStandardMaterial color="#0F172A" side={2} /></mesh>
      <mesh position={[0, 2.6, 0]}><sphereGeometry args={[0.08, 12, 12]} /><meshStandardMaterial color="#FFFBEB" emissive="#FDE68A" emissiveIntensity={1.4} toneMapped={false} /></mesh>
      <pointLight position={[0, 2.5, 0]} color="#FFF7E6" intensity={3} distance={5} decay={2} />
    </group>
  );
}
