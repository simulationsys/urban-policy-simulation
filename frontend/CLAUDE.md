# CLAUDE.md — Frontend Subsystem

Guidance for Claude Code (and any AI agent) working in the `frontend/` directory of the Urban Policy Simulation. Read this before writing code here.

> [!IMPORTANT]
> **Git Branch Rule:** Pushing directly to the `main` branch is **STRICTLY PROHIBITED**.
> All active development, commits, and pushes must go to the **`dev` branch only**.
> Prior to executing any git commands or modifying files, you must load, read, and strictly adhere to `rule.md` in this directory.

---

## Technical stack & Commands
- **Framework:** React / Vite / TypeScript
- **Styling:** Vanilla CSS / custom components
- **Package Manager:** npm
- **Lint/Format:** eslint, prettier
- **Development Server:** `npm run dev`

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
