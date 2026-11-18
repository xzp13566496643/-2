"""体验台布局规则。

当前文件实现的模块内规则（本文件独立从1开始）：
1. 优先选择3米体验台，3米无法布局时依次选择2.4米等较小规格。
   规则内容：优先选择3米体验台；3米体验台无法布局时次选2.4米体验台，
   依次往下降直至给出最佳布局。
2. 体验台3–5节，开机服务台1–2节，允许指定组合。
   规则内容：体验台标准4节、可选3–5节；开机服务台标准1节、可选
   1–2节，允许3+1、4+1、5+1、4+2组合。
3. 体验台到其它道具的垂直投影净距。
   规则内容：体验台长边与其它道具（含体验台）通道净距1.0–1.8m，
   短边与其它道具通道净距不小于0.8m。
4. 体验台和开机服务台对齐。
   规则内容：所有体验台的长边、短边应分别保持对齐，整体布局规整。
5. 横、纵向通道净距一致性。
   规则内容：在满足入口最小净距要求的前提下，横、纵向排布的各条
   通道净距应分别一致；玻璃门入口净距不得小于内部横向通道净距。
7. 体验台与出入口净距。
   规则内容：体验台短边平行出入口时，距玻璃墙不小于1.8m、距开敞式
   出入口铺位线不小于0.6m；长边平行时分别不小于2.0m和0.8m；有
   卷闸设施时距卷闸不小于0.4m。
8. 柱子周边空旷度。
   规则内容：柱子周边无法摆放体验台但仍有空间时，可用沙发柜、绿植
   展柜组合补充；入口侧包柱空白可用绿植手机支架槽补充。
9. 体验台短边与柱子净距。
   规则内容：体验台应优选与柱子中心对齐或同边对齐；体验台短边距
   柱子0.7–1.2m，不过人时可以紧贴。
10. 体验台长边与柱子净距。
    规则内容：体验台长边平行于柱子时，距柱子的间距应大于0.9m。
11. 体验台与柱子角对角净距。
    规则内容：体验台与柱子呈角对角布置时，体验台四角与柱角的间距
    应大于0.7m。
12. 根据体验台数量、长度规格和模型名称识别主题，并与规定的主题组合
    逐项比较；主题无法识别、规格不属于对应分支或组合不完全一致均不符合。
    规则内容：5张2m/2.4m体验台采用M+数字+X+PC+M，5张3m体验台
    采用M+V+数字+X+PC；4张采用M+数字+X+PC；3张采用M+数字+PC。
"""

from collections import Counter
import math

import geometry_utils as gu
import layout_data as L
from findings import (
    Finding, SEV_ERROR, SEV_INFO, SEV_WARN,
    STATUS_PASS, STATUS_WARN,
)

MODULE = "experience_table"
DISTANCE_EPS = 0.001


def _tables(scheme):
    return [f for f in scheme.furniture if f.category == "experience_table"]


def _services(scheme):
    return [f for f in scheme.furniture if f.category == "service_desk"]


def _has_mid_room_columns(ctx):
    """判断售卖区中间是否有柱子，完整沿用旧版实现。"""
    if not ctx.columns or not ctx.walls:
        return False
    for column in ctx.columns:
        if len(column) < 3:
            continue
        center = gu.polygon_centroid(column)
        minimum_distance = min(
            gu.point_segment_distance(center, wall[0], wall[1])
            for wall in ctx.walls
            if len(wall) >= 2
        )
        if minimum_distance > 1.0:
            return True
    return False


def _line_offset(x, y, angle_deg):
    """点到原点沿 angle_deg 方向线的法向偏移。"""
    rad = math.radians(angle_deg % 180)
    return -x * math.sin(rad) + y * math.cos(rad)


def _glass_doors(ctx):
    """从统一数据层取玻璃门多边形。"""
    return [opening.polygon for opening in ctx.openings
            if opening.kind == "glassDoor"]


