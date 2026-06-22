import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html, RoundedBox } from "@react-three/drei";
import * as THREE from "three";
import type { AgentMarker } from "../../types";
import { useStore } from "../../store";

// A rounded, matte robot avatar with a glowing "visor" face and a base ring in
// the agent's identity color (spec 7.11). Personality through pose + motion.
const REDUCE = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// Worker movement variety — walk is most common; lob and teleport are surprises.
type WorkerMoveMode = "walk" | "lob" | "teleport";
const WORKER_MOVES: WorkerMoveMode[] = ["walk", "walk", "walk", "walk", "lob", "lob", "teleport"];
function pickWorkerMove(): WorkerMoveMode {
  return WORKER_MOVES[Math.floor(Math.random() * WORKER_MOVES.length)];
}

// Hand-off errand: the finishing agent carries the task to the next agent and
// returns, in one of several styles. Round-trip choreography over ERR_DUR.
const ERR_DUR = 2800;
const easeIO = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
const smooth = (t: number) => t * t * (3 - 2 * t);

interface ETransform { x: number; y: number; z: number; scale: number; spin: number; faceX: number; faceZ: number; carrying: boolean; active: boolean; }

function errandTransform(mode: string, hx: number, hz: number, tox: number, toz: number, et: number): ETransform {
  if (et < 0 || et >= ERR_DUR) return { x: hx, y: 0, z: hz, scale: 1, spin: 0, faceX: hx, faceZ: hz, carrying: false, active: false };
  const p = et / ERR_DUR;
  let leg: "out" | "deliver" | "back", lp: number;
  if (p < 0.44) { leg = "out"; lp = p / 0.44; }
  else if (p < 0.56) { leg = "deliver"; lp = (p - 0.44) / 0.12; }
  else { leg = "back"; lp = (p - 0.56) / 0.44; }
  const ax = leg === "out" ? hx : tox, az = leg === "out" ? hz : toz;
  const bx = leg === "back" ? hx : tox, bz = leg === "back" ? hz : toz;
  const e = mode === "dash" ? easeIO(lp) : mode === "glide" ? smooth(lp) : lp;
  let x = ax + (bx - ax) * e, z = az + (bz - az) * e, y = 0, scale = 1, spin = 0;
  if (leg === "deliver") { x = tox; z = toz; }
  if (mode === "hop" && leg !== "deliver") y = Math.abs(Math.sin(e * Math.PI)) * 0.75;
  if (mode === "spin") spin = p * Math.PI * 10;
  if (mode === "teleport") {
    if (leg === "out") { if (lp < 0.5) { x = hx; z = hz; scale = 1 - lp / 0.5; } else { x = tox; z = toz; scale = (lp - 0.5) / 0.5; } }
    else if (leg === "back") { if (lp < 0.5) { x = tox; z = toz; scale = 1 - lp / 0.5; } else { x = hx; z = hz; scale = (lp - 0.5) / 0.5; } }
    else { x = tox; z = toz; }
  }
  return { x, y, z, scale, spin, faceX: bx, faceZ: bz, carrying: leg !== "back", active: true };
}

