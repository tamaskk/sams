// Office layout: each of the six role agents gets its OWN dedicated, themed
// workstation. Positions are [x, z] in the room's grid (room ~12 x 10). The
// agent stands at the station facing the camera; its themed desk sits behind it.
export const ROLE_STATIONS: Record<string, [number, number]> = {
  planner: [2.6, 3.0],
  designer: [5.4, 2.6],
  developer: [8.4, 3.0],
  reviewer: [2.6, 6.7],
  tester: [5.4, 7.1],
  deployer: [8.4, 6.7],
};

export const ROLE_ORDER = ["planner", "designer", "developer", "reviewer", "tester", "deployer"];

// Primitives from the legacy layout we hide now that themed desks exist.
export const HIDDEN_PRIMITIVES = new Set([
  "Desk 01", "Desk 02", "Desk 03", "Desk 04", "Desk 05", "Desk 06", "Terminal",
]);

const ROLE_THEMES = ["planner", "designer", "developer", "reviewer", "tester", "deployer"];

// Which desk theme an agent gets — instances (developer-2) keep their base theme;
// unknown agents get a tidy generic desk.
export function deskTheme(id: string): string {
  const base = id.replace(/-\d+$/, "");
  return ROLE_THEMES.includes(base) ? base : "generic";
}

// Candidate desk slots (a grid in the central area) for auto-placing new agents.
export const DESK_SLOTS: [number, number][] = (() => {
  const out: [number, number][] = [];
  for (const z of [3.0, 5.0, 7.0]) for (const x of [2.5, 4.7, 6.9, 9.1]) out.push([x, z]);
  return out;
})();

// Assign a station to every agent id, keeping existing ones and placing new
// agents into the first free slot.
export function ensureStations(
  stations: Record<string, [number, number]>,
  ids: string[],
): Record<string, [number, number]> {
  const out = { ...stations };
  for (const id of ids) {
    if (out[id]) continue;
    const taken = Object.values(out);
    let slot = DESK_SLOTS.find((s) => taken.every((t) => Math.hypot(t[0] - s[0], t[1] - s[1]) > 1.7));
    if (!slot) {
      const n = Object.keys(out).length;
      slot = [2.5 + (n % 4) * 2.2, 3 + Math.floor(n / 4) * 2 + 0.2];
    }
    out[id] = slot;
  }
  return out;
}

export const DECOR_TYPES = [
  { type: "plant", label: "Plant" },
  { type: "tree", label: "Tall plant" },
  { type: "lamp", label: "Floor lamp" },
  { type: "sofa", label: "Sofa" },
  { type: "rug", label: "Rug" },
  { type: "cabinet", label: "Cabinet" },
  { type: "water", label: "Water cooler" },
];

export interface DecorItem { id: string; type: string; pos: [number, number]; }

