"""其他道具布局原则。

当前文件实现的模块内规则（本文件独立从1开始）：
1. 以主客流入口中点到门店中心的方向作为室外看向室内的视线，用入口
   中线将室内划分为左右两侧，不判断前后距离。授权牌优先在右侧紧贴
   墙面或柱子；右侧无合格项但左侧有紧贴墙面的授权牌时输出警告。
   规则内容：授权牌优先布置在入口处右边墙面或柱子面上，其次布置在
   左边墙体。（必选）
2. 合并实体墙段并吸收与主入口门口边共线、相连的玻璃墙/实体墙段，
   得到完整入口面墙段；绿植手机支架槽须长边平行、投影落在该墙段内，
   且轮廓距墙线不超过0.15m，不满足时输出警告。
   规则内容：绿植手机支架槽只能布局在入口面侧，填补空白区域。（可选）
"""

import math

import geometry_utils as gu
import layout_data as L
from findings import (
    Finding, SEV_ERROR, SEV_INFO, SEV_WARN,
    STATUS_NOT_RELEVANT, STATUS_PASS, STATUS_WARN,
)

MODULE = "other_props"


def _minimum_polygon_distance(polygon, targets):
    return min(
        (gu.polygons_distance(polygon, target)
         for target in targets if len(target) >= 2),
        default=float("inf"),
    )


