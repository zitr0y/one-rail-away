# Logo Font and Crop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the editable A1 logo render with Barlow Bold and remove unused vertical canvas, while keeping the header SVG visually identical.

**Architecture:** `design/logo/onestopeurope-lockup-A1.svg` is canonical. Both assets use identical artwork coordinates and live Barlow 800 text; the header omits only source-editor metadata and the navy preview rectangle. Their viewBoxes crop vertically to `0 34 600 52.875`.

**Tech Stack:** SVG 1.1, Inkscape 1.4.4, Fontconfig, Vite.

## Global Constraints

- Do not alter logo colors, artwork geometry, or horizontal bounds.
- Keep Barlow Bold (800) as live text in the editable source.
- `web/src/assets/header-logo.svg` is a derived transparent-background counterpart of the source.

---

### Task 1: Verify the local edit font

**Files:**
- Verify: `$HOME/.local/share/fonts/Barlow-Bold.ttf`

**Interfaces:**
- Produces: a Fontconfig-resolvable `Barlow:style=Bold` face for Inkscape.

- [x] **Step 1: Verify the requested font is already installed**

Run:

```bash
fc-match -v 'Barlow:style=Bold' | rg 'family:|style:|file:'
```

Expected: `family: "Barlow"`, `style: "Bold"`, and `$HOME/.local/share/fonts/Barlow-Bold.ttf`. No download is needed when that exact face is present.

- [x] **Step 2: Verify Inkscape resolves the source text**

Run:

```bash
inkscape --export-id=text8 --export-id-only --export-text-to-path --export-type=svg --export-filename=/tmp/onestopeurope-wordmark.svg design/logo/onestopeurope-lockup-A1.svg
rg 'font-family:Barlow|<path' /tmp/onestopeurope-wordmark.svg
```

Expected: the exported wordmark contains Barlow-derived paths, not a missing-glyph fallback.

### Task 2: Crop and synchronize both SVGs

**Files:**
- Modify: `design/logo/onestopeurope-lockup-A1.svg`
- Modify: `web/src/assets/header-logo.svg`

**Interfaces:**
- Consumes: source artwork and the `Barlow` 800 font from Task 1.
- Produces: both assets use `viewBox="0 34 600 52.875"`; the source has `width="600" height="52.875"`.

- [x] **Step 1: Update the editable source canvas**

Change the root attributes in `design/logo/onestopeurope-lockup-A1.svg` to:

```xml
viewBox="0 34 600 52.875"
width="600"
height="52.875"
```

The bounds span from the train outline's top stroke at y=34 through the right terminal circle's bottom stroke at y=86.875. Leave the 600-unit preview rectangle and all artwork unchanged.

- [x] **Step 2: Regenerate the transparent header counterpart**

Make `web/src/assets/header-logo.svg` use the exact source artwork coordinates and live `Barlow, sans-serif` weight 800 text, with:

```xml
viewBox="0 34 600 52.875"
```

Do not include the source's navy `<rect>` or Inkscape/Sodipodi metadata. Update the comment to say it is derived from the editable source and must not be independently edited.

- [x] **Step 3: Check source/header geometry agreement**

Run:

```bash
rg -n 'viewBox|font-family|font-weight|<rect' design/logo/onestopeurope-lockup-A1.svg web/src/assets/header-logo.svg
```

Expected: both use the same viewBox and Barlow 800; only the source has the preview rectangle.

### Task 3: Render and build verification

**Files:**
- Verify: `design/logo/onestopeurope-lockup-A1.svg`
- Verify: `web/src/assets/header-logo.svg`

**Interfaces:**
- Consumes: synchronized SVGs from Task 2.
- Produces: unclipped raster previews and a successful production bundle.

- [x] **Step 1: Rasterize both assets at their drawing area**

Run:

```bash
inkscape design/logo/onestopeurope-lockup-A1.svg --export-area-page --export-type=png --export-filename=/tmp/a1-lockup.png
inkscape web/src/assets/header-logo.svg --export-area-page --export-type=png --export-filename=/tmp/header-lockup.png
identify /tmp/a1-lockup.png /tmp/header-lockup.png
```

Expected: both PNGs have the same 600:52.875 aspect ratio and neither has clipped white/gold artwork at its top or bottom edge.

- [x] **Step 2: Build the web app**

Run:

```bash
cd web && npm run build
```

Expected: Vite exits 0.

- [x] **Step 3: Commit the implementation**

Run:

```bash
git add design/logo/onestopeurope-lockup-A1.svg web/src/assets/header-logo.svg docs/superpowers/plans/2026-07-13-logo-font-and-crop.md
git commit -m "fix(logo): crop lockup and synchronize header asset"
```

Expected: one commit containing the crop, synchronized asset, and plan.
