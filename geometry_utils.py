"""荣耀 5.0 检测器的基础二维几何工具。坐标内部统一使用米。"""

import math

EPS = 1e-9


def parse_coords(data, skip_first=False):
    """扁平毫米数组转为米坐标点列表。"""
    values = list(data or [])
    if skip_first:
        values = values[1:]
    return [
        (float(values[i]) / 1000.0, float(values[i + 1]) / 1000.0)
        for i in range(0, len(values) - 1, 2)
    ]


def rotated_rect(cx, cy, length, width, angle):
    """返回以 (cx, cy) 为中心、逆时针旋转 angle 度的矩形四角。"""
    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    local = [
        (-length / 2, -width / 2),
        (length / 2, -width / 2),
        (length / 2, width / 2),
        (-length / 2, width / 2),
    ]
    return [
        (cx + x * cos_a - y * sin_a, cy + x * sin_a + y * cos_a)
        for x, y in local
    ]


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def polygon_edges(poly):
    if len(poly) < 2:
        return []
    return [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]


def point_segment_distance(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length2 = dx * dx + dy * dy
    if length2 <= EPS:
        return dist(point, start)
    t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length2
    t = max(0.0, min(1.0, t))
    projection = (start[0] + t * dx, start[1] + t * dy)
    return dist(point, projection)


def point_line_distance(point, start, end):
    """返回点到线段所在无限直线的垂直距离。"""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= EPS:
        return dist(point, start)
    return abs(dx * (start[1] - point[1])
               - (start[0] - point[0]) * dy) / length


def polygon_line_distance(polygon, start, end):
    """返回多边形各顶点到无限直线的最小垂距。"""
    return min(
        (point_line_distance(point, start, end) for point in polygon),
        default=float("inf"),
    )


def polygon_intersection_projection_depth(first, second, axis):
    """返回两多边形重叠部分在 ``axis`` 方向上的投影深度。

    无面积重叠（分离或仅边界接触）返回0。该函数用于量取道具
    沿墙法向进入实体墙的深度。
    """
    length = math.hypot(axis[0], axis[1])
    if length <= EPS:
        raise ValueError("投影轴必须为非零向量")
    try:
        from shapely.geometry import Polygon

        first_shape = Polygon(first)
        second_shape = Polygon(second)
        if not first_shape.is_valid:
            first_shape = first_shape.buffer(0)
        if not second_shape.is_valid:
            second_shape = second_shape.buffer(0)
        overlap = first_shape.intersection(second_shape)
        if overlap.is_empty or overlap.area <= EPS:
            return 0.0

        coordinates = []

        def collect(geometry):
            if geometry.geom_type == "Polygon":
                coordinates.extend(geometry.exterior.coords)
                for ring in geometry.interiors:
                    coordinates.extend(ring.coords)
            elif hasattr(geometry, "geoms"):
                for part in geometry.geoms:
                    collect(part)

        collect(overlap)
        if not coordinates:
            return 0.0
        ux, uy = axis[0] / length, axis[1] / length
        values = [point[0] * ux + point[1] * uy
                  for point in coordinates]
        return max(values) - min(values)
    except ImportError as error:
        raise RuntimeError("计算多边形进墙深度需要Shapely") from error


def _orientation(a, b, c):
    value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if value > EPS:
        return 1
    if value < -EPS:
        return -1
    return 0


def _on_segment(a, b, point):
    return (min(a[0], b[0]) - EPS <= point[0] <= max(a[0], b[0]) + EPS
            and min(a[1], b[1]) - EPS <= point[1] <= max(a[1], b[1]) + EPS)


def segments_intersect(a, b, c, d):
    o1, o2 = _orientation(a, b, c), _orientation(a, b, d)
    o3, o4 = _orientation(c, d, a), _orientation(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    return ((o1 == 0 and _on_segment(a, b, c))
            or (o2 == 0 and _on_segment(a, b, d))
            or (o3 == 0 and _on_segment(c, d, a))
            or (o4 == 0 and _on_segment(c, d, b)))


def segments_distance(a, b, c, d):
    if segments_intersect(a, b, c, d):
        return 0.0
    return min(
        point_segment_distance(a, c, d), point_segment_distance(b, c, d),
        point_segment_distance(c, a, b), point_segment_distance(d, a, b),
    )


def closest_points_on_segments(a, b, c, d):
    """返回两条线段上距离最近的一对点；相交时返回近似交点对。"""
    if segments_intersect(a, b, c, d):
        point = ((a[0] + b[0] + c[0] + d[0]) / 4,
                 (a[1] + b[1] + c[1] + d[1]) / 4)
        return point, point
    candidates = []
    for point, start, end, first in ((a, c, d, True), (b, c, d, True),
                                     (c, a, b, False), (d, a, b, False)):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length2 = dx * dx + dy * dy
        t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / max(length2, EPS)
        t = max(0.0, min(1.0, t))
        projection = (start[0] + t * dx, start[1] + t * dy)
        candidates.append((dist(point, projection), (point, projection) if first
                           else (projection, point)))
    return min(candidates, key=lambda item: item[0])[1]


def segment_polygon_distance(start, end, polygon):
    return min(
        (segments_distance(start, end, a, b) for a, b in polygon_edges(polygon)),
        default=float("inf"),
    )


def polygons_distance(first, second):
    return min(
        (segments_distance(a, b, c, d)
         for a, b in polygon_edges(first)
         for c, d in polygon_edges(second)),
        default=float("inf"),
    )


def _clip_polygon_by_axis(points, axis, limit, keep_greater):
    """用 ``dot(point, axis) >=/<= limit`` 裁剪多边形。"""
    if not points:
        return []

    def value(point):
        return point[0] * axis[0] + point[1] * axis[1]

    def inside(point):
        coordinate = value(point)
        return coordinate >= limit - EPS if keep_greater else coordinate <= limit + EPS

    result = []
    previous = points[-1]
    previous_inside = inside(previous)
    previous_value = value(previous)
    for current in points:
        current_inside = inside(current)
        current_value = value(current)
        if current_inside != previous_inside:
            denominator = current_value - previous_value
            ratio = 0.0 if abs(denominator) <= EPS else (limit - previous_value) / denominator
            result.append((
                previous[0] + (current[0] - previous[0]) * ratio,
                previous[1] + (current[1] - previous[1]) * ratio,
            ))
        if current_inside:
            result.append(current)
        previous = current
        previous_inside = current_inside
        previous_value = current_value
    return result


def edge_directional_polygon_distance(edge, direction, polygon):
    """返回边沿指定垂直方向投影后首次接触多边形的距离。

    ``edge`` 是两个端点，``direction`` 是从边指向外侧的二维向量。
    只有落在边长度投影范围内、且位于指定方向前方的多边形才参与；没有
    接触对象时返回 ``None``。多边形已接触或穿过起始边时返回 ``0.0``。
    """
    if len(edge) != 2 or len(polygon) < 2:
        return None
    start, end = edge
    edge_dx, edge_dy = end[0] - start[0], end[1] - start[1]
    edge_length = math.hypot(edge_dx, edge_dy)
    dir_length = math.hypot(direction[0], direction[1])
    if edge_length <= EPS or dir_length <= EPS:
        raise ValueError("边和投影方向均必须为非零向量")

    tangent = (edge_dx / edge_length, edge_dy / edge_length)
    ray = (direction[0] / dir_length, direction[1] / dir_length)
    # CAD 坐标经过旋转、缩放和 JSON 序列化后会产生微小浮点误差。
    # 点积容差 1e-4 约等于允许偏离严格垂直 0.0057°，仍不会把明显的
    # 斜向投影误判为垂直投影。
    if abs(tangent[0] * ray[0] + tangent[1] * ray[1]) > 1e-4:
        raise ValueError("投影方向必须与输入边垂直")

    # 先将目标多边形裁剪到由输入边向前扫掠形成的无限条带中。
    start_axis = start[0] * tangent[0] + start[1] * tangent[1]
    clipped = _clip_polygon_by_axis(list(polygon), tangent, start_axis, True)
    clipped = _clip_polygon_by_axis(clipped, tangent, start_axis + edge_length, False)
    if not clipped:
        return None

    forward = [
        (point[0] - start[0]) * ray[0] + (point[1] - start[1]) * ray[1]
        for point in clipped
    ]
    nearest, farthest = min(forward), max(forward)
    if farthest < -EPS:
        return None
    if nearest <= EPS:
        return 0.0
    return nearest


def nearest_object_in_edge_direction(edge, direction, objects, exclude=None,
                                     ignored_objects=None):
    """寻找输入边沿指定方向首次接触到的对象。

    候选对象须提供 ``corners`` 多边形属性。返回 ``(distance, object)``；投影
    范围内没有任何对象时返回 ``(None, None)``。``ignored_objects`` 可传入
    单个对象或对象集合，这些对象在投影搜索中会被完全忽略。
    """
    if ignored_objects is None:
        ignored = set()
    elif isinstance(ignored_objects, (list, tuple, set, frozenset)):
        ignored = {id(item) for item in ignored_objects}
    else:
        ignored = {id(ignored_objects)}
    if exclude is not None:
        ignored.add(id(exclude))

    best_distance = None
    best_object = None
    for item in objects:
        if id(item) in ignored:
            continue
        polygon = getattr(item, "corners", None)
        if not polygon:
            continue
        distance = edge_directional_polygon_distance(edge, direction, polygon)
        if distance is None:
            continue
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_object = item
    return best_distance, best_object


def polygon_centroid(poly):
    if not poly:
        return 0.0, 0.0
    return (sum(point[0] for point in poly) / len(poly),
            sum(point[1] for point in poly) / len(poly))


def bbox(poly):
    """返回多边形外接框 ``(minx, miny, maxx, maxy)``。"""
    if not poly:
        return None
    xs = [point[0] for point in poly]
    ys = [point[1] for point in poly]
    return min(xs), min(ys), max(xs), max(ys)


def polygon_area(poly):
    """多边形面积。"""
    if len(poly) < 3:
        return 0.0
    return abs(sum(
        poly[i][0] * poly[(i + 1) % len(poly)][1]
        - poly[(i + 1) % len(poly)][0] * poly[i][1]
        for i in range(len(poly))) / 2.0)


def minimum_rotated_rectangle_dimensions(polygon):
    """返回多边形最小面积旋转外接矩形的 ``(长, 厚, 角度)``。

    不依赖Shapely：依次以多边形每条有效边作为候选长轴，将全部顶点投影
    到该轴及其法轴，取面积最小的外接矩形。长度始终为较大尺寸，厚度为
    较小尺寸，单位与输入坐标一致。
    """
    if len(polygon or []) < 2:
        return None
    best = None
    for start, end in polygon_edges(polygon):
        dx, dy = end[0] - start[0], end[1] - start[1]
        edge_length = math.hypot(dx, dy)
        if edge_length <= EPS:
            continue
        axis = (dx / edge_length, dy / edge_length)
        normal = (-axis[1], axis[0])
        along = [point[0] * axis[0] + point[1] * axis[1]
                 for point in polygon]
        across = [point[0] * normal[0] + point[1] * normal[1]
                  for point in polygon]
        first_size = max(along) - min(along)
        second_size = max(across) - min(across)
        area = first_size * second_size
        angle = math.degrees(math.atan2(axis[1], axis[0])) % 180.0
        candidate = (area, max(first_size, second_size),
                     min(first_size, second_size), angle)
        if best is None or candidate[0] < best[0]:
            best = candidate
    return None if best is None else (best[1], best[2], best[3])


def axis_projection(point, axis, origin=(0.0, 0.0)):
    """返回点相对 ``origin`` 在 ``axis`` 上的有符号投影坐标。"""
    length = math.hypot(axis[0], axis[1])
    if length <= EPS:
        raise ValueError("投影轴必须为非零向量")
    ux, uy = axis[0] / length, axis[1] / length
    return ((point[0] - origin[0]) * ux
            + (point[1] - origin[1]) * uy)


def wall_line_key(start, end, angle_quantum=1.0,
                  offset_quantum=0.05):
    """返回墙边所在直线的规范化分组键。

    迁移自旧版 ``wall_grouping._line_key``。角度和直线偏移量先量化，
    使方向相反或存在微小CAD倾斜的共线墙边稳定落入同一组。
    """
    dx, dy = end[0] - start[0], end[1] - start[1]
    if math.hypot(dx, dy) <= EPS:
        return None
    angle = math.degrees(math.atan2(dy, dx)) % 180.0
    angle_key = round(angle / angle_quantum) * angle_quantum
    radians = math.radians(angle_key)
    normal = (-math.sin(radians), math.cos(radians))
    offset = start[0] * normal[0] + start[1] * normal[1]
    return angle_key, round(offset / offset_quantum) * offset_quantum


def build_wall_runs(wall_polygons, minimum_length=1.0, merge_gap=0.02,
                    minimum_edge_length=0.05):
    """将墙体多边形的共线边合并为完整直线墙段。

    迁移自旧版 ``wall_grouping.build_wall_runs``。返回
    ``[(p1, p2, length), ...]``。同一直线上投影重叠，或投影间隔
    不超过 ``merge_gap`` 的墙边会被合并。
    """
    by_line = {}
    for polygon in wall_polygons:
        for start, end in polygon_edges(polygon):
            if dist(start, end) < minimum_edge_length:
                continue
            key = wall_line_key(start, end)
            if key is not None:
                by_line.setdefault(key, []).append((start, end))

    runs = []
    for edges in by_line.values():
        origin, reference_end = edges[0]
        dx = reference_end[0] - origin[0]
        dy = reference_end[1] - origin[1]
        reference_length = math.hypot(dx, dy)
        if reference_length <= EPS:
            continue
        axis = (dx / reference_length, dy / reference_length)
        ranges = []
        for start, end in edges:
            first = axis_projection(start, axis, origin)
            second = axis_projection(end, axis, origin)
            ranges.append((min(first, second), max(first, second)))
        ranges.sort()
        lower, upper = ranges[0]
        merged = []
        for next_lower, next_upper in ranges[1:]:
            if next_lower <= upper + merge_gap:
                upper = max(upper, next_upper)
            else:
                merged.append((lower, upper))
                lower, upper = next_lower, next_upper
        merged.append((lower, upper))

        for lower, upper in merged:
            length = upper - lower
            if length < minimum_length:
                continue
            start = (origin[0] + lower * axis[0],
                     origin[1] + lower * axis[1])
            end = (origin[0] + upper * axis[0],
                   origin[1] + upper * axis[1])
            runs.append((start, end, length))
    return runs


def project_on_segment(point, start, end):
    """返回点在线段所在直线上的投影参数，线段范围为0–1。"""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= EPS:
        return 0.0
    return ((point[0] - start[0]) * dx
            + (point[1] - start[1]) * dy) / length_squared


def polygon_segment_span(polygon, segment):
    """返回多边形在线段方向上的投影参数范围。"""
    values = [project_on_segment(point, *segment) for point in polygon]
    return (min(values), max(values)) if values else (0.0, 0.0)


def parallel_side_walls(boundary, wall_polygons, storefront_angle,
                        angle_tolerance=12.0, minimum_length=0.50):
    """按门头方向找出门店中心左右两侧的平行内墙面。

    侧墙应与门头近似垂直。候选墙边按其中心在门头方向上的
    投影分到门店中心两侧，每侧取距中心最近的一条，以避免选中
    墙体外皮。返回 ``(left, right, axis)``；无有效对侧墙时返回
    ``None``。``axis`` 为两墙共用的沿墙单位方向。
    """
    if not boundary:
        return None
    center = polygon_centroid(boundary)
    frontage_radians = math.radians(storefront_angle)
    frontage_axis = (math.cos(frontage_radians),
                     math.sin(frontage_radians))
    side_axis = (-frontage_axis[1], frontage_axis[0])

    def angle_difference(first, second):
        difference = abs((first - second) % 180.0)
        return min(difference, 180.0 - difference)

    target_angle = (storefront_angle + 90.0) % 180.0
    negative = []
    positive = []
    for polygon in wall_polygons:
        for edge in polygon_edges(polygon):
            length = dist(*edge)
            if length < minimum_length:
                continue
            angle = math.degrees(math.atan2(
                edge[1][1] - edge[0][1],
                edge[1][0] - edge[0][0])) % 180.0
            if angle_difference(angle, target_angle) > angle_tolerance:
                continue
            midpoint = ((edge[0][0] + edge[1][0]) / 2.0,
                        (edge[0][1] + edge[1][1]) / 2.0)
            offset = axis_projection(midpoint, frontage_axis, center)
            entry = (abs(offset), edge, offset)
            if offset < -EPS:
                negative.append(entry)
            elif offset > EPS:
                positive.append(entry)

    if not negative or not positive:
        return None
    left = min(negative, key=lambda value: value[0])[1]
    right = min(positive, key=lambda value: value[0])[1]
    left_angle = math.degrees(math.atan2(
        left[1][1] - left[0][1], left[1][0] - left[0][0])) % 180.0
    right_angle = math.degrees(math.atan2(
        right[1][1] - right[0][1], right[1][0] - right[0][0])) % 180.0
    if angle_difference(left_angle, right_angle) > angle_tolerance:
        return None
    return left, right, side_axis


def opposite_wall_from_door(door, wall_polygons, interior_polygon,
                            parallel_tolerance=15.0,
                            minimum_distance=0.15):
    """从门中心沿垂直于门口边的店内方向寻找对面墙。

    ``door`` 可传具有 ``polygon`` 属性的门对象或门多边形，前两点
    视为门口边。两个法向中，选择指向 ``interior_polygon`` 中心
    的一侧作为店内方向。函数先调用 ``build_wall_runs`` 合并共线
    短墙段，再在与门口边平行的完整墙段中取射线首次命中者。
    返回包含 ``segment/run_index/length/distance/hit/direction`` 的字典，
    无有效对面墙时返回 ``None``。
    """
    door_polygon = getattr(door, "polygon", door)
    if not door_polygon or len(door_polygon) < 2 or not interior_polygon:
        return None
    start, end = door_polygon[0], door_polygon[1]
    dx, dy = end[0] - start[0], end[1] - start[1]
    door_length = math.hypot(dx, dy)
    if door_length <= EPS:
        return None
    origin = ((start[0] + end[0]) / 2.0,
              (start[1] + end[1]) / 2.0)
    first_normal = (-dy / door_length, dx / door_length)
    center = polygon_centroid(interior_polygon)
    to_center = (center[0] - origin[0], center[1] - origin[1])
    if (first_normal[0] * to_center[0]
            + first_normal[1] * to_center[1]) >= 0:
        direction = first_normal
    else:
        direction = (-first_normal[0], -first_normal[1])

    door_angle = math.degrees(math.atan2(dy, dx)) % 180.0

    def angle_difference(first, second):
        difference = abs((first - second) % 180.0)
        return min(difference, 180.0 - difference)

    ray = (origin, (origin[0] + direction[0],
                    origin[1] + direction[1]))
    candidates = []
    runs = build_wall_runs(
        wall_polygons, minimum_length=0.05, merge_gap=0.02)
    for run_index, (run_start, run_end, run_length) in enumerate(runs):
        segment = (run_start, run_end)
        edge_angle = math.degrees(math.atan2(
            run_end[1] - run_start[1],
            run_end[0] - run_start[0])) % 180.0
        if angle_difference(edge_angle, door_angle) > parallel_tolerance:
            continue
        intersection = line_intersection(ray, segment)
        if intersection is None:
            continue
        point, ray_distance, segment_parameter = intersection
        # direction为单位向量，因此射线参数即为米制距离。
        if (ray_distance <= minimum_distance + EPS
                or not -EPS <= segment_parameter <= 1.0 + EPS):
            continue
        candidates.append((ray_distance, segment, run_index,
                           run_length, point))
    if not candidates:
        return None
    distance, segment, run_index, run_length, hit = min(
        candidates, key=lambda value: value[0])
    return {
        "segment": segment,
        "run_index": run_index,
        "length": run_length,
        "distance": distance,
        "hit": hit,
        "direction": direction,
        "door_center": origin,
    }


def point_in_polygon(point, polygon):
    """射线法判断点是否位于多边形内；边界点视为在内。"""
    if len(polygon) < 3:
        return False
    for start, end in polygon_edges(polygon):
        if point_segment_distance(point, start, end) <= EPS:
            return True
    inside = False
    x, y = point
    previous = polygon[-1]
    for current in polygon:
        if ((current[1] > y) != (previous[1] > y)):
            cross_x = ((previous[0] - current[0]) * (y - current[1])
                       / (previous[1] - current[1]) + current[0])
            if x < cross_x:
                inside = not inside
        previous = current
    return inside


def line_intersection(first_segment, second_segment):
    """返回两条线段所在无限直线的交点及各自参数 ``(point, t, u)``。

    ``t/u`` 位于0–1表示交点落在对应线段范围内；两直线平行时返回
    ``None``。该函数迁移自旧版 ``wall_whitespace._line_intersection``。
    """
    first_start, first_end = first_segment
    second_start, second_end = second_segment
    rx = first_end[0] - first_start[0]
    ry = first_end[1] - first_start[1]
    sx = second_end[0] - second_start[0]
    sy = second_end[1] - second_start[1]
    denominator = rx * sy - ry * sx
    if abs(denominator) <= EPS:
        return None
    qpx = second_start[0] - first_start[0]
    qpy = second_start[1] - first_start[1]
    t = (qpx * sy - qpy * sx) / denominator
    u = (qpx * ry - qpy * rx) / denominator
    point = (first_start[0] + t * rx, first_start[1] + t * ry)
    return point, t, u


def find_inward_perpendicular_pier_boundaries(
        support, wall_runs, first_t=0.0, last_t=1.0,
        interior_polygon=None, attach_tol=0.05, perpendicular_tol=15.0):
    """识别支撑墙左右两侧向室内延伸的垂直墙垛边界。

    本函数迁移自旧版 ``wall_whitespace._pier_boundaries``。参数：

    - ``support``：作为基线的支撑墙段 ``(p1, p2)``；
    - ``wall_runs``：候选墙段，可为 ``(a, b)`` 或 ``(a, b, length)``；
    - ``first_t/last_t``：支撑墙上已有对象覆盖范围的归一化参数；
    - ``interior_polygon``：售卖区多边形；提供时仅接受向其内部延伸的墙段。

    返回 ``(left, right)``。每侧为 ``None`` 或字典，包含墙垛候选墙段、
    交点、支撑墙归一化位置及候选墙段长度。这里只识别垂直短墙的拓扑关系，
    不在此函数中套用300–900mm或430mm规则尺寸。
    """
    support_length = dist(*support)
    if support_length <= EPS:
        return None, None

    def segment_angle(segment):
        start, end = segment
        return math.degrees(math.atan2(
            end[1] - start[1], end[0] - start[0]))

    support_angle = segment_angle(support)
    left = right = None
    for run in wall_runs:
        if len(run) < 2:
            continue
        start, end = run[0], run[1]
        candidate = (start, end)
        candidate_length = dist(start, end)
        if candidate_length <= EPS:
            continue

        difference = abs((support_angle - segment_angle(candidate)) % 180.0)
        difference = min(difference, 180.0 - difference)
        if abs(difference - 90.0) > perpendicular_tol:
            continue

        intersection = line_intersection(support, candidate)
        if intersection is None:
            continue
        point, support_t, candidate_t = intersection
        if not (-attach_tol <= support_t <= 1.0 + attach_tol
                and -attach_tol <= candidate_t <= 1.0 + attach_tol):
            continue

        # 候选墙段必须从支撑墙交点朝售卖区内部延伸。
        if interior_polygon:
            farther = (start if dist(start, point) >= dist(end, point)
                       else end)
            vx, vy = farther[0] - point[0], farther[1] - point[1]
            vector_length = math.hypot(vx, vy)
            if vector_length <= EPS:
                continue
            probe_distance = min(0.08, vector_length * 0.5)
            probe = (point[0] + vx / vector_length * probe_distance,
                     point[1] + vy / vector_length * probe_distance)
            if not point_in_polygon(probe, interior_polygon):
                continue

        axis_t = max(0.0, min(1.0, support_t))
        value = {
            "segment": candidate,
            "intersection": point,
            "support_t": axis_t,
            "length": candidate_length,
        }
        if axis_t <= first_t + 1e-6:
            if left is None or axis_t > left["support_t"]:
                left = value
        if axis_t >= last_t - 1e-6:
            if right is None or axis_t < right["support_t"]:
                right = value
    return left, right


def entrance_side_wall_segments(
        door, wall_segments, frontage_segments=None, interior_polygon=None,
        join_tol=0.45, parallel_tol=15.0, perpendicular_tol=15.0):
    """返回一个入口左右两侧第一次向室内转折的墙段。

    ``door`` 可传门多边形或门对象（具有 ``polygon`` 属性），前两个点被视为
    门口边。``wall_segments`` 是实体墙线段；``frontage_segments`` 是可与门口
    连成入口立面的玻璃墙、短实体墙等线段。

    算法先从门口边向左右吸收端点相连、方向平行的入口立面，再在完整立面
    两端分别寻找第一条近似垂直且朝 ``interior_polygon`` 内部延伸的实体墙。
    返回 ``{"left": ..., "right": ..., "frontage": [...]}``，左右值为
    ``None`` 或包含墙段、连接点和墙长的字典。
    """
    door_polygon = getattr(door, "polygon", door)
    if not door_polygon or len(door_polygon) < 2:
        raise ValueError("门至少需要两个门口边端点")
    door_edge = (door_polygon[0], door_polygon[1])
    door_length = dist(*door_edge)
    if door_length <= EPS:
        raise ValueError("门口边长度必须大于0")

    def normalize_segments(values):
        result = []
        for value in values or []:
            if len(value) < 2:
                continue
            start, end = value[0], value[1]
            if dist(start, end) > EPS:
                result.append((start, end))
        return result

    walls = normalize_segments(wall_segments)
    frontage_candidates = normalize_segments(frontage_segments)

    def angle(segment):
        start, end = segment
        return math.degrees(math.atan2(
            end[1] - start[1], end[0] - start[0])) % 180.0

    def angle_difference(first, second):
        difference = abs((first - second) % 180.0)
        return min(difference, 180.0 - difference)

    def connected(first, second, tolerance):
        return min(
            dist(first[0], second[0]), dist(first[0], second[1]),
            dist(first[1], second[0]), dist(first[1], second[1]),
        ) <= tolerance

    door_angle = angle(door_edge)
    # 门本身是入口立面的种子。玻璃墙和与门平行的短实体墙按端点连通扩展。
    frontage = [door_edge]
    remaining = [
        segment for segment in frontage_candidates
        if angle_difference(angle(segment), door_angle) <= parallel_tol
    ]
    changed = True
    while changed:
        changed = False
        next_remaining = []
        for segment in remaining:
            if any(connected(segment, active, join_tol) for active in frontage):
                frontage.append(segment)
                changed = True
            else:
                next_remaining.append(segment)
        remaining = next_remaining

    ux = (door_edge[1][0] - door_edge[0][0]) / door_length
    uy = (door_edge[1][1] - door_edge[0][1]) / door_length
    origin = door_edge[0]

    def projection(point):
        return ((point[0] - origin[0]) * ux
                + (point[1] - origin[1]) * uy)

    frontage_points = [point for segment in frontage for point in segment]
    left_point = min(frontage_points, key=projection)
    right_point = max(frontage_points, key=projection)

    def inward(segment, connection):
        if not interior_polygon:
            return True
        far = (segment[0] if dist(segment[0], connection) >=
               dist(segment[1], connection) else segment[1])
        vx, vy = far[0] - connection[0], far[1] - connection[1]
        length = math.hypot(vx, vy)
        if length <= EPS:
            return False
        probe_distance = min(0.08, length * 0.5)
        probe = (connection[0] + vx / length * probe_distance,
                 connection[1] + vy / length * probe_distance)
        return point_in_polygon(probe, interior_polygon)

    def first_turn(endpoint):
        candidates = []
        for segment in walls:
            difference = angle_difference(angle(segment), door_angle)
            if abs(difference - 90.0) > perpendicular_tol:
                continue
            endpoint_distance = min(dist(endpoint, segment[0]),
                                    dist(endpoint, segment[1]))
            if endpoint_distance > join_tol:
                continue
            connection = (segment[0] if dist(endpoint, segment[0]) <=
                          dist(endpoint, segment[1]) else segment[1])
            if not inward(segment, connection):
                continue
            candidates.append((endpoint_distance, segment, connection))
        if not candidates:
            return None
        endpoint_distance, segment, connection = min(
            candidates, key=lambda value: value[0])
        return {
            "segment": segment,
            "connection": connection,
            "length": dist(*segment),
            "endpoint_distance": endpoint_distance,
        }

    return {
        "left": first_turn(left_point),
        "right": first_turn(right_point),
        "frontage": frontage,
        "left_endpoint": left_point,
        "right_endpoint": right_point,
    }


def entrance_adjacent_side_wall_runs(
        door, wall_polygons, frontage_polygons=None, interior_polygon=None,
        merge_gap=0.02, join_tol=0.45, parallel_tol=15.0,
        perpendicular_tol=15.0):
    """返回入口左右两侧的完整合并墙段及靠门半段。

    步骤：
    1. 调用 ``build_wall_runs`` 合并被CAD拆分的共线墙边；
    2. 调用 ``entrance_side_wall_segments`` 找到入口立面左右两端
       第一条向店内转折的墙段；
    3. 将该完整墙段从中点分为两半，返回与入口连接点更近的
       ``near_half``。

    ``frontage_polygons`` 可传入玻璃墙等入口立面多边形。返回
    ``{"left": value, "right": value, "frontage": ...}``；每侧 ``value``
    为 ``None`` 或包含 ``full_segment/near_half/length/connection`` 的字典。
    """
    runs = build_wall_runs(
        wall_polygons, minimum_length=0.05, merge_gap=merge_gap)
    wall_segments = [(start, end) for start, end, _length in runs]
    run_lengths = {
        (start, end): length for start, end, length in runs
    }
    frontage_segments = []
    for polygon in frontage_polygons or []:
        frontage_segments.extend(
            edge for edge in polygon_edges(polygon)
            if dist(*edge) > 0.05)

    sides = entrance_side_wall_segments(
        door, wall_segments, frontage_segments, interior_polygon,
        join_tol=join_tol, parallel_tol=parallel_tol,
        perpendicular_tol=perpendicular_tol)

    def describe(turn):
        if turn is None:
            return None
        segment = turn["segment"]
        start, end = segment
        midpoint = ((start[0] + end[0]) / 2.0,
                    (start[1] + end[1]) / 2.0)
        connection = turn["connection"]
        near_endpoint = (start if dist(start, connection)
                         <= dist(end, connection) else end)
        return {
            "full_segment": segment,
            "near_half": (near_endpoint, midpoint),
            "length": run_lengths.get(segment, dist(start, end)),
            "near_half_length": dist(near_endpoint, midpoint),
            "connection": connection,
            "endpoint_distance": turn["endpoint_distance"],
        }

    return {
        "left": describe(sides["left"]),
        "right": describe(sides["right"]),
        "frontage": sides["frontage"],
        "left_endpoint": sides["left_endpoint"],
        "right_endpoint": sides["right_endpoint"],
    }


def is_furniture_on_entrance_side(
        door, furniture, wall_segments, frontage_segments=None,
        interior_polygon=None, wall_distance_tol=0.30,
        angle_tol=12.0, **side_options):
    """判断家具是否贴在指定入口左右侧的第一次垂直转折墙上。

    ``furniture`` 可传家具对象（具有 ``corners`` 属性）或家具多边形。返回
    ``(matched, detail)``；``detail`` 包含命中的 ``left/right``、侧墙和距离。
    """
    furniture_polygon = getattr(furniture, "corners", furniture)
    if not furniture_polygon or len(furniture_polygon) < 2:
        return False, None
    sides = entrance_side_wall_segments(
        door, wall_segments, frontage_segments, interior_polygon,
        **side_options)

    furniture_edges = polygon_edges(furniture_polygon)
    furniture_axis = max(furniture_edges, key=lambda edge: dist(*edge))

    def segment_angle(segment):
        start, end = segment
        return math.degrees(math.atan2(
            end[1] - start[1], end[0] - start[0])) % 180.0

    furniture_angle = segment_angle(furniture_axis)
    for side_name in ("left", "right"):
        side = sides[side_name]
        if side is None:
            continue
        difference = abs((furniture_angle - segment_angle(side["segment"])) % 180.0)
        difference = min(difference, 180.0 - difference)
        if difference > angle_tol:
            continue
        distance = min(
            segments_distance(a, b, side["segment"][0], side["segment"][1])
            for a, b in furniture_edges)
        if distance <= wall_distance_tol:
            return True, {
                "side": side_name,
                "wall": side["segment"],
                "distance": distance,
                "frontage": sides["frontage"],
            }
    return False, {"frontage": sides["frontage"]}


def classify_store_orientation(boundary, storefront_angle, center=None):
    """按门店中心横/竖截线与门头方向判断横店或竖店。

    ``boundary`` 是 CAD 门店净平面边界；``storefront_angle`` 是门头方向角，
    取值单位为度且 0° 表示世界坐标横向。函数过门店中心分别作水平线和
    竖直线，线向两侧延伸到首次碰到边界为止：

    - 与门头方向夹角更小的截线长度作为面宽 ``width``；
    - 另一条截线长度作为进深 ``depth``；
    - ``width / depth >= 1`` 为 ``horizontal``（横店），否则为
      ``vertical``（竖店）。

    默认中心取边界轴对齐包围盒中心，也可通过 ``center`` 显式传入。返回
    字典包含分类、中心、两条截线及长度、门头匹配方向、面宽、进深和比例。
    边界无效、中心不在门店内或任一方向无法同时碰到两侧边界时抛出
    ``ValueError``。
    """
    if len(boundary or []) < 3:
        raise ValueError("门店边界至少需要3个点")
    bounds = bbox(boundary)
    if center is None:
        center = ((bounds[0] + bounds[2]) / 2.0,
                  (bounds[1] + bounds[3]) / 2.0)
    center = (float(center[0]), float(center[1]))
    if not point_in_polygon(center, boundary):
        raise ValueError("门店中心不在CAD门店边界内")

    def axis_intersections(axis):
        # axis=0：水平截线，记录交点X；axis=1：竖直截线，记录交点Y。
        fixed_axis = 1 - axis
        fixed_value = center[fixed_axis]
        values = []
        for start, end in polygon_edges(boundary):
            first = start[fixed_axis] - fixed_value
            second = end[fixed_axis] - fixed_value
            if abs(first) <= EPS and abs(second) <= EPS:
                # 边界边与截线重合时，其两个端点都是有效碰撞位置。
                values.extend((start[axis], end[axis]))
                continue
            if ((first <= EPS and second >= -EPS)
                    or (second <= EPS and first >= -EPS)):
                denominator = end[fixed_axis] - start[fixed_axis]
                if abs(denominator) <= EPS:
                    continue
                ratio = (fixed_value - start[fixed_axis]) / denominator
                if -EPS <= ratio <= 1.0 + EPS:
                    values.append(
                        start[axis] + ratio * (end[axis] - start[axis]))

        values.sort()
        unique = []
        for value in values:
            if not unique or abs(value - unique[-1]) > 1e-7:
                unique.append(value)
        coordinate = center[axis]
        negative = [value for value in unique if value <= coordinate + EPS]
        positive = [value for value in unique if value >= coordinate - EPS]
        if not negative or not positive:
            raise ValueError("中心截线未能同时碰到门店两侧边界")
        low, high = max(negative), min(positive)
        if high - low <= EPS:
            raise ValueError("中心截线在门店边界内没有有效长度")
        if axis == 0:
            segment = ((low, center[1]), (high, center[1]))
        else:
            segment = ((center[0], low), (center[0], high))
        return segment, high - low

    horizontal_segment, horizontal_length = axis_intersections(0)
    vertical_segment, vertical_length = axis_intersections(1)

    angle = float(storefront_angle) % 180.0

    def angle_difference(first, second):
        difference = abs((first - second) % 180.0)
        return min(difference, 180.0 - difference)

    horizontal_difference = angle_difference(angle, 0.0)
    vertical_difference = angle_difference(angle, 90.0)
    frontage_axis = ("horizontal" if horizontal_difference <= vertical_difference
                     else "vertical")
    if frontage_axis == "horizontal":
        width, depth = horizontal_length, vertical_length
    else:
        width, depth = vertical_length, horizontal_length
    ratio = width / depth
    store_type = "horizontal" if ratio >= 1.0 else "vertical"
    return {
        "store_type": store_type,
        "store_type_cn": "横店" if store_type == "horizontal" else "竖店",
        "center": center,
        "horizontal_segment": horizontal_segment,
        "horizontal_length": horizontal_length,
        "vertical_segment": vertical_segment,
        "vertical_length": vertical_length,
        "storefront_angle": angle,
        "frontage_axis": frontage_axis,
        "width": width,
        "depth": depth,
        "ratio": ratio,
    }


def experience_table_array_region(scheme, align_tol=0.05):
    """根据体验台和开机服务台短边共线关系生成桌类阵列区域。

    返回 Shapely Polygon/MultiPolygon；桌类道具少于两张、没有共线分组，
    或当前环境未安装 Shapely 时返回 ``None``。
    """
    try:
        from shapely.geometry import box
        from shapely.ops import unary_union
    except ImportError:
        return None

    desks = [item for item in scheme.furniture
             if item.category in {"experience_table", "service_desk"}]
    if len(desks) < 2:
        return None

    def short_orientation(desk):
        edge = (desk.corners[1], desk.corners[2])
        return "horizontal" if abs(edge[1][0] - edge[0][0]) >= abs(edge[1][1] - edge[0][1]) else "vertical"

    def short_offsets(desk, orientation):
        edges = ((desk.corners[1], desk.corners[2]),
                 (desk.corners[3], desk.corners[0]))
        axis = 1 if orientation == "horizontal" else 0
        return tuple((a[axis] + b[axis]) / 2.0 for a, b in edges)

    groups = []
    for orientation in ("horizontal", "vertical"):
        oriented = [desk for desk in desks if short_orientation(desk) == orientation]
        offsets = {id(desk): short_offsets(desk, orientation) for desk in oriented}
        unseen = set(range(len(oriented)))
        while unseen:
            seed = unseen.pop()
            component = {seed}
            pending = [seed]
            while pending:
                index = pending.pop()
                joined = []
                for other_index in unseen:
                    if min(abs(a - b) for a in offsets[id(oriented[index])]
                           for b in offsets[id(oriented[other_index])]) <= align_tol:
                        joined.append(other_index)
                for other_index in joined:
                    unseen.remove(other_index)
                    component.add(other_index)
                    pending.append(other_index)
            if len(component) >= 2:
                groups.append((orientation, [oriented[index] for index in component]))

    rectangles = []
    for orientation, group in groups:
        points = [point for desk in group for point in desk.corners]
        rect = box(min(point[0] for point in points), min(point[1] for point in points),
                   max(point[0] for point in points), max(point[1] for point in points))
        rectangles.append((rect.area, orientation, rect))
    if not rectangles:
        return None

    rectangles.sort(key=lambda item: item[0])
    bridges = []
    for (_area, orientation, smaller), (_next_area, _next_orientation, larger) in zip(
            rectangles, rectangles[1:]):
        if smaller.intersects(larger) or smaller.touches(larger):
            continue
        sx0, sy0, sx1, sy1 = smaller.bounds
        lx0, ly0, lx1, ly1 = larger.bounds
        scx, scy = (sx0 + sx1) / 2.0, (sy0 + sy1) / 2.0
        lcx, lcy = (lx0 + lx1) / 2.0, (ly0 + ly1) / 2.0
        if orientation == "horizontal":
            y0, y1 = (sy1, ly0) if lcy >= scy else (ly1, sy0)
            target_x = min(max(scx, lx0), lx1)
            bridges.append(box(min(sx0, target_x), min(y0, y1),
                               max(sx1, target_x), max(y0, y1)))
        else:
            x0, x1 = (sx1, lx0) if lcx >= scx else (lx1, sx0)
            target_y = min(max(scy, ly0), ly1)
            bridges.append(box(min(x0, x1), min(sy0, target_y),
                               max(x0, x1), max(sy1, target_y)))
    return unary_union([item[2] for item in rectangles] + bridges).buffer(0)
