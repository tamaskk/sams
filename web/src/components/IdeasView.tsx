import { useState } from "react";
import { api } from "../lib/api";
import { FolderPicker } from "./FolderPicker";

const CATEGORIES = [
  { id: "business", label: "Business", bg: "#DCFCE7", text: "#166534" },
  { id: "ui-ux", label: "UI/UX", bg: "#FCE7F3", text: "#9D174D" },
  { id: "features", label: "Features", bg: "#DBEAFE", text: "#1E40AF" },
  { id: "performance", label: "Performance", bg: "#FEF3C7", text: "#92400E" },
  { id: "security", label: "Security", bg: "#FEE2E2", text: "#991B1B" },
  { id: "dev-experience", label: "Dev Experience", bg: "#EDE9FE", text: "#5B21B6" },
  { id: "code-quality", label: "Code Quality", bg: "#F1F5F9", text: "#334155" },
  { id: "marketing", label: "Marketing", bg: "#FFEDD5", text: "#9A3412" },
];

const MODELS = [
  { id: "claude-opus-4-8", label: "Opus 4.8", hint: "Most capable · Deepest reasoning" },
  { id: "claude-sonnet-4-6", label: "Sonnet 4.6", hint: "Balanced · Recommended" },
  { id: "claude-haiku-4-5-20251001", label: "Haiku 4.5", hint: "Fastest · Most economical" },
];

const IMPACT_STYLE: Record<string, { bg: string; text: string }> = {
  High: { bg: "#DCFCE7", text: "#166534" },
  Medium: { bg: "#FEF3C7", text: "#92400E" },
  Low: { bg: "#F1F5F9", text: "#475569" },
};

interface Idea {
  title: string;
  description: string;
  category: string;
  impact: string;
}

function catStyle(label: string): { bg: string; text: string } {
  const c = CATEGORIES.find(
    (x) => x.label.toLowerCase() === label.toLowerCase() || x.id === label.toLowerCase()
  );
  return c ? { bg: c.bg, text: c.text } : { bg: "#F1F5F9", text: "#334155" };
}