def _spacing_pairs(scheme):
    """每张体验台的每条边沿外侧垂直方向寻找最近的其它道具。

    返回 ``(体验台, 最近道具, 是否长边, 距离, 边序号)``。距离直接使用
    ``nearest_object_in_edge_direction``；搜索时仅忽略当前体验台自身，其它
    体验台仍参与。没有投影对象时，最近道具为 ``None``、距离为正无穷。
    """
    pairs = []
    desks = _tables(scheme)
    for desk in desks:
        for edge_index, edge in enumerate(gu.polygon_edges(desk.corners)):
            edge_len = gu.dist(*edge)
            is_long = abs(edge_len - desk.length) < abs(edge_len - desk.width)
            midpoint = ((edge[0][0] + edge[1][0]) / 2.0,
                        (edge[0][1] + edge[1][1]) / 2.0)
            outward = (midpoint[0] - desk.cx, midpoint[1] - desk.cy)
            gap, other = gu.nearest_object_in_edge_direction(
                edge, outward, scheme.furniture, exclude=desk)
            pairs.append((desk, other, is_long,
                          float("inf") if gap is None else gap, edge_index))
    return pairs


def _rule_1(scheme):
    """模块规则1：优先选择3米体验台，当3米体验台无法布局时次选2.4米体验台，依次往下降直至给出最佳布局。"""
    desks = _tables(scheme)
    three = [d for d in desks if abs(d.length - 3.0) <= 0.05]
    ok = bool(three)
    detail = (f"共布置{len(desks)}张体验台，其中{len(three)}张为3m体验台" if ok
              else (f"共布置{len(desks)}张体验台，未布置3m体验台" if desks else "方案中未识别到体验台"))
    return Finding(
        "1", MODULE, "优先选择3m体验台，无法布局时依次选择较小规格",
        STATUS_PASS if ok else STATUS_WARN,
        SEV_INFO if ok else SEV_WARN, scheme.index,
        detail if ok else detail + "；警告：未采用优先3m规格")


def _rule_2(scheme):
    """模块规则2：体验台数量标准4节，可选范围3–5节；开机服务台标准1节，可选范围1–2节；允许组合为3+1、4+1、5+1、4+2。"""
    count = (len(_tables(scheme)), len(_services(scheme)))
    ok = count in {(3, 1), (4, 1), (5, 1), (4, 2)}
    return Finding("2", MODULE, "体验台3–5节、开机服务台1–2节，组合为3+1/4+1/5+1/4+2", ok,
                   SEV_INFO if ok else SEV_ERROR, scheme.index,
                   f"体验台{count[0]}节，开机服务台{count[1]}节")


def _rule_3(scheme):
    """模块规则3：逐边检测到其它道具（含体验台）的垂直投影净距；长边1.0–1.8米，短边不小于0.8米。"""
    bad, checked = [], []
    pairs = _spacing_pairs(scheme)
    side_counts = {}
    for desk, other, is_long, gap, edge_index in pairs:
        key = (id(desk), is_long)
        side_counts[key] = side_counts.get(key, 0) + 1
        side_number = side_counts[key]
        invalid = (gap < 1.0 - DISTANCE_EPS or gap > 1.8 + DISTANCE_EPS
                   if is_long else gap < 0.8 - DISTANCE_EPS)
        side = "长边" if is_long else "短边"
        target = other.name if other is not None else "无投影道具"
        distance_text = f"{gap:.2f}m" if math.isfinite(gap) else "∞"
        checked.append(f"{desk.name}{side}{side_number}→{target}：{distance_text}")
        if invalid:
            req = "1.0–1.8m" if is_long else "≥0.8m"
            bad.append(
                f"{desk.name}{side}{side_number}→{target}：{distance_text}（要求{req}）")
    return Finding("3", MODULE, "体验台到其它道具（含体验台）：长边净距1.0–1.8m、短边净距≥0.8m", not bad,
                   SEV_INFO if not bad else SEV_ERROR, scheme.index,
                   ("不符合：" + "；".join(bad) + "。全部测量：" + "；".join(checked)
                    if bad else "全部测量：" + "；".join(checked)))


