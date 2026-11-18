"""布局检测图的通用尺寸标注工具。"""

import math

import geometry_utils as gu


def _parallel_angle(angle_a, angle_b, tolerance=15.0):
    diff = abs((angle_a - angle_b) % 180.0)
    return min(diff, 180.0 - diff) <= tolerance


def _projection_overlap(edge_a, edge_b):
    ax, ay = edge_a[0]
    bx, by = edge_a[1]
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length <= gu.EPS:
        return 0.0
    ux, uy = dx / length, dy / length
    values = [(point[0] - ax) * ux + (point[1] - ay) * uy for point in edge_b]
    return max(0.0, min(length, max(values)) - max(0.0, min(values)))


def _measurement_positions(edge_a, edge_b):
    """返回同一平行边间距的多个可滑动尺寸线位置。"""
    origin = edge_a[0]
    dx, dy = edge_a[1][0] - origin[0], edge_a[1][1] - origin[1]
    length = math.hypot(dx, dy)
    if length <= gu.EPS:
        return []
    ux, uy = dx / length, dy / length
    projected = [(point[0] - origin[0]) * ux + (point[1] - origin[1]) * uy
                 for point in edge_b]
    low, high = max(0.0, min(projected)), min(length, max(projected))
    if high < low:
        return []
    fractions = (0.5, 0.25, 0.75, 0.1, 0.9, 0.0, 1.0)
    positions = []
    for fraction in fractions:
        value = low + (high - low) * fraction
        p1 = (origin[0] + ux * value, origin[1] + uy * value)
        bx, by = edge_b[1][0] - edge_b[0][0], edge_b[1][1] - edge_b[0][1]
        length2 = bx * bx + by * by
        t = ((p1[0] - edge_b[0][0]) * bx +
             (p1[1] - edge_b[0][1]) * by) / max(length2, gu.EPS)
        t = max(0.0, min(1.0, t))
        p2 = (edge_b[0][0] + bx * t, edge_b[0][1] + by * t)
        positions.append((p1, p2))
    return positions


def _lines_conflict(first, second, tolerance=0.06):
    """尺寸线相交、重合或距离过近时视为冲突。"""
    return gu.segments_distance(first[0], first[1], second[0], second[1]) < tolerance


def _same_wall_size_key(item, angle_tolerance=5.0, wall_tolerance=0.20):
    """返回靠墙道具的“同墙同尺寸”分组键；非靠墙道具返回 None。"""
    wall_categories = {
        "light_box", "background_lightbox_cabinet",
        "imaging_cabinet", "lightbox_cabinet",
        "theme_cabinet", "authorization_sign",
    }
    if item.category not in wall_categories:
        return None
    angle = round((item.angle % 180.0) / angle_tolerance) * angle_tolerance
    rad = math.radians(angle)
    # 长轴法向投影相同，表示道具位于同一条墙面基线上。
    wall_offset = -item.cx * math.sin(rad) + item.cy * math.cos(rad)
    return (
        round(angle, 3),
        round(wall_offset / wall_tolerance),
        round(item.length, 3),
        round(item.width, 3),
    )


def _deduplicate_same_wall_size(measurements):
    """同一面墙、相同尺寸的靠墙道具仅保留最小体验台间距标注。"""
    kept = []
    grouped = {}
    for measured in measurements:
        key = _same_wall_size_key(measured["item"])
        if key is None:
            kept.append(measured)
            continue
        current = grouped.get(key)
        if current is None or measured["distance"] < current["distance"]:
            grouped[key] = measured
    kept.extend(grouped.values())
    return kept


def nearest_parallel_edge_gap(poly_a, poly_b, angle_tolerance=15.0,
                              overlap_min=0.05):
    """返回两个多边形最近的有效平行边测量结果。"""
    best = None
    for index_a, edge_a in enumerate(gu.polygon_edges(poly_a)):
        angle_a = math.degrees(math.atan2(
            edge_a[1][1] - edge_a[0][1], edge_a[1][0] - edge_a[0][0]))
        for index_b, edge_b in enumerate(gu.polygon_edges(poly_b)):
            angle_b = math.degrees(math.atan2(
                edge_b[1][1] - edge_b[0][1], edge_b[1][0] - edge_b[0][0]))
            if not _parallel_angle(angle_a, angle_b, angle_tolerance):
                continue
            if _projection_overlap(edge_a, edge_b) < overlap_min:
                continue
            p1, p2 = gu.closest_points_on_segments(
                edge_a[0], edge_a[1], edge_b[0], edge_b[1])
            distance = gu.dist(p1, p2)
            if best is None or distance < best["distance"]:
                best = {"distance": distance, "p1": p1, "p2": p2,
                        "edge_a": index_a, "edge_b": index_b,
                        "positions": _measurement_positions(edge_a, edge_b)}
    return best


