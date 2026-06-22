import { RoundedBox } from "@react-three/drei";

// A themed workstation for each role agent. The agent stands at the station
// (local origin, facing +z / the camera); the desk + props sit behind it so both
// the robot's face and its gear are visible from the isometric camera.
export function AgentDesk({ role, position, color }: { role: string; position: [number, number, number]; color: string }) {
  return (
    <group position={position}>
      <DeskBase />
      {role === "developer" && <DeveloperDesk color={color} />}
      {role === "designer" && <DesignerDesk color={color} />}
      {role === "planner" && <PlannerDesk color={color} />}
      {role === "reviewer" && <ReviewerDesk color={color} />}
      {role === "tester" && <TesterDesk color={color} />}
      {role === "deployer" && <DeployerDesk color={color} />}
      {role === "generic" && <GenericDesk color={color} />}
    </group>
  );
}

// ---- Generic: a tidy desk with a laptop, mug, papers and a plant ----
function GenericDesk({ color }: { color: string }) {
  return (
    <group>
      {/* laptop */}
      <group position={[-0.1, TOP_Y + 0.05, DESK_Z]}>
        <mesh castShadow><boxGeometry args={[0.42, 0.02, 0.28]} /><meshStandardMaterial color="#1E293B" /></mesh>
        <mesh position={[0, 0.16, -0.13]} rotation={[-1.2, 0, 0]} castShadow>
          <boxGeometry args={[0.42, 0.26, 0.02]} /><meshStandardMaterial color="#0F172A" />
        </mesh>
        <mesh position={[0, 0.16, -0.12]} rotation={[-1.2, 0, 0]}>
          <planeGeometry args={[0.38, 0.22]} /><meshStandardMaterial color="#0B1220" emissive={color} emissiveIntensity={0.4} toneMapped={false} />
        </mesh>
      </group>
      <Mug x={0.45} color={color} />
      <group position={[0.4, TOP_Y + 0.05, DESK_Z - 0.05]}>
        {[0, 1, 2].map((i) => (
          <mesh key={i} position={[i * 0.004, i * 0.01, 0]}><boxGeometry args={[0.22, 0.008, 0.28]} /><meshStandardMaterial color="#F8FAFC" /></mesh>
        ))}
      </group>
      <Plant x={-0.6} z={DESK_Z - 0.12} />
    </group>
  );
}

const DESK_Z = -0.6; // desk sits behind the agent
const TOP_Y = 0.6;

function DeskBase() {
  return (
    <group>
      <RoundedBox args={[1.6, 0.07, 0.72]} radius={0.03} position={[0, TOP_Y, DESK_Z]} castShadow receiveShadow>
        <meshStandardMaterial color="#C8A876" roughness={0.7} />
      </RoundedBox>
      {[-0.72, 0.72].map((x) => (
        <mesh key={x} position={[x, TOP_Y / 2, DESK_Z]} castShadow>
          <boxGeometry args={[0.07, TOP_Y, 0.6]} />
          <meshStandardMaterial color="#A98B5E" roughness={0.75} />
        </mesh>
      ))}
      {/* a small stool tucked to the side (doesn't occlude the agent) */}
      <group position={[0.95, 0, -0.1]}>
        <mesh position={[0, 0.34, 0]} castShadow><cylinderGeometry args={[0.16, 0.16, 0.06, 16]} /><meshStandardMaterial color="#64748B" /></mesh>
        <mesh position={[0, 0.16, 0]}><cylinderGeometry args={[0.025, 0.03, 0.34, 8]} /><meshStandardMaterial color="#334155" /></mesh>
      </group>
    </group>
  );
}

