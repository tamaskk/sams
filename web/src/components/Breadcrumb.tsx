import { useStore } from "../store";

const COLUMNS = ["To Do", "Planner", "Designer", "Developer", "Reviewer", "Tester", "Deployer", "Committed"];

interface Props {
  tab: string;
  onTabClick: (tab: string) => void;
  onCloseRepo: () => void;
  onClosePull: () => void;
}

interface Crumb {
  label: string;
  onClick?: () => void;
}

export function Breadcrumb({ tab, onTabClick, onCloseRepo, onClosePull }: Props) {
  const selectedRepo = useStore((s) => s.selectedRepo);
  const selectedPull = useStore((s) => s.selectedPull);
  const navCard = useStore((s) => s.navCard);
  const openFile = useStore((s) => s.openFile);

  const crumbs: Crumb[] = [];
  let context = "";

  if (selectedPull) {
    crumbs.push({ label: "GitHub", onClick: () => { onClosePull(); onCloseRepo(); } });
    crumbs.push({ label: `PR #${selectedPull.number} — ${selectedPull.title}` });
  } else if (selectedRepo) {
    crumbs.push({ label: "GitHub", onClick: onCloseRepo });
    crumbs.push({ label: selectedRepo.full_name });
  } else if (tab === "Kanban" && navCard) {
    crumbs.push({ label: "Kanban", onClick: () => useStore.getState().setNavCard(null) });
    crumbs.push({ label: navCard.title });
    const idx = COLUMNS.indexOf(navCard.status);
    if (idx >= 0) context = `Step ${idx + 1} of ${COLUMNS.length}`;
  } else if (tab === "Code" && openFile) {
    crumbs.push({ label: "Code", onClick: () => onTabClick("Code") });
    crumbs.push({ label: openFile.path.split("/").pop() ?? openFile.path });
  } else {
    crumbs.push({ label: tab });
  }

  return (
    <nav className="breadcrumb" aria-label="Breadcrumb navigation">
      <ol className="breadcrumb-list">
        {crumbs.map((c, i) => (
          <li key={i} className="breadcrumb-item">
            {i > 0 && <span className="breadcrumb-sep" aria-hidden="true">›</span>}
            {c.onClick ? (
              <button className="breadcrumb-btn" onClick={c.onClick} aria-label={`Navigate to ${c.label}`}>
                {c.label}
              </button>
            ) : (
              <span className="breadcrumb-current" aria-current="page">{c.label}</span>
            )}
          </li>
        ))}
      </ol>
      {context && <span className="breadcrumb-context" aria-label={context}>{context}</span>}
    </nav>
  );
}