export function Agent3D({ agent }: { agent: AgentMarker }) {
  const group = useRef<THREE.Group>(null);
  const ring = useRef<THREE.Mesh>(null);
  const body = useRef<THREE.Group>(null);
  const halo = useRef<THREE.Mesh>(null);
  const orb = useRef<THREE.Mesh>(null);
  const taskOrb = useRef<THREE.Mesh>(null);
  const select = useStore((s) => s.select);
  const selected = useStore((s) => s.selected);
  const isSel = selected?.kind === "agent" && selected.id === agent.id;

  // Latch movement mode each time the target changes.
  const lastTargetRef = useRef<string>("");
  const moveRef = useRef<{
    mode: WorkerMoveMode;
    fromX: number; fromZ: number;
    startTime: number; duration: number;
  } | null>(null);

  const color = agent.color || "#9CA3AF";
  const working = agent.state === "working";
  // Per-agent phase so the fleet breathes out of sync (feels alive, not robotic).
  const phase = (agent.id.charCodeAt(0) + agent.id.length * 13) % 100 / 100 * Math.PI * 2;

  useFrame((state, dt) => {
    if (!group.current) return;
    const [tx, , tz] = agent.target;
    const targetKey = `${tx.toFixed(2)},${tz.toFixed(2)}`;

    let moving = false;
    let faceX = tx, faceZ = tz, carrying = false;

    // --- Hand-off errand: carry the task to the next agent and return. It
    // overrides the normal station movement while active. ---
    const er = agent.errand;
    const tf = er ? errandTransform(REDUCE ? "walk" : er.mode, agent.position[0], agent.position[2], er.to[0], er.to[1], performance.now() - er.t0) : null;

    if (tf && tf.active) {
      group.current.position.set(tf.x, tf.y, tf.z);
      group.current.scale.setScalar(tf.scale);
      faceX = tf.faceX; faceZ = tf.faceZ; carrying = tf.carrying; moving = true;
      lastTargetRef.current = targetKey;
      moveRef.current = null;
    } else {
      // Detect station-target change and pick a movement mode for the journey.
      if (lastTargetRef.current === "") {
        lastTargetRef.current = targetKey;
      } else if (targetKey !== lastTargetRef.current) {
        lastTargetRef.current = targetKey;
        const mode = REDUCE ? "walk" : pickWorkerMove();
        moveRef.current = { mode, fromX: group.current.position.x, fromZ: group.current.position.z,
          startTime: performance.now(), duration: mode === "lob" ? 1800 : mode === "teleport" ? 700 : 0 };
      }
      const mv = moveRef.current;
      if (mv && mv.mode !== "walk") {
        const p = Math.min(1, (performance.now() - mv.startTime) / mv.duration);
        if (mv.mode === "lob") {
          group.current.position.x = mv.fromX + (tx - mv.fromX) * p;
          group.current.position.z = mv.fromZ + (tz - mv.fromZ) * p;
          group.current.position.y = Math.sin(p * Math.PI) * 1.4;
          moving = p < 1;
        } else if (mv.mode === "teleport") {
          if (p < 0.38) group.current.scale.setScalar(Math.max(0, 1 - p / 0.38));
          else if (p < 0.55) { group.current.scale.setScalar(0); group.current.position.x = tx; group.current.position.z = tz; }
          else { group.current.scale.setScalar(Math.min(1, (p - 0.55) / 0.45)); group.current.position.x = tx; group.current.position.z = tz; }
        }
        if (p >= 1) { moveRef.current = null; group.current.scale.setScalar(1); group.current.position.y = 0; }
      } else {
        group.current.scale.setScalar(1);
        group.current.position.x += (tx - group.current.position.x) * Math.min(1, dt * 2.5);
        group.current.position.z += (tz - group.current.position.z) * Math.min(1, dt * 2.5);
        if (group.current.position.y !== 0) group.current.position.y += (0 - group.current.position.y) * Math.min(1, dt * 4);
        moving = Math.abs(tx - group.current.position.x) + Math.abs(tz - group.current.position.z) > 0.05;
      }
    }
    if (taskOrb.current) taskOrb.current.visible = carrying;

    const t = state.clock.elapsedTime;
    const m = REDUCE ? 0 : 1;

    if (ring.current) {
      const mat = ring.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = working ? 0.9 + Math.sin(t * 5) * 0.6 * m : 0.35;
    }
    if (body.current) {
      // Working: energetic bob + slight forward lean. Idle: gentle breathing + sway.
      const bob = working ? 0.36 + Math.sin(t * 6 + phase) * 0.05 * m
                          : 0.36 + Math.sin(t * 1.6 + phase) * 0.018 * m;
      body.current.position.y = bob;
      body.current.rotation.z = (working ? Math.sin(t * 6 + phase) * 0.04 : Math.sin(t * 1.3 + phase) * 0.02) * m;
      body.current.rotation.x = working ? 0.06 * m : 0;
      // face toward the travel direction (the next agent during a hand-off)
      if (moving) body.current.rotation.y = Math.atan2(faceX - group.current.position.x, faceZ - group.current.position.z);
      if (carrying) body.current.rotation.x = -0.12; // lean forward, carrying the task
    }
    // Activity halo + orb above the head — only while working.
    if (halo.current) {
      halo.current.visible = working;
      if (working) { halo.current.rotation.z += dt * 3 * m; halo.current.scale.setScalar(1 + Math.sin(t * 4 + phase) * 0.12 * m); }
    }
    if (orb.current) {
      orb.current.visible = working;
      if (working) {
        orb.current.position.y = 1.02 + Math.sin(t * 4 + phase) * 0.05 * m;
        (orb.current.material as THREE.MeshStandardMaterial).emissiveIntensity = 1.2 + Math.sin(t * 8) * 0.6 * m;
      }
    }
  });

  return (
    <group ref={group} position={agent.position}>
      {/* base ring marks position + draws the eye */}
      <mesh ref={ring} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
        <torusGeometry args={[0.32, 0.035, 12, 32]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.4} toneMapped={false} />
      </mesh>

      <group ref={body} position={[0, 0.36, 0]} onClick={(e) => { e.stopPropagation(); select("agent", agent.id); }}>
        {/* body */}
        <RoundedBox args={[0.42, 0.5, 0.34]} radius={0.1} smoothness={4} castShadow>
          <meshStandardMaterial color={color} roughness={0.65} metalness={0.05} />
        </RoundedBox>
        {/* head */}
        <RoundedBox args={[0.36, 0.3, 0.3]} radius={0.1} smoothness={4} position={[0, 0.42, 0]} castShadow>
          <meshStandardMaterial color={color} roughness={0.6} metalness={0.05} />
        </RoundedBox>
        {/* visor */}
        <RoundedBox args={[0.3, 0.14, 0.04]} radius={0.05} position={[0, 0.44, 0.16]}>
          <meshStandardMaterial color="#0F172A" roughness={0.3} />
        </RoundedBox>
        {/* two glowing eyes */}
        {[-0.07, 0.07].map((x) => (
          <mesh key={x} position={[x, 0.44, 0.185]}>
            <sphereGeometry args={[0.022, 12, 12]} />
            <meshStandardMaterial color="#7CC3FF" emissive="#7CC3FF" emissiveIntensity={1.4} toneMapped={false} />
          </mesh>
        ))}
        {/* working: spinning activity halo + pulsing orb above the head */}
        <mesh ref={halo} position={[0, 0.95, 0]} rotation={[-Math.PI / 2, 0, 0]} visible={false}>
          <torusGeometry args={[0.16, 0.022, 8, 24]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={1} toneMapped={false} />
        </mesh>
        <mesh ref={orb} position={[0, 1.02, 0]} visible={false}>
          <sphereGeometry args={[0.05, 16, 16]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={1.2} toneMapped={false} />
        </mesh>
        {/* the task being carried to the next agent during a hand-off */}
        <mesh ref={taskOrb} position={[0, 0.12, 0.28]} visible={false}>
          <sphereGeometry args={[0.1, 16, 16]} />
          <meshStandardMaterial color="#FDE68A" emissive="#F59E0B" emissiveIntensity={1.4} toneMapped={false} />
        </mesh>
        {isSel && (
          <mesh position={[0, 0.1, 0]}>
            <boxGeometry args={[0.6, 1.0, 0.5]} />
            <meshBasicMaterial color={color} wireframe transparent opacity={0.25} />
          </mesh>
        )}
      </group>

      <Html position={[0, 1.25, 0]} center style={{ pointerEvents: "none" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
          <div style={{
            font: "600 11px var(--font-ui)", color: "#0F172A",
            background: "rgba(255,255,255,.85)", padding: "1px 7px", borderRadius: 999,
            border: "1px solid var(--border)", whiteSpace: "nowrap",
          }}>{agent.name}</div>
          <span className={`pill state-${agent.state}`} style={{ transform: "scale(.85)" }}>
            <span className="pdot" style={{ background: color }} />{agent.state}
          </span>
        </div>
      </Html>
    </group>
  );
}