def draw_distance_measurement(ax, measured, label=None, color="#D71313",
                              gid="distance_measurement"):
    """绘制带端点、虚线和数值标签的尺寸线。"""
    p1, p2 = measured["p1"], measured["p2"]
    label = label or f"间距{measured['distance']:.2f}m"
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color,
            linewidth=2.2, linestyle="--", zorder=8)
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], "o",
            color=color, markersize=4, zorder=9)
    mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    annotation = ax.annotate(
        label, mid, xytext=(0, 0), textcoords="offset points",
        fontsize=8, color=color, fontweight="bold", ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                  edgecolor=color, alpha=0.9), zorder=10)
    annotation.set_gid(gid)


def avoid_label_overlaps(fig, ax, gid="distance_measurement"):
    """尝试移动尺寸标签，避免标签相互重叠。"""
    labels = [text for text in ax.texts if text.get_gid() == gid]
    if not labels:
        return
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    occupied = [text.get_window_extent(renderer).expanded(1.03, 1.12)
                for text in ax.texts
                if text.get_gid() != gid and text.get_visible() and text.get_text()]
    offsets = [(0, 0), (0, 14), (0, -14), (0, 28), (0, -28),
               (28, 0), (-28, 0), (40, 16), (-40, 16)]
    for label in labels:
        for offset in offsets:
            label.set_position(offset)
            fig.canvas.draw()
            box = label.get_window_extent(renderer).expanded(1.03, 1.12)
            if not any(box.overlaps(other) for other in occupied):
                occupied.append(box)
                break


def experience_region_spacing_measurements(scheme):
    """返回每个非桌类道具到体验台/开机服务台区域的最小有效平行间距。

    体验台区域由全部体验台和开机服务台共同构成；实际尺寸仍量到最近桌类
    道具的实体平行边，避免阵列外接区域中的空白通道被误当成实体边界。
    每个其它道具最多返回一条。
    """
    desks = [item for item in scheme.furniture
             if item.category in {"experience_table", "service_desk"}
             and item.corners]
    if not desks:
        return []

    # 执行区域识别，后续阵列范围标注和穿插检测可复用同一结果。
    region = gu.experience_table_array_region(scheme)
    measurements = []
    for item in scheme.furniture:
        if item.category in {"experience_table", "service_desk"} or not item.corners:
            continue
        candidates = []
        for desk in desks:
            measured = nearest_parallel_edge_gap(item.corners, desk.corners)
            if measured is not None:
                candidates.append((measured["distance"], measured, desk))
        if not candidates:
            continue
        _distance, measured, desk = min(candidates, key=lambda candidate: candidate[0])
        measured.update({
            "item": item,
            "desk": desk,
            "region": region,
            "label": f"间距{measured['distance']:.2f}m",
            "color": "#1565C0",
        })
        measurements.append(measured)

    measurements = _deduplicate_same_wall_size(measurements)

    # 在不改变每件道具最小距离的前提下，沿平行边滑动尺寸线以避免重合。
    occupied = []
    for measured in sorted(measurements, key=lambda item: item["distance"]):
        positions = measured.get("positions") or [(measured["p1"], measured["p2"])]
        chosen = None
        for position in positions:
            if not any(_lines_conflict(position, line) for line in occupied):
                chosen = position
                break
        if chosen is None:
            chosen = positions[0]
        measured["p1"], measured["p2"] = chosen
        occupied.append(chosen)
    return measurements


def draw_experience_region_spacing(fig, ax, scheme):
    """绘制每个其它道具到体验台/开机服务台区域的唯一最小平行间距。"""
    gid = "experience_region_spacing"
    measurements = experience_region_spacing_measurements(scheme)
    for measured in measurements:
        draw_distance_measurement(
            ax, measured, label=measured["label"], color=measured["color"], gid=gid)
    avoid_label_overlaps(fig, ax, gid=gid)
    return measurements


def _directional_contact_points(edge, direction, polygon, distance):
    """取得定向投影距离对应的起点和目标多边形接触点。"""
    start, end = edge
    dx, dy = end[0] - start[0], end[1] - start[1]
    edge_length = math.hypot(dx, dy)
    direction_length = math.hypot(direction[0], direction[1])
    if edge_length <= gu.EPS or direction_length <= gu.EPS:
        return None
    tangent = (dx / edge_length, dy / edge_length)
    ray = (direction[0] / direction_length, direction[1] / direction_length)
    start_axis = start[0] * tangent[0] + start[1] * tangent[1]
    clipped = gu._clip_polygon_by_axis(list(polygon), tangent, start_axis, True)
    clipped = gu._clip_polygon_by_axis(clipped, tangent, start_axis + edge_length, False)
    if not clipped:
        return None
    target = min(
        clipped,
        key=lambda point: ((point[0] - start[0]) * ray[0] +
                           (point[1] - start[1]) * ray[1]),
    )
    source = (target[0] - ray[0] * distance,
              target[1] - ray[1] * distance)
    return source, target


