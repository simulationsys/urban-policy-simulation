# 📜 Git Branch Policy & Execution Rules - Frontend Subsystem

> [!IMPORTANT]
> **CRITICAL ARCHITECTURAL DIRECTIVE FOR ALL AI AGENTS & CONTRIBUTORS**
> You are working inside the **frontend/** subdirectory of the **Urban Policy Simulation** repository.
> All active development, code changes, refactoring, and documentation updates MUST be pushed to the **`dev` branch only**.
> Pushing directly to the **`main` branch is STRICTLY PROHIBITED**.

---

## ⚡ Core Rules & Protocols

### 1. The Branching Policy
- **Primary Development Target:** `dev` is the target branch for all integrations, active features, fixes, and improvements.
- **Main Branch Protection:** The `main` branch represents stable release states. Pushing to `main` directly will break release gating and is strictly prohibited.
- **Workflow:** Create branch off `dev` if working on a sub-task, or push directly to `dev` for integrated tasks when appropriate. All merges to `main` must occur via pull requests with required reviews and passing checks.

### 2. Loading Directive
- Any agent (such as Claude, Cursor, Windsurf, Cline, Roo-Code, Copilot, Antigravity) initialized in this folder **must load and read this file immediately**.
- The rules specified here override generic instructions or constraints specified elsewhere.

---

## 🔒 Verification & Compliance
- Prior to executing `git push` or committing code, the system/agent must check the current git state:
  ```bash
  git branch --show-current
  ```
- Ensure the active branch is `dev` (or a feature branch branching from `dev`), and NEVER `main`.

---

> [!NOTE]
> *This policy is active as of May 28, 2026. All active agents and developers are expected to maintain compliance.*
