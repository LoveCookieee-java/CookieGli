---
name: cookiegli-core
description: High-density project context genome compression (<=1500 tokens) and ROI-based Darwin memory evolution. Use to onboard instantly into unfamiliar projects, compress project context, and evolve learned engineering patterns.
---

# CookieGli Core — Project Genome & Darwin Memory Evolution

This skill equips AI agents with high-density project context comprehension and evolutionary knowledge persistence, synthesizing principles from **Headroom token economy** and **System Autopilot continuous verification**.

---

## 1. Fast Project Onboarding via Genome
When entering a workspace or starting a new programming task:
1. **Check for `.agents/GENOME.md`**:
   - If present, read it using `view_file` to understand the entire architecture, frameworks, entry points, public APIs, and dependency graph in `< 600` tokens.
   - If not present and you need a high-level project map, generate it on demand:
     ```powershell
     python cli/cookiegli.py genome build . --save .agents/GENOME.md
     ```
2. **Synthesize Task Context**:
   - For specific targeted tasks (e.g. "Refactor auth controller"), run:
     ```powershell
     python cli/cookiegli.py genome context "<task description>"
     ```
   - Work directly from the synthesized slice to minimize context bloat.

---

## 2. Headroom Token Discipline
- **Zero Raw Dumps**: Never dump massive directory trees or entire large files into your context window.
- **Pinpoint Operations**: Use `grep_search` and line-range `view_file` (`StartLine`/`EndLine`) targeted directly at symbols identified in `GENOME.md`.
- **Log Noise Stripping**: Filter compiler/test outputs to include only stack traces and failing assertions.

---

## 3. The Continuous Verification Loop (System Autopilot)
Before completing any coding task:
1. **Compile & Run Unit Tests**: Execute all relevant unit tests (`python -m unittest discover -s tests -v`, `npm test`, etc.).
2. **Diagnose & Auto-Fix**: If any test fails, analyze root cause and fix immediately without asking for permission.
3. **Regression Guard**: Verify that modifications do not break callers identified in the Dependency Matrix.
4. **Zero-Defect Standard**: Do not declare completion until 100% of tests pass.

---

## 4. Darwin Knowledge Evolution (Learned Patterns)
When you transition from a failure/bug to a verified fix:
- Record the lesson:
  - **What failed**: Root cause of the error.
  - **What succeeded**: The verified fix or pattern.
  - **The Principle**: Concrete rule to avoid repeating the mistake.
- Record the lesson in the project's `.agents/AGENTS.md` under `<!-- darwin:learnings:start -->` so future agent sessions inherit the learning automatically.