def _rule_4(scheme):
    """模块规则4：连接上下左右相邻体验台/开机服务台中心，偏差≤3°。"""
    desks, services = _tables(scheme), _services(scheme)
    items, bad = desks + services, []
    if len(items) < 2:
        bad.append("体验台和开机服务台合计少于2件，无法形成相邻中心连线")

    def spans(item):
        xs = [point[0] for point in item.corners]
        ys = [point[1] for point in item.corners]
        return min(xs), max(xs), min(ys), max(ys)

    bounds = {id(item): spans(item) for item in items}
    labels = {
        id(item): f"D{index}"
        for index, item in enumerate(
            sorted(desks, key=lambda value: (value.cx, value.cy, value.name)), 1)
    }
    labels.update({
        id(item): f"S{index}"
        for index, item in enumerate(
            sorted(services, key=lambda value: (value.cx, value.cy, value.name)), 1)
    })
    pairs = {}
    for desk in items:
        x0, x1, y0, y1 = bounds[id(desk)]
        nearest = {"left": None, "right": None, "down": None, "up": None}
        for other in items:
            if other is desk:
                continue
            ox0, ox1, oy0, oy1 = bounds[id(other)]
            dx, dy = other.cx - desk.cx, other.cy - desk.cy
            y_overlap = min(y1, oy1) >= max(y0, oy0) - gu.EPS
            x_overlap = min(x1, ox1) >= max(x0, ox0) - gu.EPS
            direction = None
            forward = None
            if y_overlap and dx > gu.EPS:
                direction, forward = "right", dx
            elif y_overlap and dx < -gu.EPS:
                direction, forward = "left", -dx
            elif x_overlap and dy > gu.EPS:
                direction, forward = "up", dy
            elif x_overlap and dy < -gu.EPS:
                direction, forward = "down", -dy
            if direction is None:
                continue
            current = nearest[direction]
            if current is None or forward < current[0]:
                nearest[direction] = (forward, other)
        for value in nearest.values():
            if value is None:
                continue
            other = value[1]
            key = tuple(sorted((id(desk), id(other))))
            pairs[key] = (desk, other)

    checked = []
    if len(items) >= 2 and not pairs:
        bad.append("未识别到上下左右相邻的体验台或开机服务台")
    for desk, other in pairs.values():
        dx, dy = other.cx - desk.cx, other.cy - desk.cy
        angle = abs(math.degrees(math.atan2(dy, dx))) % 180.0
        deviation = min(angle, abs(angle - 90.0), 180.0 - angle)
        description = (f"{labels[id(desk)]}-{labels[id(other)]}中心连线"
                       f"{angle:.2f}°，偏差{deviation:.2f}°")
        checked.append(description)
        if deviation > 3.0 + gu.EPS:
            bad.append(description + "＞3°")
    return Finding("4", MODULE, "体验台与开机服务台长边、短边分别保持对齐", not bad,
                   SEV_INFO if not bad else SEV_ERROR, scheme.index,
                   ("不符合：" + "；".join(bad) + "。全部连线：" + "；".join(checked)
                    if bad else "全部连线：" + "；".join(checked)))


