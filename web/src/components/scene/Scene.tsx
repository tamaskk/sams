import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows, OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { useStore } from "../../store";
import { Primitive3D } from "./Primitive3D";
import { Agent3D } from "./Agent3D";
import { Office } from "./Office";
import { AgentDesk } from "./AgentDesk";
import { Decor3D } from "./Decor3D";
import { deskTheme, HIDDEN_PRIMITIVES } from "../../lib/office";

type DragTarget = { kind: "agent" | "decor"; id: string } | null;

// Orthographic zoom that keeps the whole room in frame.
const fitZoom = (w: number, d: number) => Math.max(16, Math.min(52, 520 / Math.max(w, d)));

// Left-drag PANS (move the camera across the room), right-drag rotates, wheel
// zooms — the natural mapping for a map/floorplan view. Module constants so the
// props keep a stable identity across re-renders.
const MOUSE_BUTTONS = { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE };
const TOUCHES = { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_ROTATE };

// Fits the room in view when its size changes. On first mount it sets the full
// iso position; afterwards a resize only re-zooms + recenters the target, so the
// user's orbit angle is preserved. Never runs on unrelated re-renders.
function CameraRig({ width, depth }: { width: number; depth: number }) {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as any;
  const mounted = useRef(false);
  useLayoutEffect(() => {
    const cx = width / 2, cz = depth / 2;
    const cam = camera as THREE.OrthographicCamera;
    cam.zoom = fitZoom(width, depth);
    cam.updateProjectionMatrix();
    if (!mounted.current) {
      camera.position.set(cx + 13, 14, cz + 13);
      mounted.current = true;
    }
    if (controls) { controls.target.set(cx, 0.6, cz); controls.update(); }
  }, [width, depth, camera, controls]);
  return null;
}

// Polls the pointer each frame while something is being dragged and writes the
// floor-plane position into the store (desks move their agent; decor moves alone).
function DragManager({ dragRef, width, depth }: { dragRef: React.MutableRefObject<DragTarget>; width: number; depth: number }) {
  const { camera, pointer, raycaster } = useThree();
  const setStation = useStore((s) => s.setStation);
  const moveDecor = useStore((s) => s.moveDecor);
  const plane = useMemo(() => new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), []);
  const hit = useMemo(() => new THREE.Vector3(), []);
  useFrame(() => {
    const d = dragRef.current;
    if (!d) return;
    raycaster.setFromCamera(pointer, camera);
    if (!raycaster.ray.intersectPlane(plane, hit)) return;
    const x = Math.max(0.7, Math.min(width - 0.7, hit.x));
    const z = Math.max(0.7, Math.min(depth - 0.7, hit.z));
    if (d.kind === "agent") setStation(d.id, [x, z]);
    else moveDecor(d.id, [x, z]);
  });
  return null;
}

// The isometric office: a real room with a dedicated, themed workstation per
// agent, placeable decorations, and a drag-to-rearrange layout editor.
export function Scene() {
  const scene = useStore((s) => s.scene);
  const agents = useStore((s) => s.agents);
  const stations = useStore((s) => s.stations);
  const decor = useStore((s) => s.decor);
  const editLayout = useStore((s) => s.editLayout);
  const roomSize = useStore((s) => s.roomSize);
  const removeDecor = useStore((s) => s.removeDecor);
  const deselect = useStore((s) => s.select);

  const controls = useRef<any>(null);
  const dragRef = useRef<DragTarget>(null);

  useEffect(() => {
    const up = () => {
      dragRef.current = null;
      if (controls.current) controls.current.enabled = true;
      document.body.style.cursor = "auto";
    };
    window.addEventListener("pointerup", up);
    return () => window.removeEventListener("pointerup", up);
  }, []);

  if (!scene) return <div style={{ display: "grid", placeItems: "center", height: "100%", color: "var(--text-subtle)" }}>Connecting to SAMS…</div>;

  // Effective room size: a user override (if set) wins over the backend scene.
  const W = roomSize?.width ?? scene.room.width;
  const D = roomSize?.depth ?? scene.room.depth;
  const cx = W / 2;
  const cz = D / 2;
  const primitives = scene.primitives.filter((p) => !HIDDEN_PRIMITIVES.has(p.name));

  const startDrag = (kind: "agent" | "decor", id: string) => (e: any) => {
    if (!editLayout) return;
    e.stopPropagation();
    dragRef.current = { kind, id };
    if (controls.current) controls.current.enabled = false;
    document.body.style.cursor = "grabbing";
  };
  const hoverGrab = () => { if (editLayout) document.body.style.cursor = "grab"; };
  const hoverEnd = () => { if (!dragRef.current) document.body.style.cursor = "auto"; };

  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      orthographic
      camera={{ position: [cx + 13, 14, cz + 13], zoom: fitZoom(W, D), near: -100, far: 300 }}
      style={{ background: "transparent" }}
    >
      <color attach="background" args={["#eaf1fb"]} />
      <OrbitControls ref={controls} makeDefault enablePan screenSpacePanning
        mouseButtons={MOUSE_BUTTONS} touches={TOUCHES}
        minZoom={14} maxZoom={130} maxPolarAngle={Math.PI / 2.15} />
      <CameraRig width={W} depth={D} />

      <ambientLight intensity={0.85} />
      <hemisphereLight args={["#ffffff", "#dbe6f5", 0.5]} />
      <directionalLight
        position={[cx + 7, 16, cz + 5]} intensity={1.0} castShadow
        shadow-mapSize={[2048, 2048]} shadow-camera-left={-16} shadow-camera-right={16}
        shadow-camera-top={16} shadow-camera-bottom={-16} shadow-camera-near={0.1} shadow-camera-far={60}
      />

      <Office width={W} depth={D} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[cx, 0.001, cz]} onClick={() => deselect("primitive", "")} visible={false}>
        <planeGeometry args={[W + 2, D + 2]} />
        <meshBasicMaterial />
      </mesh>
      <ContactShadows position={[cx, 0.03, cz]} opacity={0.28} scale={Math.max(W, D) + 8} blur={2.6} far={9} />

      <DragManager dragRef={dragRef} width={W} depth={D} />

      {/* placeable decorations */}
      {decor.map((d) => (
        <Decor3D key={d.id} type={d.type} position={[d.pos[0], 0, d.pos[1]]} editing={editLayout}
          onRemove={() => removeDecor(d.id)} onPointerDown={startDrag("decor", d.id)} />
      ))}

      {/* one themed, draggable workstation per agent */}
      {Object.values(agents).map((a) => {
        const st = stations[a.id];
        const pos: [number, number, number] = st ? [st[0], 0, st[1]] : [a.position[0], 0, a.position[2]];
        return (
          <group key={a.id} onPointerDown={startDrag("agent", a.id)} onPointerOver={hoverGrab} onPointerOut={hoverEnd}>
            <AgentDesk role={deskTheme(a.id)} position={pos} color={a.color} />
          </group>
        );
      })}

      {/* remaining office fixtures (Kanban Wall, Vault, Security Gate, Whiteboard, Lounge, Event Stream) */}
      {primitives.map((p) => <Primitive3D key={p.id} prim={p} />)}
      {Object.values(agents).map((a) => <Agent3D key={a.id} agent={a} />)}
    </Canvas>
  );
}
