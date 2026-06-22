# agents/custom/seo_agent.py
# Code-backed handler for the SEO agent (spec 6.2). Adds a brand-new capability,
# content.seo_audit, with no change to SAMS core.
from sams.sdk import Agent, capability, hook


class SeoAgent(Agent):
    """Custom SEO agent with a bespoke capability."""

    @hook("on_spawn")
    async def setup(self, ctx):
        # Runs once when the agent is instantiated.
        ctx.log.info("SEO agent ready")
        rules_uri = "vault://content/seo-rules.yaml"
        if await ctx.vault.exists(rules_uri):
            self.ruleset = await ctx.vault.read(rules_uri)
        else:
            self.ruleset = "default ruleset: titles, meta descriptions, headings, alt text, canonicals"

    @capability("content.seo_audit")  # a NEW capability
    async def seo_audit(self, ctx, url: str) -> dict:
        """Audit a page and return prioritized findings."""
        html = await self.tools.web_fetch(url)  # calls a registered tool
        findings = await self.think(  # calls the bound LLM
            prompt=f"Audit this page against the ruleset:\n{html[:4000]}",
            context=self.ruleset,
        )
        report_path = await self.tools.doc_write(
            path=f"vault://content/seo-reports/{ctx.slug(url)}.md",
            content=findings.markdown,
        )
        # Create follow-up tasks for humans/other agents.
        for fix in findings.fixes:
            await self.tools.kanban_write(
                title=fix["title"], column="To Do", labels=["seo"]
            )
        await ctx.emit(
            "content.seo_audit.completed", {"url": url, "report": report_path}
        )
        return {"report": report_path, "issues": len(findings.fixes)}

    @hook("on_error")
    async def on_error(self, ctx, error):
        ctx.log.error(f"SEO audit failed: {error}")
        await ctx.emit("agent.error", {"agent": self.id, "error": str(error)})