export function IdeasView() {
  const [project, setProject] = useState("");
  const [selectedCats, setSelectedCats] = useState<Set<string>>(new Set(["features", "ui-ux"]));
  const [model, setModel] = useState("claude-sonnet-4-6");
  const [temperature, setTemperature] = useState(0.7);
  const [count, setCount] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [added, setAdded] = useState<Set<number>>(new Set());
  const [adding, setAdding] = useState<Set<number>>(new Set());

  const toggleCat = (id: string) => {
    const next = new Set(selectedCats);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedCats(next);
  };

  const generate = async () => {
    if (loading || selectedCats.size === 0) return;
    setLoading(true);
    setError("");
    setIdeas([]);
    setAdded(new Set());
    setAdding(new Set());
    try {
      const res = await (api as any).generateIdeas({
        project,
        categories: Array.from(selectedCats).map((id) => CATEGORIES.find((c) => c.id === id)!.label),
        model,
        temperature,
        count,
      });
      setIdeas(res.ideas ?? []);
    } catch (e: any) {
      setError(e?.message ?? "Generation failed. Is ANTHROPIC_API_KEY set in your .env file?");
    } finally {
      setLoading(false);
    }
  };

  const addToTodo = async (idea: Idea, idx: number) => {
    if (adding.has(idx) || added.has(idx)) return;
    setAdding((prev) => new Set(prev).add(idx));
    try {
      await api.createTask({
        title: idea.title,
        description: `[${idea.category} · ${idea.impact} Impact]\n\n${idea.description}`,
        project: project || null,
        column: "To Do",
      });
      setAdded((prev) => new Set(prev).add(idx));
    } catch {
      /* silent — user can retry */
    } finally {
      setAdding((prev) => { const s = new Set(prev); s.delete(idx); return s; });
    }
  };

  return (
    <div className="ideas-layout">
      {/* ── Config sidebar ── */}
      <div className="ideas-config">
        <div className="ideas-config-inner">

          <div className="ideas-section">
            <div className="ideas-section-title">Project (optional)</div>
            <FolderPicker onChange={setProject} />
            {project && (
              <div className="ideas-project-hint mono">
                {project.split("/").filter(Boolean).pop()}
              </div>
            )}
          </div>

          <div className="ideas-section">
            <div className="ideas-section-title">Improvement Types</div>
            <div className="ideas-cats">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  className={`ideas-cat-btn${selectedCats.has(cat.id) ? " on" : ""}`}
                  style={selectedCats.has(cat.id) ? { background: cat.bg, color: cat.text, borderColor: cat.text + "55" } : {}}
                  onClick={() => toggleCat(cat.id)}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          <div className="ideas-section">
            <div className="ideas-section-title">AI Model</div>
            <div className="ideas-models">
              {MODELS.map((m) => (
                <button
                  key={m.id}
                  className={`ideas-model-btn${model === m.id ? " on" : ""}`}
                  onClick={() => setModel(m.id)}
                >
                  <span className="ideas-model-name">{m.label}</span>
                  <span className="ideas-model-hint">{m.hint}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="ideas-section">
            <div className="ideas-section-title">
              Creativity&nbsp;·&nbsp;
              <span style={{ color: "var(--brand)", fontWeight: 700 }}>{temperature.toFixed(1)}</span>
            </div>
            <input
              type="range" min="0" max="1" step="0.05"
              value={temperature}
              onChange={(e) => setTemperature(Number(e.target.value))}
              className="ideas-slider"
            />
            <div className="ideas-slider-labels">
              <span>Precise</span>
              <span>Creative</span>
            </div>
          </div>

          <div className="ideas-section">
            <div className="ideas-section-title">Number of Ideas</div>
            <div className="ideas-count-row">
              {[3, 5, 8, 10].map((n) => (
                <button
                  key={n}
                  className={`ideas-count-btn${count === n ? " on" : ""}`}
                  onClick={() => setCount(n)}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          <button
            className="btn-primary ideas-generate-btn"
            disabled={loading || selectedCats.size === 0}
            onClick={generate}
          >
            {loading ? "Generating…" : "✦  Generate Ideas"}
          </button>
          {selectedCats.size === 0 && (
            <div className="ideas-warn">Select at least one improvement type</div>
          )}

        </div>
      </div>

      {/* ── Results canvas ── */}
      <div className="ideas-canvas">
        {!loading && !error && ideas.length === 0 && (
          <div className="ideas-empty">
            <div className="ideas-empty-icon">✦</div>
            <div className="ideas-empty-title">Generate AI-powered ideas</div>
            <div className="ideas-empty-sub">
              Pick a project, choose improvement types, select a model,<br />
              then generate actionable ideas from Claude.
            </div>
            <button
              className="btn-primary"
              disabled={selectedCats.size === 0}
              onClick={generate}
              style={{ marginTop: 4 }}
            >
              ✦ Generate Ideas
            </button>
          </div>
        )}

        {loading && (
          <>
            <div className="ideas-result-header">
              <span className="skel" style={{ width: 130, height: 16 }} />
            </div>
            <div className="ideas-cards">
              {Array.from({ length: count }).map((_, i) => (
                <div key={i} className="ideas-card">
                  <div className="ideas-card-badges">
                    <span className="skel" style={{ width: 64, height: 20, borderRadius: 999 }} />
                    <span className="skel" style={{ width: 86, height: 20, borderRadius: 999 }} />
                  </div>
                  <span className="skel" style={{ width: "75%", height: 17 }} />
                  <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                    <span className="skel" style={{ width: "100%", height: 13 }} />
                    <span className="skel" style={{ width: "90%", height: 13 }} />
                    <span className="skel" style={{ width: "60%", height: 13 }} />
                  </div>
                  <span className="skel" style={{ width: 110, height: 28, borderRadius: 999 }} />
                </div>
              ))}
            </div>
          </>
        )}

        {!loading && error && (
          <div className="ideas-error">
            <strong>Error:</strong> {error}
          </div>
        )}

        {!loading && ideas.length > 0 && (
          <>
            <div className="ideas-result-header">
              <span className="ideas-result-count">{ideas.length} ideas generated</span>
              <span className="ideas-result-meta">
                {MODELS.find((m) => m.id === model)?.label}
                {project ? ` · ${project.split("/").filter(Boolean).pop()}` : ""}
              </span>
            </div>
            <div className="ideas-cards">
              {ideas.map((idea, i) => {
                const cs = catStyle(idea.category);
                const is = IMPACT_STYLE[idea.impact] ?? IMPACT_STYLE.Medium;
                const isDone = added.has(i);
                const isBusy = adding.has(i);
                return (
                  <div key={i} className="ideas-card">
                    <div className="ideas-card-badges">
                      <span className="ideas-badge" style={{ background: cs.bg, color: cs.text }}>
                        {idea.category}
                      </span>
                      <span className="ideas-badge" style={{ background: is.bg, color: is.text }}>
                        {idea.impact} Impact
                      </span>
                    </div>
                    <div className="ideas-card-title">{idea.title}</div>
                    <div className="ideas-card-desc">{idea.description}</div>
                    <button
                      className={`ideas-add-btn${isDone ? " done" : ""}`}
                      disabled={isDone || isBusy}
                      onClick={() => addToTodo(idea, i)}
                    >
                      {isDone ? "✓ Added to To Do" : isBusy ? "Adding…" : "+ Add to To Do"}
                    </button>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
