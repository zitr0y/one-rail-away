# Filled Favicon Design

## Goal

Improve small-size favicon legibility by changing the existing outlined train mark into a filled silhouette.

## Artwork

`web/public/favicon.svg` remains a 48 × 48 SVG with the existing `viewBox="0 0 200 100"`. Replace the navy stroked train and route line with a solid `#003399` silhouette using the same train geometry. Retain the gold `#ffcc00` star at its current size and position as the sole interior accent.

## Scope

Do not add a background tile, new colors, text, windows, or additional details. The favicon remains referenced by `web/index.html` at `/favicon.svg`.

## Validation

Rasterize the SVG at 16, 32, and 48 pixels to confirm the navy silhouette and gold star remain distinct, then run the web production build.
