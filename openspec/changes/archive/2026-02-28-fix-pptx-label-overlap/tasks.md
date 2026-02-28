## 1. Add dependency

- [x] 1.1 Add `adjustText` to backend requirements (requirements.txt / pyproject.toml)

## 2. Refactor label placement

- [x] 2.1 Collect all `ax.text()` label objects (departure, arrival, mission event POIs) into a single list instead of placing them independently with fixed offsets
- [x] 2.2 Call `adjust_text()` on the collected labels with conservative force parameters (`force_text=(0.5, 0.5)`, `force_points=(0.5, 0.5)`) and gray leader line styling (`arrowstyle='->'`, `color='gray'`, `lw=0.5`)

## 3. Verify

- [x] 3.1 Generate a PPTX export for a mission with closely-spaced POIs and confirm labels are readable and non-overlapping
- [x] 3.2 Generate a PPTX export for a mission with well-spaced POIs and confirm labels remain close to their markers with no unnecessary displacement
