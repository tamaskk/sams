import { useState } from "react";
import { useStore } from "../store";
import { DECOR_TYPES } from "../lib/office";

// Floating controls over the 3D office: toggle the layout editor and add
// decorations. Lives top-right of the canvas so it clears the view tabs.
export function SpatialToolbar() {
  const editLayout = useStore((s) => s.editLayout);
  const toggleEditLayout = useStore((s) => s.toggleEditLayout);
  const addDecor = useStore((s) => s.addDecor);
  const roomSize = useStore((s) => s.roomSize);
  const sceneRoom = useStore((s) => s.scene?.room);
  const setRoomSize = useStore((s) => s.setRoomSize);
  const resetRoomSize = useStore((s) => s.resetRoomSize);
  const [menu, setMenu] = useState(false);

  // Effective (unrounded) sizes; the steppers bump the rounded display value of
  // the touched axis and pass the untouched axis through unchanged (no snap).
  const ew = roomSize?.width ?? sceneRoom?.width ?? 12;
  const ed = roomSize?.depth ?? sceneRoom?.depth ?? 10;
  const w = Math.round(ew);
  const d = Math.round(ed);

  return (
    <div className="spatial-toolbar">
      <div className="spatial-toolbar-row">
        <div className="decor-add">
          <button className="stb-btn" onClick={() => setMenu((m) => !m)} aria-expanded={menu}>
            <Leaf /> Add decor
          </button>
          {menu && (
            <div className="decor-menu" onMouseLeave={() => setMenu(false)}>
              {DECOR_TYPES.map((d) => (
                <button key={d.type} className="decor-item" onClick={() => { addDecor(d.type); setMenu(false); }}>
                  {d.label}
                </button>
              ))}
            </div>
          )}
        </div>
        <button className={`stb-btn ${editLayout ? "on" : ""}`} onClick={toggleEditLayout}>
          <Move /> {editLayout ? "Done" : "Edit layout"}
        </button>
      </div>
      {editLayout && (
        <div className="room-panel">
          <div className="room-row">
            <span className="room-label">Room size</span>
            {roomSize && <button className="room-reset" onClick={resetRoomSize}>Reset</button>}
          </div>
          <div className="room-row">
            <Stepper label="W" value={w} onDec={() => setRoomSize(w - 1, ed)} onInc={() => setRoomSize(w + 1, ed)} />
            <Stepper label="D" value={d} onDec={() => setRoomSize(ew, d - 1)} onInc={() => setRoomSize(ew, d + 1)} />
          </div>
          <div className="spatial-hint">Drag desks &amp; decor to move · click <b>×</b> to remove decor</div>
        </div>
      )}
    </div>
  );
}

function Stepper({ label, value, onDec, onInc }: { label: string; value: number; onDec: () => void; onInc: () => void }) {
  return (
    <div className="stepper">
      <span className="stepper-label">{label}</span>
      <button className="stepper-btn" onClick={onDec} aria-label={`Decrease ${label}`}>−</button>
      <span className="stepper-val">{value}</span>
      <button className="stepper-btn" onClick={onInc} aria-label={`Increase ${label}`}>+</button>
    </div>
  );
}

function Leaf() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
      <path d="M2 21c0-3 1.85-5.36 5.08-6" />
    </svg>
  );
}

function Move() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="5 9 2 12 5 15" /><polyline points="9 5 12 2 15 5" />
      <polyline points="15 19 12 22 9 19" /><polyline points="19 9 22 12 19 15" />
      <line x1="2" y1="12" x2="22" y2="12" /><line x1="12" y1="2" x2="12" y2="22" />
    </svg>
  );
}
