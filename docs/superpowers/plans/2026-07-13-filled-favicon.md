# Filled Favicon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the outlined favicon train with a filled navy silhouette while retaining its gold star.

**Architecture:** Edit only `web/public/favicon.svg`; `web/index.html` already references it. The SVG preserves its 48px dimensions and 200×100 viewBox.

**Tech Stack:** SVG, Inkscape, Vite.

## Global Constraints

- Navy is `#003399`; gold is `#ffcc00`.
- No background tile or extra train details.

---

### Task 1: Draw and verify the filled favicon

**Files:**
- Modify: `web/public/favicon.svg`

- [x] **Step 1: Replace the outlined mark with the filled silhouette**

Use a solid navy train body and route-line path, retaining the existing gold star:

```xml
<path d="M4 77 H38 V46 Q38 36 48 36 H118 Q136 36 146 50 L156 68 Q160 76 152 80 H196 V83 H152 Q149 83 147 80 L143 73 Q139 67 132 67 H48 Q44 67 44 71 V83 H4 Z" fill="#003399"/>
<text x="60" y="74" font-size="30" fill="#ffcc00">★</text>
```

- [x] **Step 2: Rasterize at favicon sizes**

```bash
for size in 16 32 48; do inkscape web/public/favicon.svg --export-width=$size --export-height=$size --export-filename=/tmp/favicon-$size.png; done
identify /tmp/favicon-16.png /tmp/favicon-32.png /tmp/favicon-48.png
```

Expected: all images are square at their requested sizes and retain a distinct gold star.

- [x] **Step 3: Build and commit**

```bash
cd web && npm run build
git add public/favicon.svg docs/superpowers/plans/2026-07-13-filled-favicon.md
git commit -m "feat(brand): fill favicon train silhouette"
```

Expected: Vite exits 0 and the commit contains only the favicon and plan.
