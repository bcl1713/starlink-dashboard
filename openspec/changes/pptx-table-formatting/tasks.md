## 1. Table Font Size

- [x] 1.1 In `pptx_builder.py`, change header row font size from `Pt(10)` to `Pt(8)`
- [x] 1.2 In `pptx_builder.py`, change data row font size from `Pt(9)` to `Pt(8)`

## 2. Segment Column Header

- [x] 2.1 In `pptx_builder.py`, change the first entry in `columns_to_show` from `"Segment #"` to `""` (empty string) so the header cell is blank while data rows still show segment numbers

## 3. Verify

- [x] 3.1 Export a test mission as PPTX and confirm the segment column header is blank and all table text renders at 8pt without overflow
