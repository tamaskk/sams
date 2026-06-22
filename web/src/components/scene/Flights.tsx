import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { RoundedBox } from "@react-three/drei";
import * as THREE from "three";
import { useStore, type Flight } from "../../store";

const REDUCE = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const DUR: Record<Flight["mode"], number> = { throw: 1100, walk: 1750, teleport: 1150, lob: 2000, bounce: 1700 };
const TAIL = 460; // ms of burst/settle after arrival

// Visible task hand-off with several choreographies (spec 7.14 — motion is
// purposeful and reinforced by color). A packet is thrown in an arc, walked
// along the floor, or teleported (dematerialize → rematerialize).
export function Flights() {
  const flights = useStore((s) => s.flights);
  return <>{flights.map((f) => <FlightToken key={f.id} flight={f} />)}</>;
}

function FlightToken({ flight }: { flight: Flight }) {
  const remove = useStore((s) => s.removeFlight);
  const group = useRef<THREE.Group>(null);
  const packet = useRef<THREE.Group>(null);
  const burst = useRef<THREE.Mesh>(null); // ring at the target on arrival
  const echo = useRef<THREE.Mesh>(null);  // ring at the source (teleport "out" / "back")
  const done = useRef(false);

  const mode = REDUCE ? "teleport" : flight.mode;
  const dur = DUR[mode];
  const [fx, fy, fz] = flight.from;
  const [tx, ty, tz] = flight.to;

  const setRing = (mesh: THREE.Mesh | null, on: boolean, pos: [number, number, number], scale: number, opacity: number) => {
    if (!mesh) return;
    mesh.visible = on;
    if (!on) return;
    mesh.position.set(pos[0], 0.12, pos[2]);
    mesh.scale.setScalar(scale);
    (mesh.material as THREE.MeshBasicMaterial).opacity = opacity;
  };

  useFrame((state, dt) => {
    const t = performance.now() - flight.t0;
    const p = Math.min(1, t / dur);
    const tail = t - dur; // >0 after arrival
    let x = fx, y = fy, z = fz, pscale = 1, pvisible = true, spin = 0.12;

    if (mode === "throw") {
      x = fx + (tx - fx) * p; z = fz + (tz - fz) * p;
      y = fy + (ty - fy) * p + Math.sin(p * Math.PI) * 1.6;
      spin = 0.18;
      setRing(echo.current, false, flight.from, 0, 0);
    } else if (mode === "lob") {
      // very high, dramatic arc — slow and visible across the whole office.
      x = fx + (tx - fx) * p; z = fz + (tz - fz) * p;
      y = fy + (ty - fy) * p + Math.sin(p * Math.PI) * 2.8;
      spin = 0.26;
      setRing(echo.current, false, flight.from, 0, 0);
    } else if (mode === "walk") {
      // travels along the floor with a little step-bob; turns to face the way.
      x = fx + (tx - fx) * p; z = fz + (tz - fz) * p;
      y = 0.42 + Math.abs(Math.sin(p * Math.PI * 7)) * 0.07;
      spin = 0.04;
      setRing(echo.current, false, flight.from, 0, 0);
    } else if (mode === "bounce") {
      // three hops along the floor; a mini landing ring appears at each hop.
      const hop = Math.min(2, Math.floor(p * 3));
      const pt = p >= 1 ? 1 : (p * 3) % 1;
      const hf0 = hop / 3;
      const hf1 = Math.min(1, (hop + 1) / 3);
      x = fx + (tx - fx) * (hf0 + (hf1 - hf0) * pt);
      z = fz + (tz - fz) * (hf0 + (hf1 - hf0) * pt);
      y = 0.42 + Math.sin(pt * Math.PI) * 0.42;
      spin = 0.08;
      if (pt < 0.18 && hop > 0 && p < 1) {
        const landX = fx + (tx - fx) * hf0;
        const landZ = fz + (tz - fz) * hf0;
        setRing(echo.current, true, [landX, 0, landZ], 0.25 + pt * 4, ((0.18 - pt) / 0.18) * 0.55);
      } else {
        setRing(echo.current, false, flight.from, 0, 0);
      }
    } else {
      // teleport: shrink-out at source, gap, grow-in at target.
      if (p < 0.28) {
        x = fx; y = fy + 0.2; z = fz;
        pscale = Math.max(0, 1 - p / 0.28);
        const o = (1 - p / 0.28) * 0.7;
        setRing(echo.current, true, flight.from, 0.3 + p * 2.2, o); // dematerialize ring
        setRing(burst.current, false, flight.to, 0, 0);
      } else if (p < 0.55) {
        pvisible = false; pscale = 0;
        setRing(echo.current, false, flight.from, 0, 0);
      } else {
        x = tx; y = ty + 0.2; z = tz;
        const g = (p - 0.55) / 0.45;
        pscale = Math.min(1, g);
        setRing(burst.current, true, flight.to, 0.3 + g * 1.8, (1 - g) * 0.7); // rematerialize ring
        // a faint "back" echo at the source as it lands
        if (g > 0.6) setRing(echo.current, true, flight.from, (g - 0.6) * 2.5, (1 - g) * 0.4);
      }
    }

    if (group.current) group.current.position.set(x, y, z);
    if (packet.current) {
      packet.current.visible = pvisible && (mode === "teleport" ? true : p < 1);
      packet.current.rotation.y += spin;
      packet.current.rotation.x += spin * 0.5;
      packet.current.scale.setScalar(pscale);
    }

    // Landing burst for throw / walk (teleport uses its rematerialize ring).
    if (mode !== "teleport") {
      if (tail > 0) {
        const bp = Math.min(1, tail / TAIL);
        setRing(burst.current, true, flight.to, 0.3 + bp * 1.9, (1 - bp) * 0.65);
        if (packet.current) packet.current.visible = false;
      } else {
        setRing(burst.current, false, flight.to, 0, 0);
      }
    }

    if (t > dur + TAIL && !done.current) { done.current = true; remove(flight.id); }
  });

  return (
    <group>
      <group ref={group}>
        <group ref={packet}>
          <RoundedBox args={[0.34, 0.26, 0.06]} radius={0.04} smoothness={3}>
            <meshStandardMaterial color={flight.color} emissive={flight.color} emissiveIntensity={1.1} toneMapped={false} />
          </RoundedBox>
          <mesh>
            <sphereGeometry args={[0.3, 16, 16]} />
            <meshBasicMaterial color={flight.color} transparent opacity={0.18} toneMapped={false} depthWrite={false} />
          </mesh>
        </group>
        <pointLight color={flight.color} intensity={2.2} distance={2.6} />
      </group>
      <mesh ref={burst} rotation={[-Math.PI / 2, 0, 0]} visible={false}>
        <torusGeometry args={[0.5, 0.05, 12, 36]} />
        <meshBasicMaterial color={flight.color} transparent opacity={0} toneMapped={false} depthWrite={false} />
      </mesh>
      <mesh ref={echo} rotation={[-Math.PI / 2, 0, 0]} visible={false}>
        <torusGeometry args={[0.5, 0.05, 12, 36]} />
        <meshBasicMaterial color={flight.color} transparent opacity={0} toneMapped={false} depthWrite={false} />
      </mesh>
    </group>
  );
}