def draw_rule17_violations(fig, ax, scheme):
    """仅绘制总体规则18中不符合的体验台边定向投影距离。"""
    from rules import experience_table as experience_rules

    gid = "rule17_violation_measurement"
    measurements = []
    for desk, other, is_long, distance, edge_index in experience_rules._spacing_pairs(scheme):
        invalid = (
            distance < 1.0 - experience_rules.DISTANCE_EPS or
            distance > 1.8 + experience_rules.DISTANCE_EPS
            if is_long else
            distance < 0.8 - experience_rules.DISTANCE_EPS
        )
        if not invalid or other is None or not math.isfinite(distance):
            continue
        edge = gu.polygon_edges(desk.corners)[edge_index]
        midpoint = ((edge[0][0] + edge[1][0]) / 2.0,
                    (edge[0][1] + edge[1][1]) / 2.0)
        direction = (midpoint[0] - desk.cx, midpoint[1] - desk.cy)
        points = _directional_contact_points(edge, direction, other.corners, distance)
        if points is None:
            continue
        p1, p2 = points
        measured = {
            "distance": distance,
            "p1": p1,
            "p2": p2,
            "desk": desk,
            "item": other,
            "label": f"规则18 不符合 {distance:.2f}m",
            "color": "#D71313",
        }
        measurements.append(measured)
        draw_distance_measurement(
            ax, measured, label=measured["label"], color=measured["color"], gid=gid)
    avoid_label_overlaps(fig, ax, gid=gid)
    return measurements


def _rule21_openings(ctx):
    """返回规则21参与检测的玻璃墙/开敞式入口轮廓。"""
    return [
        ("glass" if opening.kind in {"glassWall", "glassDoor"} else "open",
         opening.polygon)
        for opening in ctx.openings
        if opening.kind in {"glassWall", "glassDoor", "door"}
        and len(opening.polygon) >= 2
    ]


def _polygon_main_angle(polygon):
    """多边形最长边的方向（0–180°）。"""
    edges = gu.polygon_edges(polygon)
    if not edges:
        return None
    start, end = max(edges, key=lambda edge: gu.dist(*edge))
    return math.degrees(
        math.atan2(end[1] - start[1], end[0] - start[0])) % 180


def _segment_polygon_measurement(edge, polygon):
    """返回输入边到多边形边界的最短距离及尺寸线端点。"""
    best = None
    for target_edge in gu.polygon_edges(polygon):
        p1, p2 = gu.closest_points_on_segments(
            edge[0], edge[1], target_edge[0], target_edge[1])
        distance = gu.dist(p1, p2)
        if best is None or distance < best["distance"]:
            best = {"distance": distance, "p1": p1, "p2": p2}
    return best


def _polygon_polygon_measurement(first, second):
    """返回两个多边形边界的最短距离及真实最近点。"""
    best = None
    for first_edge in gu.polygon_edges(first):
        measured = _segment_polygon_measurement(first_edge, second)
        if measured is None:
            continue
        if best is None or measured["distance"] < best["distance"]:
            best = measured
    return best


def rule21_violation_measurements(ctx, scheme):
    """计算规则21中不符合的体验台—出入口净距尺寸。"""
    measurements = []
    desks = [item for item in scheme.furniture
             if item.category == "experience_table" and item.corners]
    for desk in desks:
        desk_edges = gu.polygon_edges(desk.corners)
        edge_lengths = [gu.dist(*edge) for edge in desk_edges]
        edge_is_long = [
            abs(length - desk.length) < abs(length - desk.width)
            for length in edge_lengths
        ]
        edge_angles = [
            math.degrees(math.atan2(
                edge[1][1] - edge[0][1], edge[1][0] - edge[0][0])) % 180
            for edge in desk_edges
        ]

        for opening_type, polygon in _rule21_openings(ctx):
            opening_angle = _polygon_main_angle(polygon)
            if opening_angle is None:
                continue
            parallel_is_long = None
            for index, edge in enumerate(desk_edges):
                if not _parallel_angle(edge_angles[index], opening_angle, 15.0):
                    continue
                parallel_is_long = edge_is_long[index]
                break
            if parallel_is_long is None:
                continue

            # 与规则21一致：平行边决定阈值类型，尺寸线则标在两个
            # 完整轮廓的真实最近点之间。
            best = _polygon_polygon_measurement(desk.corners, polygon)
            if best is None:
                continue
            best["is_long"] = parallel_is_long

            if opening_type == "glass":
                required = 2.0 if best["is_long"] else 1.8
                opening_label = "玻璃墙"
            else:
                required = 0.8 if best["is_long"] else 0.6
                opening_label = "铺位线"
            if best["distance"] >= required - 0.05:
                continue
            side = "长边" if best["is_long"] else "短边"
            best.update({
                "desk": desk,
                "opening_type": opening_type,
                "required": required,
                "label": (f"规则21 {side}距{opening_label}"
                          f"{best['distance']:.2f}m（≥{required:.1f}m）"),
                "color": "#D71313",
            })
            measurements.append(best)
    return measurements


def draw_rule21_violations(fig, ax, ctx, scheme):
    """规则21不符合时，仅绘制造成不符合的净距尺寸线。"""
    gid = "rule21_violation_measurement"
    measurements = rule21_violation_measurements(ctx, scheme)
    for measured in measurements:
        draw_distance_measurement(
            ax, measured, label=measured["label"],
            color=measured["color"], gid=gid)
    avoid_label_overlaps(fig, ax, gid=gid)
    return measurements
