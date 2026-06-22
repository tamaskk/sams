# Accessibility Audit (capability: design.a11y_audit)

When auditing a UI for accessibility, check against WCAG 2.2 AA and report
concrete, prioritized fixes:

- **Color contrast** — minimum 4.5:1 for normal text, 3:1 for large text.
- **Focus states** — visible focus rings on every interactive element.
- **Keyboard navigation** — tab order matches visual order; no traps.
- **Labels** — every input has an associated `<label>`; icon-only buttons have `aria-label`.
- **Alt text** — meaningful images have descriptive alt; decorative images are `alt=""`.
- **Color is never the only signal** — pair color with text or an icon.
- **Reduced motion** — honor `prefers-reduced-motion`.

Produce a markdown report grouped by severity (blocker / major / minor), each
finding with the element, the rule, and the recommended fix. Never auto-apply;
create tasks for human review.
