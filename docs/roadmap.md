## RunRun Roadmap

Milestones are tracked as checkboxes. Status here must mirror the current implementation state.

### MVP: Single-file HTML+JS app
- [x] Create `docs/roadmap.md` with milestones and tasks
- [x] Scaffold single-page `index.html` with tabs and inputs
- [x] Implement core data schema and normalization functions
- [x] Add mock aggregators (RunSignUp, Sporthive) with sample payloads
- [x] Implement merge/dedupe logic and unit tests
- [x] Build Data tab editable review and JSON editor
- [x] Implement JSON import/export and local snapshots
- [x] Add basic visualizations (trend, pace vs distance, negative splits)
- [x] Create `tests/index.html` to run unit tests for core functions
- [ ] Stub weather enrichment and condition flags with thresholds UI
- [ ] Polish UI/UX, status messages, and error handling

### Phase 2: Enrichment & UX
- [ ] Weather enrichment and condition thresholds UI
- [ ] Map view, percentiles, and elevation overlays (if data available)

### Phase 3: Advanced analytics
- [ ] Age grading, calendar heatmap, and course difficulty scoring
- [ ] Shareable, sanitized exports; presets and themes

### Notes
- Keep the app single-document for the UI (`index.html`), use a separate browser test page (`tests/index.html`).
- Prefer vanilla JS and SVG for visuals to avoid dependencies.
- Ensure ToS transparency and local-only data persistence.