def _rule_5(ctx, scheme):
    """模块规则5：体验台和开机服务台共同参与通道净距一致性判断。"""
    h_gaps, v_gaps = [], []
    desks = _tables(scheme) + _services(scheme)
    if len(desks) >= 2:
        def projected_interval(corners, angle_deg):
            rad = math.radians(angle_deg)
            values = [x * math.cos(rad) + y * math.sin(rad) for x, y in corners]
            return min(values), max(values)

        def interval_gap(a_min, a_max, b_min, b_max):
            if a_max < b_min - 0.01:
                return b_min - a_max
            if b_max < a_min - 0.01:
                return a_min - b_max
            return 0.0

        short_groups = {}
        long_groups = {}
        for desk in desks:
            short_key = round(_line_offset(desk.cx, desk.cy, desk.angle + 90), 2)
            short_groups.setdefault(short_key, []).append(
                (desk, *projected_interval(desk.corners, desk.angle + 90)))

            long_key = round(_line_offset(desk.cx, desk.cy, desk.angle), 2)
            long_groups.setdefault(long_key, []).append(
                (desk, *projected_interval(desk.corners, desk.angle)))

        for desks_in_row in short_groups.values():
            if len(desks_in_row) < 2:
                continue
            desks_in_row.sort(key=lambda item: item[1])
            for index in range(len(desks_in_row) - 1):
                _, a0, a1 = desks_in_row[index]
                _, b0, b1 = desks_in_row[index + 1]
                gap = interval_gap(a0, a1, b0, b1)
                if gap > 0.01:
                    h_gaps.append(round(gap, 2))

        for desks_in_column in long_groups.values():
            if len(desks_in_column) < 2:
                continue
            desks_in_column.sort(key=lambda item: item[1])
            for index in range(len(desks_in_column) - 1):
                _, a0, a1 = desks_in_column[index]
                _, b0, b1 = desks_in_column[index + 1]
                gap = interval_gap(a0, a1, b0, b1)
                if gap > 0.01:
                    v_gaps.append(round(gap, 2))

        h_gaps = sorted(set(h_gaps))
        v_gaps = sorted(set(v_gaps))

    inconsistent = []
    if len(h_gaps) >= 2 and max(h_gaps) - min(h_gaps) > 0.2:
        inconsistent.append(f"横向通道宽窄不均{h_gaps}")
    if len(v_gaps) >= 2 and max(v_gaps) - min(v_gaps) > 0.2:
        inconsistent.append(f"纵向通道宽窄不均{v_gaps}")

    door_failures = []
    glass_doors = _glass_doors(ctx)
    if glass_doors and h_gaps:
        horizontal_reference = min(h_gaps)
        for door in glass_doors:
            nearest_distance, nearest_desk = float("inf"), None
            for desk in desks:
                distance = gu.polygons_distance(desk.corners, door)
                if distance < nearest_distance:
                    nearest_distance, nearest_desk = distance, desk
            if nearest_desk is None:
                continue
            short_distances = [
                gu.segment_polygon_distance(
                    nearest_desk.corners[1], nearest_desk.corners[2], door),
                gu.segment_polygon_distance(
                    nearest_desk.corners[3], nearest_desk.corners[0], door),
            ]
            minimum_short = min(short_distances)
            if minimum_short < horizontal_reference - 0.05:
                door_failures.append(
                    f"玻璃门入口净距{minimum_short:.2f}m < "
                    f"横向通道{horizontal_reference:.2f}m（{nearest_desk.name}）")

    failures = inconsistent + door_failures
    detail = ("；".join(failures) if failures
              else f"横向通道{h_gaps}、纵向通道{v_gaps} 均一致")
    if glass_doors and not h_gaps:
        detail += "；无内部横向通道，玻璃门入口净距无法比较"
    return Finding(
        "5", MODULE, "体验台/开机服务台横、纵通道净距一致；入口净距≥内部横向通道",
        not failures, SEV_INFO if not failures else SEV_ERROR, scheme.index, detail)