def _rule_1(ctx, scheme):
    """模块规则1：授权牌优先位于主入口视角右侧墙面或柱面。"""
    signs = [item for item in scheme.furniture
             if item.category == "authorization_sign"]
    if not signs:
        return Finding(
            "1", MODULE, "授权牌优先布置在主入口右侧墙面或柱面",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未布置授权牌，规则不涉及")

    entrance = L.main_entrance(ctx)
    if entrance is None:
        return Finding(
            "1", MODULE, "授权牌优先布置在主入口右侧墙面或柱面",
            STATUS_WARN, SEV_WARN, scheme.index,
            "已布置授权牌，但JSON未提供有效crowdDensity，无法确定主客流入口")

    door_center = gu.polygon_centroid(entrance.polygon)
    store_center = gu.polygon_centroid(ctx.boundary)
    inward = (store_center[0] - door_center[0],
              store_center[1] - door_center[1])
    inward_length = math.hypot(*inward)
    if inward_length <= gu.EPS:
        return Finding(
            "1", MODULE, "授权牌优先布置在主入口右侧墙面或柱面",
            STATUS_WARN, SEV_WARN, scheme.index,
            "主入口中心与门店中心重合，无法确定室外看向室内的左右方向")

    inward_unit = (inward[0] / inward_length, inward[1] / inward_length)
    # 面向室内时的右手方向为入店方向顺时针旋转90°。
    right_axis = (inward_unit[1], -inward_unit[0])
    right_valid = []
    left_wall_valid = []
    details = []
    for index, sign in enumerate(signs, 1):
        lateral = gu.axis_projection(
            (sign.cx, sign.cy), right_axis, door_center)
        side = "右侧" if lateral > gu.EPS else (
            "左侧" if lateral < -gu.EPS else "入口中线")
        wall_distance = _minimum_polygon_distance(sign.corners, ctx.walls)
        column_distance = _minimum_polygon_distance(sign.corners, ctx.columns)
        details.append(
            f"授权牌{index}位于{side}，距墙{wall_distance:.2f}m，"
            + (f"距柱{column_distance:.2f}m"
               if math.isfinite(column_distance) else "无柱子"))
        if (side == "右侧"
                and min(wall_distance, column_distance) <= 0.10 + gu.EPS):
            right_valid.append(sign)
        elif side == "左侧" and wall_distance <= 0.10 + gu.EPS:
            left_wall_valid.append(sign)

    detail = f"识别到{len(signs)}个授权牌；" + "；".join(details)
    if right_valid:
        detail += "；授权牌位于主入口视角右侧并紧贴墙面或柱面，符合"
        status, severity = STATUS_PASS, SEV_INFO
    elif left_wall_valid:
        detail += "；警告：授权牌仅布置在主入口视角左侧墙面，未采用优先右侧"
        status, severity = STATUS_WARN, SEV_WARN
    else:
        detail += "；不符合：没有授权牌紧贴主入口视角右侧墙面/柱面或左侧墙面"
        status, severity = False, SEV_ERROR
    return Finding(
        "1", MODULE, "授权牌优先布置在主入口右侧墙面或柱面",
        status, severity, scheme.index, detail)


def _angle(segment):
    return math.degrees(math.atan2(
        segment[1][1] - segment[0][1],
        segment[1][0] - segment[0][0])) % 180.0


def _angle_difference(first, second):
    difference = abs(first - second) % 180.0
    return min(difference, 180.0 - difference)


def _main_entrance_frontage(ctx, entrance):
    """合并主入口所在立面的玻璃墙及实体墙段。"""
    runs = gu.build_wall_runs(
        ctx.walls, minimum_length=0.05, merge_gap=0.02)
    wall_segments = [(start, end) for start, end, _length in runs]
    frontage_candidates = list(wall_segments)
    for opening in ctx.openings:
        if opening.kind != "glassWall":
            continue
        frontage_candidates.extend(
            edge for edge in gu.polygon_edges(opening.polygon)
            if gu.dist(*edge) > 0.05)

    sides = gu.entrance_side_wall_segments(
        entrance, wall_segments, frontage_candidates, ctx.boundary)
    frontage = sides["frontage"]
    if not frontage:
        return None

    door_edge = (entrance.polygon[0], entrance.polygon[1])
    door_length = gu.dist(*door_edge)
    if door_length <= gu.EPS:
        return None
    axis = ((door_edge[1][0] - door_edge[0][0]) / door_length,
            (door_edge[1][1] - door_edge[0][1]) / door_length)
    origin = door_edge[0]
    values = [gu.axis_projection(point, axis, origin)
              for segment in frontage for point in segment]
    lower, upper = min(values), max(values)
    return (
        (origin[0] + lower * axis[0], origin[1] + lower * axis[1]),
        (origin[0] + upper * axis[0], origin[1] + upper * axis[1]),
    )


def _rule_2(ctx, scheme):
    """模块规则2：绿植手机支架槽只能布置在主入口完整立面。"""
    stands = [item for item in scheme.furniture
              if item.category == "plant_phone_stand"]
    if not stands:
        return Finding(
            "2", MODULE, "绿植手机支架槽仅布置在入口面侧",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未布置绿植手机支架槽，可选规则不涉及")

    entrance = L.main_entrance(ctx)
    if entrance is None:
        return Finding(
            "2", MODULE, "绿植手机支架槽仅布置在入口面侧",
            STATUS_WARN, SEV_WARN, scheme.index,
            "已布置绿植手机支架槽，但JSON未提供有效crowdDensity，"
            "无法确定主入口")

    frontage = _main_entrance_frontage(ctx, entrance)
    if frontage is None or gu.dist(*frontage) <= gu.EPS:
        return Finding(
            "2", MODULE, "绿植手机支架槽仅布置在入口面侧",
            STATUS_WARN, SEV_WARN, scheme.index,
            "无法合并得到主入口面完整墙段")

    frontage_angle = _angle(frontage)

    def polygon_to_line_distance(polygon, segment):
        start, end = segment
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= gu.EPS:
            return float("inf")
        signed = [
            (dx * (point[1] - start[1])
             - dy * (point[0] - start[0])) / length
            for point in polygon
        ]
        if min(signed) <= gu.EPS and max(signed) >= -gu.EPS:
            return 0.0
        return min(abs(value) for value in signed)

    warnings = []
    details = []
    for index, stand in enumerate(stands, 1):
        if len(stand.corners) < 3:
            warnings.append(f"绿植手机支架槽{index}缺少有效轮廓")
            continue
        long_edge = max(gu.polygon_edges(stand.corners),
                        key=lambda edge: gu.dist(*edge))
        parallel = _angle_difference(
            _angle(long_edge), frontage_angle) <= 12.0
        lower, upper = gu.polygon_segment_span(stand.corners, frontage)
        overlaps = upper >= -gu.EPS and lower <= 1.0 + gu.EPS
        distance = polygon_to_line_distance(stand.corners, frontage)
        on_frontage = parallel and overlaps and distance <= 0.15 + gu.EPS
        details.append(
            f"绿植手机支架槽{index}距入口面{distance:.2f}m，"
            f"长边{'平行' if parallel else '不平行'}，"
            f"投影{'落在墙段内' if overlaps else '超出墙段'}")
        if not on_frontage:
            warnings.append(f"绿植手机支架槽{index}未布置在主入口面墙段")

    detail = (f"主入口面墙段长度{gu.dist(*frontage):.2f}m；"
              + "；".join(details))
    if warnings:
        detail += "；警告：" + "；".join(warnings)
        status, severity = STATUS_WARN, SEV_WARN
    else:
        detail += "；全部位于入口面侧"
        status, severity = STATUS_PASS, SEV_INFO
    return Finding(
        "2", MODULE, "绿植手机支架槽仅布置在入口面侧",
        status, severity, scheme.index, detail)


def check(ctx, schemes):
    findings = []
    for scheme in schemes:
        findings.extend((_rule_1(ctx, scheme), _rule_2(ctx, scheme)))
    return findings
