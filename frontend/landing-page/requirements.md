# Simulationsys — Frontend Requirements

> Urban Policy Simulation Interface  
> Design system aligned with [`design.md`](./design.md)

---

## Overview

This document defines the technical requirements and constraints for the Simulationsys frontend. The interface functions as a sophisticated urban policy simulation command center — data-driven, slightly skeuomorphic, and optimized for long working sessions.

---

## Tech Stack

| Category            | Technology                              | Version   | Notes                                      |
|---------------------|-----------------------------------------|-----------|--------------------------------------------|
| **Framework**       | [Next.js](https://nextjs.org/)          | 15.x      | App Router, React Server Components       |
| **Language**        | TypeScript                              | 5.x       | Strict mode enabled                        |
| **Styling**         | Tailwind CSS                            | 4.x       | Utility-first; custom tokens from design.md|
| **Animation**       | [GSAP](https://gsap.com/)               | 3.x       | Core + `@gsap/react` hooks                 |
| **Smooth Scroll**   | [Lenis](https://lenis.studiofreight.com/) | latest  | GSAP-integrated smooth scrolling           |
| **Font**            | Inter (Google Fonts)                    | —         | Via `next/font/google`                     |
| **Icons**           | Solar Icon Set                          | —         | Linear style, 1.5px stroke                 |
| **Linting**         | ESLint                                  | 9.x       | `next/core-web-vitals` config              |
| **Package Manager** | npm                                     | —         | Lock file committed                        |
| **Containerisation**| Docker                                  | —         | Multi-stage build; `next start` server     |

---

## Design Constraints

All implementation must stay aligned with `design.md`. Key constraints are summarised below.

### Colors

| Token            | Value       | Role                                   |
|------------------|-------------|----------------------------------------|
| `primary`        | `#A3907A`   | Main accent — key actions & emphasis   |
| `secondary`      | `#8C8273`   | Secondary emphasis & metrics           |
| `tertiary`       | `#A1AE7A`   | Positive policy outcome highlights     |
| `neutral`        | `#7A756D`   | Backgrounds, surfaces, chrome          |
| `background`     | `#EAE5DF`   | Page background                        |
| `text-primary`   | `#8C8273`   | Body & heading text                    |
| `text-secondary` | `#7A756D`   | Supporting / muted text                |
| `border`         | `#EAE5DF`   | Hairline dividers                      |
| `accent`         | `#A3907A`   | Interactive accent                     |

### Typography

All text uses **Inter** with thin weights to maximise data readability.

| Scale        | Size  | Weight | Line Height | Notes                          |
|--------------|-------|--------|-------------|--------------------------------|
| `display-lg` | 96px  | 200    | 96px        | Uppercase, `-0.025em` tracking |
| `body-md`    | 12px  | 200    | 16px        | Default body                   |
| `label-md`   | 14px  | 300    | 20px        | UI labels, buttons             |

### Spacing & Layout

- **Base unit:** 4px
- **Scale:** 1px, 4px, 8px, 10px, 12px, 14px, 16px, 20px
- **Layout:** Full-bleed grid with `max-w-7xl` centred container
- **Section padding:** 24px / 56px
- **Card padding:** 8px / 12px / 16px / 18px
- **Gaps:** 6px, 8px, 12px, 16px

### Elevation & Surfaces

- **Surface style:** Glass-first (`backdrop-blur-md`, `backdrop-blur-xl`)
- **Border:** `1px solid #EAE5DF` and `1px solid #DCD6CC`
- **Shadow system (dual-shadow):**
  - Outer: `rgba(0,0,0,0.08)` drop-shadow
  - Inner: `inset 0 1px 0 white`
- **Blur:** 12px (cards), 24px (overlays)
- **Gradient border shell:** `linear-gradient(#fff, #FDFBF7, #DCD6CC)` as 1px wrapper

### Radius System

`2px` → `3px` → `4px` → `5px` → `6px` → `8px` (no pill exceptions on controls)

- Buttons: `5px`
- Cards: `7px`–`11px`
- Large bezels: `15px`

### Motion

| Property      | Values                                              |
|---------------|-----------------------------------------------------|
| Level         | Moderate                                            |
| Durations     | 150ms, 300ms, 1000ms                                |
| Easings       | `ease`, `ease-in-out`, `cubic-bezier(0.4, 0, 0.2, 1)` |
| Hover patterns| colour, text, shadow — `transition-colors duration-300` |
| Icons         | `group-hover:translate-x-1` for directional cues   |
| Reveals       | Opacity fade + gentle slide-in for data rows       |

---

## Animation Guidelines (GSAP + Lenis)

### Lenis — Smooth Scroll

- Wrap the root layout with a `<LenisProvider>` component
- Integrate Lenis with GSAP's `ScrollTrigger` via `lenis.on('scroll', ScrollTrigger.update)`
- Use `lerp: 0.1` for a controlled, data-dashboard feel (not springy)
- Respect `prefers-reduced-motion` — disable Lenis when set

### GSAP — Animations

- Use `@gsap/react` hooks (`useGSAP`) for all component-level animations
- All animations must use the `duration` and `ease` values from the motion spec above
- Prefer `gsap.context()` for cleanup on unmount
- Use `ScrollTrigger` for section reveals (opacity + `y: 20` → `y: 0`)
- Avoid elastic or spring easings — linear / ease-in-out only

---

## Component Requirements

### Buttons

- **Primary:** text `#2C2C2A`, radius `5px`, padding `14px`, multi-layer shadow (`inset 0 1px 0 white`)
- **Link:** text `#8C8273`, radius `0`, padding `0`

### Cards

- Gradient border shell wrapper (1px, `linear-gradient(#fff, #FDFBF7, #DCD6CC)`)
- Inner surface: radius `5px`, padding `16px`, `backdrop-blur-md`
- Dual shadow: outer subtle drop + inset white highlight

### Navigation Dock

- Fixed bottom anchor
- `backdrop-blur-xl` + layered shadows
- Appears visually detached / floating

---

## Project Structure

```
frontend/
├── public/                  # Static assets
├── src/
│   ├── app/
│   │   ├── layout.tsx       # Root layout (Lenis + fonts)
│   │   ├── page.tsx         # Home / dashboard entry
│   │   └── globals.css      # Tailwind base + custom tokens
│   ├── components/
│   │   ├── ui/              # Buttons, Cards, Badge etc.
│   │   ├── layout/          # Navigation dock, grid wrappers
│   │   ├── simulation/      # Policy controls, data tables
│   │   └── map/             # City visualisation layer
│   ├── hooks/               # useGSAP, useLenis, useSimulation
│   ├── lib/                 # Utility functions, constants
│   └── types/               # TypeScript interfaces
├── design.md                # Design system reference
├── requirements.md          # ← this file
├── Dockerfile               # Multi-stage Next.js build
├── nginx.conf               # (kept for reference)
└── package.json
```

---

## Do's and Don'ts

### ✅ Do
- Keep all spacing on the 4px grid
- Use Glass surface treatment consistently, especially over map layers
- Reuse the gradient border shell for all primary cards
- Keep corner radii within the `2–8px` family
- Use GSAP `useGSAP` hook with proper cleanup context
- Integrate Lenis scroll position with GSAP `ScrollTrigger`

### ❌ Don't
- Don't introduce accent colours outside the defined palette
- Don't mix shadow/blur recipes that break the depth system
- Don't use elastic or spring easings — keep motion controlled
- Don't exceed `8px` radius on buttons or badges
- Don't add Lenis to server components — keep it client-side only
