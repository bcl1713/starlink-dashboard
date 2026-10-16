"""Collect actual painted PDF rectangles, failing closed on complex paths/clips."""

FILL = {b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}
STROKE = {b"S", b"s", b"B", b"B*", b"b", b"b*"}
END = FILL | STROKE | {b"n"}


def painted_rectangles(page):
    height = float(page.mediabox.top)
    state = {
        "fill": [0, 0, 0],
        "stroke": [0, 0, 0],
        "fillAlpha": 1,
        "strokeAlpha": 1,
        "clip": [0, 0, float(page.mediabox.right), height],
    }
    stack, path, rectangles, outlines = [], [], [], []
    complex_path, pending_clip = False, False
    resources = page.get("/Resources")
    resources = resources.get_object() if resources else {}
    graphics = resources.get("/ExtGState")
    graphics = graphics.get_object() if graphics else {}

    def intersection(left, right):
        if left is None or right is None:
            return None
        result = [
            max(left[0], right[0]),
            max(left[1], right[1]),
            min(left[2], right[2]),
            min(left[3], right[3]),
        ]
        return result if result[0] < result[2] and result[1] < result[3] else None

    def visit(operator, operands, cm, _tm):
        nonlocal state, complex_path, pending_clip
        if operator == b"q":
            stack.append(state.copy())
        elif operator == b"Q" and stack:
            state = stack.pop()
        elif operator in {b"rg", b"RG", b"g", b"G", b"k", b"K"}:
            values = list(map(float, operands))
            color = values if len(values) == 3 else values * 3
            if len(values) == 4:
                color = [1 - min(1, channel + values[3]) for channel in values[:3]]
            state["fill" if operator.islower() else "stroke"] = color
        elif operator == b"gs":
            settings = graphics.get(operands[0])
            settings = settings.get_object() if settings else {}
            state["fillAlpha"] = float(settings.get("/ca", state["fillAlpha"]))
            state["strokeAlpha"] = float(settings.get("/CA", state["strokeAlpha"]))
        elif operator == b"re":
            x, y, width, rect_height = map(float, operands)
            a, b, c, d, e, f = map(float, cm)
            corners = [
                (a * px + c * py + e, b * px + d * py + f)
                for px, py in [
                    (x, y),
                    (x + width, y),
                    (x + width, y + rect_height),
                    (x, y + rect_height),
                ]
            ]
            axis_aligned = all(
                abs(left[0] - right[0]) < 0.001 or abs(left[1] - right[1]) < 0.001
                for left, right in zip(corners, corners[1:] + corners[:1])
            )
            if not axis_aligned:
                complex_path = True
            xs, ys = zip(*corners)
            path.append([min(xs), height - max(ys), max(xs), height - min(ys)])
        elif operator in {b"m", b"l", b"c", b"v", b"y"}:
            complex_path = True
        elif operator in {b"W", b"W*"}:
            pending_clip = True
        elif operator in END:
            # Multiple subpaths can punch holes under either winding rule.
            # Such a path cannot prove an entire solid rectangular band.
            box = path[0] if len(path) == 1 and not complex_path else None
            visible = intersection(box, state["clip"])
            if visible and operator in FILL and state["fillAlpha"] == 1:
                rectangles.append({"bounds": visible, "fill": state["fill"][:]})
            if (
                visible
                and operator in STROKE
                and state["strokeAlpha"] == 1
                and all(
                    abs(a - b) < 0.015
                    for a, b in zip(state["stroke"], [0.451, 0.318, 0.141])
                )
            ):
                outlines.append(visible)
            if pending_clip:
                state["clip"] = intersection(state["clip"], box)
            path.clear()
            complex_path, pending_clip = False, False

    page.extract_text(visitor_operand_before=visit)
    return rectangles, outlines