function Monitor({ x, y, w = 0.42, h = 0.27, glow = "#3B82F6" }: { x: number; y: number; w?: number; h?: number; glow?: string }) {
  const z = DESK_Z - 0.28;
  return (
    <group position={[x, y, z]}>
      <mesh position={[0, -h / 2 - 0.07, 0]}><cylinderGeometry args={[0.025, 0.04, 0.12, 8]} /><meshStandardMaterial color="#334155" /></mesh>
      <mesh position={[0, -h / 2 - 0.13, 0.04]}><boxGeometry args={[0.16, 0.02, 0.12]} /><meshStandardMaterial color="#334155" /></mesh>
      <mesh castShadow><boxGeometry args={[w, h, 0.03]} /><meshStandardMaterial color="#0F172A" roughness={0.4} /></mesh>
      <mesh position={[0, 0, 0.017]}><planeGeometry args={[w - 0.04, h - 0.04]} /><meshStandardMaterial color="#0B1220" emissive={glow} emissiveIntensity={0.45} toneMapped={false} /></mesh>
      {[0, 1, 2, 3].map((i) => (
        <mesh key={i} position={[-w * 0.18 + (i % 2) * 0.04, h / 2 - 0.06 - i * 0.045, 0.02]}>
          <planeGeometry args={[(w - 0.1) * (0.45 + (i % 3) * 0.22), 0.014]} />
          <meshBasicMaterial color={glow} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
}

function Keyboard() {
  return (
    <mesh position={[0, TOP_Y + 0.05, DESK_Z + 0.18]} rotation={[-0.05, 0, 0]} castShadow>
      <boxGeometry args={[0.5, 0.03, 0.18]} />
      <meshStandardMaterial color="#1E293B" />
    </mesh>
  );
}

function Mug({ x, color = "#3B82F6" }: { x: number; color?: string }) {
  return (
    <mesh position={[x, TOP_Y + 0.11, DESK_Z + 0.05]} castShadow>
      <cylinderGeometry args={[0.06, 0.05, 0.14, 14]} />
      <meshStandardMaterial color={color} roughness={0.5} />
    </mesh>
  );
}

function Plant({ x, z = DESK_Z - 0.05 }: { x: number; z?: number }) {
  return (
    <group position={[x, TOP_Y + 0.04, z]}>
      <mesh castShadow><cylinderGeometry args={[0.07, 0.06, 0.12, 12]} /><meshStandardMaterial color="#B45309" /></mesh>
      {[[-0.04, 0.16, 0.3], [0.05, 0.18, -0.2], [0, 0.22, 0]].map((p, i) => (
        <mesh key={i} position={[p[0], p[1], 0]} rotation={[0, 0, p[2]]} castShadow>
          <coneGeometry args={[0.06, 0.22, 6]} /><meshStandardMaterial color="#16A34A" />
        </mesh>
      ))}
    </group>
  );
}

// ---- Developer: 4 monitors, keyboard, mug, rubber duck, plant ----
function DeveloperDesk({ color }: { color: string }) {
  return (
    <group>
      <Monitor x={-0.32} y={TOP_Y + 0.34} glow={color} />
      <Monitor x={0.32} y={TOP_Y + 0.34} glow="#22C55E" />
      <Monitor x={-0.32} y={TOP_Y + 0.66} glow="#38BDF8" />
      <Monitor x={0.32} y={TOP_Y + 0.66} glow="#A78BFA" />
      <Keyboard />
      <Mug x={0.58} color={color} />
      {/* rubber duck */}
      <group position={[-0.55, TOP_Y + 0.1, DESK_Z + 0.12]}>
        <mesh castShadow><sphereGeometry args={[0.07, 12, 12]} /><meshStandardMaterial color="#FACC15" /></mesh>
        <mesh position={[0, 0.07, 0]} castShadow><sphereGeometry args={[0.045, 12, 12]} /><meshStandardMaterial color="#FACC15" /></mesh>
        <mesh position={[0.05, 0.08, 0]} rotation={[0, 0, -0.3]}><coneGeometry args={[0.02, 0.06, 8]} /><meshStandardMaterial color="#F97316" /></mesh>
      </group>
      <Plant x={0.62} z={DESK_Z - 0.18} />
    </group>
  );
}

// ---- Designer: colorful pencils, color palette, tilted canvas, art ----
function DesignerDesk({ color }: { color: string }) {
  const pencilColors = ["#EF4444", "#F97316", "#EAB308", "#22C55E", "#3B82F6", "#8B5CF6", "#EC4899", "#14B8A6"];
  return (
    <group>
      {/* tilted drawing tablet / canvas */}
      <group position={[-0.25, TOP_Y + 0.26, DESK_Z - 0.05]} rotation={[-0.5, 0, 0]}>
        <mesh castShadow><boxGeometry args={[0.6, 0.44, 0.03]} /><meshStandardMaterial color="#0F172A" /></mesh>
        <mesh position={[0, 0, 0.02]}><planeGeometry args={[0.56, 0.4]} /><meshStandardMaterial color="#FAFAF9" emissive={color} emissiveIntensity={0.12} /></mesh>
        {/* a colorful scribble */}
        {[["#F43F5E", -0.1, 0.08], ["#3B82F6", 0.08, -0.04], ["#22C55E", -0.04, -0.1]].map((s, i) => (
          <mesh key={i} position={[s[1] as number, s[2] as number, 0.025]}><circleGeometry args={[0.07, 16]} /><meshBasicMaterial color={s[0] as string} /></mesh>
        ))}
      </group>
      {/* cup full of colorful pencils */}
      <group position={[0.45, TOP_Y + 0.12, DESK_Z + 0.05]}>
        <mesh castShadow><cylinderGeometry args={[0.09, 0.08, 0.18, 14]} /><meshStandardMaterial color={color} /></mesh>
        {pencilColors.map((c, i) => {
          const a = (i / pencilColors.length) * Math.PI * 2;
          return (
            <mesh key={i} position={[Math.cos(a) * 0.04, 0.16, Math.sin(a) * 0.04]} rotation={[Math.sin(a) * 0.25, 0, -Math.cos(a) * 0.25]} castShadow>
              <cylinderGeometry args={[0.012, 0.012, 0.26, 6]} /><meshStandardMaterial color={c} />
            </mesh>
          );
        })}
      </group>
      {/* color palette swatches */}
      <group position={[0.2, TOP_Y + 0.045, DESK_Z + 0.2]} rotation={[-Math.PI / 2, 0, 0]}>
        {["#EF4444", "#F59E0B", "#22C55E", "#3B82F6", "#8B5CF6"].map((c, i) => (
          <mesh key={i} position={[(i - 2) * 0.09, 0, 0]}><boxGeometry args={[0.08, 0.08, 0.02]} /><meshStandardMaterial color={c} /></mesh>
        ))}
      </group>
      <Plant x={-0.62} z={DESK_Z - 0.15} />
    </group>
  );
}

// ---- Planner: sticky-note board, calendar, gantt bars, pen cup ----
function PlannerDesk({ color }: { color: string }) {
  const sticky = ["#FEF3C7", "#DCFCE7", "#FCE7F3", "#DBEAFE", "#EDE9FE", "#FEF3C7"];
  return (
    <group>
      {/* cork/sticky board standing on the desk */}
      <group position={[-0.3, TOP_Y + 0.42, DESK_Z - 0.02]}>
        <mesh castShadow><boxGeometry args={[0.66, 0.5, 0.03]} /><meshStandardMaterial color="#A16207" /></mesh>
        {sticky.map((c, i) => (
          <mesh key={i} position={[-0.18 + (i % 3) * 0.18, 0.12 - Math.floor(i / 3) * 0.18, 0.02]} rotation={[0, 0, (i % 2 ? 1 : -1) * 0.12]}>
            <planeGeometry args={[0.13, 0.13]} /><meshStandardMaterial color={c} />
          </mesh>
        ))}
      </group>
      {/* desk calendar */}
      <group position={[0.4, TOP_Y + 0.09, DESK_Z + 0.02]}>
        <mesh castShadow><boxGeometry args={[0.26, 0.18, 0.03]} /><meshStandardMaterial color="#fff" /></mesh>
        <mesh position={[0, 0.07, 0.02]}><planeGeometry args={[0.26, 0.05]} /><meshStandardMaterial color={color} /></mesh>
        {[0, 1, 2, 3].map((r) => [0, 1, 2, 3, 4].map((cc) => (
          <mesh key={`${r}-${cc}`} position={[-0.1 + cc * 0.05, 0.02 - r * 0.035, 0.02]}><planeGeometry args={[0.03, 0.022]} /><meshBasicMaterial color="#CBD5E1" /></mesh>
        )))}
      </group>
      {/* gantt bars on the desktop */}
      <group position={[0.4, TOP_Y + 0.04, DESK_Z + 0.22]} rotation={[-Math.PI / 2, 0, 0]}>
        {["#0EA5E9", "#22C55E", "#F59E0B"].map((c, i) => (
          <mesh key={i} position={[(i - 1) * 0.02, -i * 0.06, 0]}><boxGeometry args={[0.24 - i * 0.05, 0.04, 0.01]} /><meshStandardMaterial color={c} /></mesh>
        ))}
      </group>
      <Mug x={0.62} color={color} />
    </group>
  );
}

// ---- Reviewer: diff monitor, magnifier, paper stack, red stamp ----
function ReviewerDesk({ color }: { color: string }) {
  return (
    <group>
      <Monitor x={-0.2} y={TOP_Y + 0.4} w={0.5} h={0.32} glow="#EF4444" />
      {/* magnifying glass */}
      <group position={[0.4, TOP_Y + 0.12, DESK_Z + 0.06]} rotation={[-0.6, 0, 0.4]}>
        <mesh><torusGeometry args={[0.09, 0.015, 10, 24]} /><meshStandardMaterial color="#334155" metalness={0.6} /></mesh>
        <mesh><circleGeometry args={[0.08, 20]} /><meshStandardMaterial color="#BAE6FD" transparent opacity={0.5} /></mesh>
        <mesh position={[0.02, -0.16, 0]} rotation={[0, 0, 0.7]}><cylinderGeometry args={[0.016, 0.016, 0.16, 8]} /><meshStandardMaterial color="#1E293B" /></mesh>
      </group>
      {/* stacked papers */}
      <group position={[0.5, TOP_Y + 0.06, DESK_Z - 0.05]}>
        {[0, 1, 2, 3].map((i) => (
          <mesh key={i} position={[i * 0.004, i * 0.012, 0]} rotation={[0, (i % 2 ? 1 : -1) * 0.04, 0]}><boxGeometry args={[0.24, 0.008, 0.3]} /><meshStandardMaterial color="#F8FAFC" /></mesh>
        ))}
      </group>
      {/* red approval stamp */}
      <group position={[-0.55, TOP_Y + 0.1, DESK_Z + 0.1]}>
        <mesh castShadow><cylinderGeometry args={[0.07, 0.07, 0.06, 16]} /><meshStandardMaterial color={color} /></mesh>
        <mesh position={[0, 0.09, 0]}><cylinderGeometry args={[0.02, 0.02, 0.12, 8]} /><meshStandardMaterial color="#7F1D1D" /></mesh>
        <mesh position={[0, 0.16, 0]}><sphereGeometry args={[0.04, 10, 10]} /><meshStandardMaterial color="#7F1D1D" /></mesh>
      </group>
    </group>
  );
}

// ---- Tester: beakers, phone + tablet, bug jar, pass/fail signs ----
function TesterDesk({ color }: { color: string }) {
  return (
    <group>
      {/* beakers with colored liquid */}
      {[["#22C55E", -0.5, 0.13], ["#F59E0B", -0.32, 0.16], ["#3B82F6", -0.14, 0.11]].map((b, i) => (
        <group key={i} position={[b[1] as number, TOP_Y + 0.04, DESK_Z + 0.02]}>
          <mesh castShadow><cylinderGeometry args={[0.05, 0.06, b[2] as number, 14]} /><meshStandardMaterial color="#E0F2FE" transparent opacity={0.45} /></mesh>
          <mesh position={[0, -(b[2] as number) / 2 + 0.03, 0]}><cylinderGeometry args={[0.048, 0.058, 0.06, 14]} /><meshStandardMaterial color={b[0] as string} emissive={b[0] as string} emissiveIntensity={0.3} toneMapped={false} /></mesh>
        </group>
      ))}
      {/* phone + tablet on stands */}
      <mesh position={[0.2, TOP_Y + 0.17, DESK_Z - 0.05]} rotation={[-0.18, 0, 0]} castShadow><boxGeometry args={[0.16, 0.3, 0.02]} /><meshStandardMaterial color="#0F172A" emissive={color} emissiveIntensity={0.25} toneMapped={false} /></mesh>
      <mesh position={[0.46, TOP_Y + 0.21, DESK_Z - 0.06]} rotation={[-0.18, 0, 0]} castShadow><boxGeometry args={[0.32, 0.4, 0.02]} /><meshStandardMaterial color="#0F172A" emissive="#2DD4BF" emissiveIntensity={0.25} toneMapped={false} /></mesh>
      {/* bug jar */}
      <group position={[0.62, TOP_Y + 0.11, DESK_Z + 0.12]}>
        <mesh><cylinderGeometry args={[0.07, 0.07, 0.16, 16]} /><meshStandardMaterial color="#DCFCE7" transparent opacity={0.35} /></mesh>
        <mesh position={[0, -0.02, 0]}><sphereGeometry args={[0.04, 10, 10]} /><meshStandardMaterial color="#7C2D12" /></mesh>
      </group>
      {/* pass / fail signs */}
      <mesh position={[-0.58, TOP_Y + 0.16, DESK_Z + 0.1]}><planeGeometry args={[0.12, 0.12]} /><meshBasicMaterial color="#22C55E" /></mesh>
    </group>
  );
}

// ---- Deployer: server rack, rocket, cloud, big lever ----
function DeployerDesk({ color }: { color: string }) {
  return (
    <group>
      {/* server rack */}
      <group position={[-0.45, TOP_Y + 0.3, DESK_Z - 0.02]}>
        <mesh castShadow><boxGeometry args={[0.3, 0.5, 0.22]} /><meshStandardMaterial color="#1E293B" metalness={0.4} roughness={0.5} /></mesh>
        {[0, 1, 2, 3, 4].map((r) => (
          <group key={r} position={[0, 0.18 - r * 0.09, 0.12]}>
            <mesh><boxGeometry args={[0.26, 0.06, 0.01]} /><meshStandardMaterial color="#334155" /></mesh>
            {[0, 1, 2].map((l) => (
              <mesh key={l} position={[-0.08 + l * 0.05, 0, 0.008]}><circleGeometry args={[0.012, 8]} /><meshBasicMaterial color={["#22C55E", "#EAB308", "#22C55E"][l]} toneMapped={false} /></mesh>
            ))}
          </group>
        ))}
      </group>
      {/* rocket */}
      <group position={[0.3, TOP_Y + 0.2, DESK_Z + 0.02]}>
        <mesh castShadow><cylinderGeometry args={[0.06, 0.06, 0.26, 14]} /><meshStandardMaterial color="#F1F5F9" /></mesh>
        <mesh position={[0, 0.18, 0]}><coneGeometry args={[0.06, 0.12, 14]} /><meshStandardMaterial color={color} /></mesh>
        {[[-0.07, 0.07], [0.07, -0.07]].map((f, i) => (
          <mesh key={i} position={[f[0], -0.12, f[1]]} rotation={[0, i * Math.PI / 2, 0]}><coneGeometry args={[0.04, 0.1, 4]} /><meshStandardMaterial color="#EF4444" /></mesh>
        ))}
      </group>
      {/* cloud */}
      <group position={[0.55, TOP_Y + 0.26, DESK_Z - 0.08]}>
        {[[0, 0, 0.07], [0.08, 0.02, 0.06], [-0.08, 0.01, 0.055]].map((c, i) => (
          <mesh key={i} position={[c[0], c[1], 0]}><sphereGeometry args={[c[2] as number, 12, 12]} /><meshStandardMaterial color="#E2E8F0" /></mesh>
        ))}
      </group>
      {/* big deploy lever */}
      <group position={[0.5, TOP_Y + 0.06, DESK_Z + 0.2]}>
        <mesh><boxGeometry args={[0.12, 0.06, 0.1]} /><meshStandardMaterial color="#334155" /></mesh>
        <mesh position={[0, 0.1, 0]} rotation={[0.5, 0, 0]}><cylinderGeometry args={[0.015, 0.015, 0.16, 8]} /><meshStandardMaterial color="#94A3B8" metalness={0.6} /></mesh>
        <mesh position={[0.04, 0.17, 0.06]}><sphereGeometry args={[0.03, 10, 10]} /><meshStandardMaterial color="#EF4444" emissive="#EF4444" emissiveIntensity={0.5} toneMapped={false} /></mesh>
      </group>
    </group>
  );
}
