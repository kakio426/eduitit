## Upstream Source

- Repository: `https://github.com/edwardkim/rhwp`
- Package: `rhwp-studio`
- Pinned commit: `70d9e2d704d88da2e81baa8b09e21523593efa18`

This directory is the source of truth for the embedded `rhwp` editor that powers
`doccollab`.

Rules for updates:

- Apply product-specific embed changes here, not directly in
  `doccollab/static/doccollab/rhwp-studio`.
- Rebuild this workspace and sync its `dist/` output into
  `doccollab/static/doccollab/rhwp-studio`.
- Keep the pinned upstream commit updated in this file when the vendor snapshot
  changes.
