# Logo Font and Crop Design

## Goal

Make the editable lockup render correctly in Inkscape and remove its unused vertical canvas space, while keeping the web header asset an exact visual mirror.

## Source of truth

`design/logo/onestopeurope-lockup-A1.svg` remains the canonical, editable logo. Its live wordmark uses Barlow at weight 800. Install the Barlow font family in the user's per-user font directory and refresh the font cache so Inkscape resolves the text without fallback.

## SVG synchronization

Determine the visible artwork bounds, including stroke widths. Keep the existing 600-unit width and replace each SVG's 100-unit-high viewBox with the tight vertical bounds. Update `width` and `height` on the editable source to match; the header asset relies on its viewBox only. Copy the cropped source artwork into `web/src/assets/header-logo.svg`, omitting only source-specific editor metadata and the navy preview rectangle so the header retains its current transparent background behavior.

## Validation

Use Inkscape's command-line bounding-box export and raster previews to confirm that neither artwork is clipped, the two assets share matching visible geometry, and the source text resolves to Barlow. The web build must still complete successfully.

## Scope

No logo redraw, color change, or horizontal crop is included. The web header asset must be regenerated whenever the source artwork is edited.
