// Thin REST client for the SAMS control plane (spec 11.1).
const BASE = "/api/v1";

async function req<T>(method: string, path: string, body?: any): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) throw new Error(`${method} ${path} -> ${resp.status}`);
  return resp.json();
}

export const api = {
  status: () => req<any>("GET", "/status"),
  agents: () => req<any[]>("GET", "/agents"),
  agent: (id: string) => req<any>("GET", `/agents/${encodeURIComponent(id)}`),
  patchAgent: (id: string, body: Record<string, any>) => req<any>("PATCH", `/agents/${encodeURIComponent(id)}`, body),
  setStagePrompt: (column: string, prompt: string | null) =>
    req<any>("PATCH", "/pipeline/prompts", { column, prompt }),
  spawn: (ref: string) => req<any>("POST", "/agents", { ref }),
  spawnType: (ref: string) => req<any>("POST", "/agents/spawn", { ref }),
  despawn: (id: string) => req<any>("DELETE", `/agents/${id}`),
  assign: (id: string, title: string, capability?: string) =>
    req<any>("POST", `/agents/${id}/assign`, { title, capability }),
  scene: (space: string) => req<any>("GET", `/spaces/${space}/scene`),
  tasks: () => req<any[]>("GET", "/tasks"),
  createTask: (body: { title: string; labels?: string[]; description?: string; project?: string | null; column?: string; image_data?: string; image_name?: string }) =>
    req<any>("POST", "/tasks", body),
  moveTask: (id: string, to: string) => req<any>("PATCH", `/tasks/${id}`, { to }),
  updateTask: (id: string, body: Record<string, any>) => req<any>("PATCH", `/tasks/${id}`, body),
  deleteTask: (id: string) => req<any>("DELETE", `/tasks/${id}`),
  acceptTask: (id: string) => req<any>("POST", `/tasks/${id}/accept`, {}),
  commitTask: (id: string) => req<any>("POST", `/tasks/${id}/commit`, {}),
  rejectTask: (id: string, comment = "") => req<any>("POST", `/tasks/${id}/reject`, { comment }),
  workflows: () => req<any[]>("GET", "/workflows"),
  runWorkflow: (id: string, payload: any = {}) =>
    req<any>("POST", `/workflows/${id}/run`, { payload }),
  gates: () => req<any[]>("GET", "/gates"),
  approveGate: (id: string, approver = "human:lead") =>
    req<any>("POST", `/gates/${id}/approve`, { approver }),
  events: (limit = 80) => req<any[]>("GET", `/events?limit=${limit}`),
  addPrimitive: (space: string, type: string, name?: string) =>
    req<any>("POST", `/spaces/${space}/primitives`, { type, name }),
  fs: (path?: string) =>
    req<{ path: string; parent: string; entries: { name: string; path: string; type: "dir" | "file"; size: number | null }[] }>(
      "GET", `/fs${path ? `?path=${encodeURIComponent(path)}` : ""}`),
  fsRead: (path: string) =>
    req<{ path: string; content: string; truncated: boolean }>("GET", `/fs/read?path=${encodeURIComponent(path)}`),
  clickupStatus: () => req<{ configured: boolean }>("GET", "/integrations/clickup/status"),
  clickupTasks: () => req<{ configured: boolean; user?: string; hint?: string; tasks: { id: string; name: string; description: string; status: string; url: string; priority: string | null; list: string; team: string }[] }>("GET", "/integrations/clickup/tasks"),
  githubRepos: () => req<{ configured: boolean; user?: string; avatar?: string; hint?: string; repos: {
    id: number; name: string; full_name: string; description: string; url: string; clone_url: string; ssh_url: string;
    private: boolean; language: string | null; stars: number; forks: number; updated_at: string; default_branch: string;
    owner: string; fork: boolean; archived: boolean;
  }[] }>("GET", "/integrations/github/repos"),
  githubTree: (repo: string, ref?: string) =>
    req<{ repo: string; ref: string; truncated: boolean; entries: { path: string; type: "dir" | "file"; size: number | null }[] }>(
      "GET", `/integrations/github/tree?repo=${encodeURIComponent(repo)}${ref ? `&ref=${encodeURIComponent(ref)}` : ""}`),
  githubFile: (repo: string, path: string, ref?: string) =>
    req<{ path: string; content: string; truncated?: boolean; binary?: boolean; directory?: boolean }>(
      "GET", `/integrations/github/file?repo=${encodeURIComponent(repo)}&path=${encodeURIComponent(path)}${ref ? `&ref=${encodeURIComponent(ref)}` : ""}`),
  githubWork: (repo: string, task: string, base?: string) =>
    req<{ started: boolean; repo: string }>("POST", "/integrations/github/work", { repo, task, base }),
  githubPulls: (state: "open" | "closed" | "all" = "open") =>
    req<{ configured: boolean; user?: string; hint?: string; pulls: {
      id: number; number: number; title: string; url: string; repo: string;
      state: string; draft: boolean; updated_at: string; comments: number;
    }[] }>("GET", `/integrations/github/pulls?state=${state}`),
  githubPull: (repo: string, number: number) =>
    req<{ repo: string; number: number; title: string; body: string; state: string; draft: boolean; merged: boolean;
      mergeable: boolean | null; mergeable_state: string; head: string; base: string; additions: number; deletions: number;
      changed_files: number; commits: number; url: string; author: string }>(
      "GET", `/integrations/github/pull?repo=${encodeURIComponent(repo)}&number=${number}`),
  githubPullFiles: (repo: string, number: number) =>
    req<{ files: { filename: string; status: string; additions: number; deletions: number; patch: string | null }[] }>(
      "GET", `/integrations/github/pull/files?repo=${encodeURIComponent(repo)}&number=${number}`),
  githubMergePull: (repo: string, number: number, method: "merge" | "squash" | "rebase" = "merge") =>
    req<{ merged: boolean; message: string; sha?: string; status?: number }>("POST", "/integrations/github/pull/merge", { repo, number, method }),
  githubClosePull: (repo: string, number: number) =>
    req<{ closed: boolean; message?: string; status?: number }>("POST", "/integrations/github/pull/close", { repo, number }),
  githubReadyPull: (repo: string, number: number) =>
    req<{ ok: boolean; message?: string }>("POST", "/integrations/github/pull/ready", { repo, number }),
  vercelStatus: () => req<{ configured: boolean }>("GET", "/integrations/vercel/status"),
  vercelDeploy: (target: string, prod = true, subdir?: string) =>
    req<{ started: boolean; target: string; prod: boolean }>("POST", "/integrations/vercel/deploy", { target, prod, subdir }),
  startProject: (path: string) =>
    req<{ started: boolean; command?: string; pid?: number; reason?: string }>("POST", "/projects/start", { path }),
  runningProjects: () => req<any[]>("GET", "/projects/running"),
  stopProject: (pid: number) => req<any>("POST", "/projects/stop", { pid }),
  projectLog: (pid: number) =>
    req<{ pid: number; name: string; command: string; alive: boolean; content: string }>("GET", `/projects/log?pid=${pid}`),
};