def _rule_7(ctx, scheme):
    """模块规则7：体验台与玻璃墙、开敞式出入口的分级净距。

    平行判断与旧项目一致：体验台边与出入口最长边的夹角不超过15°。
    本阶段不检测卷闸。
    """
    def polygon_direction(polygon):
        edges = gu.polygon_edges(polygon)
        if not edges:
            return None
        start, end = max(edges, key=lambda edge: gu.dist(*edge))
        return math.degrees(
            math.atan2(end[1] - start[1], end[0] - start[0])) % 180

    def edges_parallel(first_angle, second_angle, tolerance=15.0):
        difference = abs((first_angle % 180) - (second_angle % 180))
        return min(difference, 180 - difference) <= tolerance

    openings = [
        ("glass" if opening.kind in {"glassWall", "glassDoor"} else "open",
         opening.polygon)
        for opening in ctx.openings
        if opening.kind in {"glassWall", "glassDoor", "door"}
        and len(opening.polygon) >= 2
    ]

    failures = []
    checked = []
    for desk in _tables(scheme):
        desk_edges = gu.polygon_edges(desk.corners)
        edge_lengths = [gu.dist(start, end) for start, end in desk_edges]
        edge_is_long = [
            abs(length - desk.length) < abs(length - desk.width)
            for length in edge_lengths
        ]
        edge_angles = [
            math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 180
            for start, end in desk_edges
        ]

        for opening_type, polygon in openings:
            opening_angle = polygon_direction(polygon)
            if opening_angle is None:
                continue

            nearest_is_long = None
            for index, ((start, end), is_long) in enumerate(
                    zip(desk_edges, edge_is_long)):
                if not edges_parallel(edge_angles[index], opening_angle):
                    continue
                # 平行边只用于确定本次应用长边还是短边阈值。
                # 同一组对边类型相同，找到任一平行边即可。
                nearest_is_long = is_long
                break

            if nearest_is_long is None:
                continue

            # 净距按体验台整体轮廓到出入口整体轮廓的最短距离计算，
            # 不限定最近点必须落在上述平行边上。
            nearest_distance = gu.polygons_distance(desk.corners, polygon)

            side = "长边" if nearest_is_long else "短边"
            opening_label = "玻璃墙" if opening_type == "glass" else "铺位线"
            if opening_type == "glass":
                required = 2.0 if nearest_is_long else 1.8
            else:
                required = 0.8 if nearest_is_long else 0.6
            measurement = (
                f"{desk.name}{side}距{opening_label}{nearest_distance:.2f}m"
                f"（要求≥{required:.1f}m）")
            checked.append(measurement)
            if nearest_distance < required - 0.05:
                failures.append(measurement)

    if failures:
        detail = "不符合：" + "；".join(failures)
    elif checked:
        detail = "全部测量均满足：" + "；".join(checked)
    else:
        detail = "未识别到与出入口平行的体验台边"
    return Finding(
        "7", MODULE,
        "体验台与出入口净距：短边∥玻璃墙≥1.8m/铺位线≥0.6m；"
        "长边∥玻璃墙≥2.0m/铺位线≥0.8m",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_8(ctx, scheme):
    """模块规则8：每根柱子到最近道具障碍物的净距不得大于2.7米。"""
    columns = [column for column in ctx.columns if len(column) >= 2]
    obstacles = [item for item in scheme.furniture if item.corners]

    if not columns:
        return Finding(
            "8", MODULE, "柱子到最近道具障碍物的净距≤2.7m",
            True, SEV_INFO, scheme.index, "未识别到柱子")

    distances = []
    too_open = []
    for index, column in enumerate(columns, 1):
        nearest = min(
            (gu.polygons_distance(column, item.corners) for item in obstacles),
            default=float("inf"),
        )
        distances.append((index, nearest))
        if nearest > 2.7 + DISTANCE_EPS:
            too_open.append((index, nearest))

    if too_open:
        values = "；".join(
            f"柱{index}最近道具距离"
            + (f"{distance:.2f}m" if math.isfinite(distance) else "∞")
            for index, distance in too_open
        )
        detail = f"警告：周围过于空旷：{values}"
    else:
        detail = "；".join(
            f"柱{index}最近道具距离{distance:.2f}m"
            for index, distance in distances
        )
    return Finding(
        "8", MODULE, "柱子到最近道具障碍物的净距≤2.7m",
        STATUS_PASS if not too_open else STATUS_WARN,
        SEV_INFO if not too_open else SEV_WARN,
        scheme.index, detail)


def _rule_9(ctx, scheme):
    """模块规则9：体验台短边距柱0.7–1.2m，不过人时可紧贴。

    复用旧版判定：每根柱子仅检查真实边到边距离最近的一张体验台；
    通过柱心在体验台局部坐标中的位置识别短边关系。净距≤0.05m视为
    “不过人时紧贴”并允许；当前输入无人流通道属性，无法进一步区分。
    """
    columns = [column for column in ctx.columns if len(column) >= 3]
    desks = _tables(scheme)
    if not columns:
        return Finding(
            "9", MODULE, "体验台短边距柱0.7–1.2m，不过人时可紧贴",
            True, SEV_INFO, scheme.index, "未识别到柱子")
    if not desks:
        return Finding(
            "9", MODULE, "体验台短边距柱0.7–1.2m，不过人时可紧贴",
            False, SEV_ERROR, scheme.index, "未识别到体验台")

    violations = []
    checked = []
    skipped = []
    for column_index, column in enumerate(columns, 1):
        desk = min(
            desks, key=lambda item: L.furniture_to_polygon_distance(item, column))
        column_center = gu.polygon_centroid(column)
        local_long, local_short = L.point_in_furniture_local(desk, column_center)
        relation, _center_gap = L.classify_point_edge(
            local_long, local_short, desk.length, desk.width)

        if relation != "short":
            skipped.append(f"柱{column_index}-{desk.name}为{relation}关系")
            continue

        short_gap = min(
            gu.segment_polygon_distance(
                desk.corners[1], desk.corners[2], column),
            gu.segment_polygon_distance(
                desk.corners[3], desk.corners[0], column),
        )
        if short_gap <= 0.05 + DISTANCE_EPS:
            checked.append(
                f"柱{column_index}-{desk.name}短边紧贴{short_gap:.2f}m")
        elif short_gap < 0.7 - DISTANCE_EPS or short_gap > 1.2 + DISTANCE_EPS:
            violations.append(
                f"柱{column_index}-{desk.name}短边距离{short_gap:.2f}m"
                "（要求0.7–1.2m，或紧贴）")
        else:
            checked.append(
                f"柱{column_index}-{desk.name}短边距离{short_gap:.2f}m")

    if violations:
        detail = "不符合：" + "；".join(violations)
    elif checked:
        detail = "符合：" + "；".join(checked)
    else:
        detail = "无可检查的体验台短边与柱子关系"
    if skipped:
        detail += "；本条不检查：" + "；".join(skipped)
    return Finding(
        "9", MODULE, "体验台短边距柱0.7–1.2m，不过人时可紧贴",
        not violations, SEV_INFO if not violations else SEV_ERROR,
        scheme.index, detail)


def _rule_10(ctx, scheme):
    """模块规则10：体验台长边平行柱子时间距大于0.9m。

    本函数完整沿用旧版模块规则11的柱心局部坐标判定和0.05m容差。
    """
    if not _has_mid_room_columns(ctx):
        return Finding(
            "10", MODULE, "体验台长边平行柱子时间距>0.9m",
            True, SEV_INFO, scheme.index, "未识别到售卖区中间柱子")

    violations = []
    column_centers = [gu.polygon_centroid(column) for column in ctx.columns]
    for desk in _tables(scheme):
        for column_center in column_centers:
            local_long, local_short = L.point_in_furniture_local(
                desk, column_center)
            edge, gap = L.classify_point_edge(
                local_long, local_short, desk.length, desk.width)
            if edge == "long" and gap < 0.9 - 0.05:
                violations.append(f"{desk.name}@长边{gap:.2f}m")

    return Finding(
        "10", MODULE, "体验台长边平行柱子时间距>0.9m",
        not violations, SEV_INFO if not violations else SEV_ERROR,
        scheme.index,
        (f"长边距柱≤0.9m: {violations}"
         if violations else "长边距柱均>0.9m"))


def _rule_11(ctx, scheme):
    """模块规则11：体验台与柱子角对角时，四角到柱角最小距离>0.7m。

    本函数完整沿用旧版规则26：世界坐标X/Y两轴投影都不重合时
    视为角对角，并保留0.05m判定容差。
    """
    if not _has_mid_room_columns(ctx):
        return Finding(
            "11", MODULE, "体验台与柱子角对角时四角到柱角间距>0.7m",
            True, SEV_INFO, scheme.index, "未识别到售卖区中间柱子")

    violations = []
    checked = []
    for desk in _tables(scheme):
        desk_xs = [point[0] for point in desk.corners]
        desk_ys = [point[1] for point in desk.corners]
        desk_xmin, desk_xmax = min(desk_xs), max(desk_xs)
        desk_ymin, desk_ymax = min(desk_ys), max(desk_ys)
        for column_index, column in enumerate(ctx.columns, 1):
            if len(column) < 2:
                continue
            column_xs = [point[0] for point in column]
            column_ys = [point[1] for point in column]
            column_xmin, column_xmax = min(column_xs), max(column_xs)
            column_ymin, column_ymax = min(column_ys), max(column_ys)

            x_overlap = not (
                desk_xmax < column_xmin - 0.01
                or desk_xmin > column_xmax + 0.01)
            y_overlap = not (
                desk_ymax < column_ymin - 0.01
                or desk_ymin > column_ymax + 0.01)
            if x_overlap or y_overlap:
                continue

            minimum_distance = min(
                gu.dist(desk_corner, column_corner)
                for desk_corner in desk.corners
                for column_corner in column
            )
            checked.append(
                f"{desk.name}-柱{column_index}角距{minimum_distance:.2f}m")
            if minimum_distance < 0.7 - 0.05:
                violations.append(
                    f"{desk.name}-柱{column_index}@角距{minimum_distance:.2f}m")

    if violations:
        detail = f"角对角间距≤0.7m: {violations}"
    elif checked:
        detail = "角对角间距均>0.7m：" + "；".join(checked)
    else:
        detail = "未识别到体验台与柱子的角对角关系"
    return Finding(
        "11", MODULE, "体验台与柱子角对角时四角到柱角间距>0.7m",
        not violations, SEV_INFO if not violations else SEV_ERROR,
        scheme.index, detail)


def _experience_theme(item):
    """从体验台模型名称识别规则12使用的主题代号。"""
    name = (item.model or item.name or "").lower()
    if "m系列" in name:
        return "M"
    if "v旗舰" in name:
        return "V"
    if "x系列" in name:
        return "X"
    if "数字系列" in name:
        return "数字"
    if "平板pc" in name or "平板电脑" in name:
        return "PC"
    return None


def _rule_12(scheme):
    """模块规则12：体验台数量/规格对应的主题组合必须完全匹配。"""
    desks = _tables(scheme)
    count = len(desks)
    failures = []

    allowed_lengths = (2.0, 2.4, 3.0)

    def length_is(value, expected):
        return abs(value - expected) <= 0.05

    if count == 5:
        if all(length_is(item.length, 3.0) for item in desks):
            branch = "5张3m体验台"
            expected = Counter({"M": 1, "V": 1, "数字": 1,
                                "X": 1, "PC": 1})
        elif all(any(length_is(item.length, expected_length)
                     for expected_length in (2.0, 2.4))
                 for item in desks):
            branch = "5张2m/2.4m体验台"
            expected = Counter({"M": 2, "数字": 1, "X": 1, "PC": 1})
        else:
            branch = "5张体验台"
            expected = None
            lengths = "、".join(f"{item.length:.2f}m" for item in desks)
            failures.append(
                "5张体验台须全部为3m，或全部为2m/2.4m；"
                f"当前规格为{lengths}")
    elif count == 4:
        branch = "4张体验台"
        expected = Counter({"M": 1, "数字": 1, "X": 1, "PC": 1})
    elif count == 3:
        branch = "3张体验台"
        expected = Counter({"M": 1, "数字": 1, "PC": 1})
    else:
        branch = f"{count}张体验台"
        expected = None
        failures.append(f"体验台数量为{count}，不属于3张、4张或5张原则")

    if count in (3, 4):
        invalid_lengths = [
            item for item in desks
            if not any(length_is(item.length, expected_length)
                       for expected_length in allowed_lengths)
        ]
        if invalid_lengths:
            failures.append(
                "存在非2m/2.4m/3m规格：" + "、".join(
                    f"{item.name}({item.length:.2f}m)"
                    for item in invalid_lengths))

    recognized = []
    unknown = []
    for item in desks:
        theme = _experience_theme(item)
        if theme is None:
            unknown.append(item.name)
        else:
            recognized.append(theme)
    actual = Counter(recognized)
    if unknown:
        failures.append("无法识别体验台主题：" + "、".join(unknown))

    if expected is not None and not unknown and actual != expected:
        missing = expected - actual
        extra = actual - expected
        messages = []
        if missing:
            messages.append("缺少" + "、".join(
                f"{theme}×{amount}" for theme, amount in missing.items()))
        if extra:
            messages.append("多出" + "、".join(
                f"{theme}×{amount}" for theme, amount in extra.items()))
        failures.append("主题组合不符合（" + "；".join(messages) + "）")

    expected_text = (
        "、".join(f"{theme}×{amount}" for theme, amount in expected.items())
        if expected is not None else "无适用组合")
    actual_text = (
        "、".join(f"{theme}×{amount}" for theme, amount in actual.items())
        if actual else "未识别")
    detail = f"{branch}；要求{expected_text}；实际{actual_text}"
    if failures:
        detail += "；不符合：" + "；".join(failures)
    else:
        detail += "；符合"
    return Finding(
        "12", MODULE, "体验台数量、规格与主题组合符合规定",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def check(ctx, schemes):
    findings = []
    for scheme in schemes:
        findings.extend((_rule_1(scheme), _rule_2(scheme),
                         _rule_3(scheme), _rule_4(scheme),
                         _rule_5(ctx, scheme), _rule_7(ctx, scheme),
                         _rule_8(ctx, scheme), _rule_9(ctx, scheme),
                         _rule_10(ctx, scheme), _rule_11(ctx, scheme),
                         _rule_12(scheme)))
    return findings
