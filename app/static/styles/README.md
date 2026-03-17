# Unified Style System

This directory contains the design-system based CSS layers.

## Layers
- `00-tokens.css`: colors, spacing, radius, typography, shadow, z-index, motion tokens.
- `01-base.css`: reset/base defaults and global shell layout.
- `02-components.css`: reusable components and legacy class aliases.
- `03-utilities.css`: small helper utilities.
- `pages/*.css`: page-specific layout and unique behavior styles.

## Legacy to new class mapping
- `.app` -> `.layout-app`
- `.form-container` -> `.panel.panel-form`
- `.controls` -> `.toolbar`
- `.submit-btn` -> `.btn.btn--success`
- `.file-drop` -> `.dropzone`
- `.upload-label` -> `.btn-upload`
- `.delete-btn` -> `.btn.btn--danger`
- `.output` -> `.log-panel`
- `.modal-btn` -> `.btn.btn--accent`
- `.hidden` -> `.is-hidden`

Note: JS signaling classes are intentionally unchanged: `.hover`, `.expanded`, `.drag-over`, `.hidden`, `.active`.
