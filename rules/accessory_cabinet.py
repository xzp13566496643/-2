"""配件柜布局原则。

当前文件实现的模块内规则（本文件独立从1开始）：
1. 灯箱配件柜数量为1–2个；有2个时须长边平行、沿墙方向中心投影
    偏差不超过0.30m，且两个柜体尺寸一致。
   规则内容：常规灯箱配件柜按墙长适配2.4m和3.6m规格，标配1个、
   最多2个；两个平行对齐摆放时，两边尺寸应一致，优先3.6m，无法
   满足时选2.4m。
2. 影像创作柜仅允许2.4m灯箱款或1.2m包柱款；2.4m款须与灯箱
    配件柜同墙、平行且相邻，1.2m款须贴近柱子。
   规则内容：影像创作柜分为2.4m灯箱款和1.2m包柱灯箱款，优先选择
   2.4m款并与灯箱配件柜连成一体。
3. 同一面墙上的两个主题配件柜之间不得布置灯箱配件柜。本阶段不判断
    主题柜内部的灯箱侧和层板侧方向。
   规则内容：主题配件柜与灯箱配件柜相邻时不得形成两个主题柜夹一个
   灯箱配件柜；左右均有主题柜时应灯箱对灯箱、层板侧对层板侧；左右
   墙体平行时，左右配件柜尾部应平行对齐。
4. 灯箱配件柜、影像创作柜和主题配件柜应外挂于墙体；柜体
    距最近平行实体墙不超过0.15m，进入墙体深度不超过0.02m。
   规则内容：所有墙面柜子均外挂于墙体，不得采用内嵌形式。
5. 以crowdDensity最大的门为主入口，影像创作柜应布置在
    从主入口向店内正对的墙体上。
   规则内容：影像创作柜应根据主客流方向布置在相对一侧墙面，保证
   客户第一视觉能够看到。
6. 整体店内配件柜数量应为3–8组。
   规则内容：整体店内柜子标准为6组，最低3组、最多8组；销服店须有
   一组水吧台展柜。
7. 主题配件柜优先级为影音娱乐＞智能家居＞潮玩配件＞运动健康；
    低优先级存在时，前面所有高优先级主题均不得缺失。
   规则内容：主题配件柜分为影音娱乐、智能家居、潮玩配件、运动健康，
   优先级为影音娱乐＞智能家居＞潮玩配件＞运动健康。
8. 主入口相邻侧墙靠门半段上的封口板，近门封口板须紧贴墙体/垛，
   远门封口板向外侧的留白净距须不小于0.80m。
   规则内容：第一个侧边封口板与配件柜靠近出入口时须紧贴墙体或垛；
   尾部配件柜与侧边封口板外侧存在留白时，净间距须不小于0.8m。
9. 遍历每个配件柜的两个短边，沿短边外侧投影查找最近道具；最近道具
   与柜体净距须不超过0.03m，且只能是其它配件柜或侧边封口板。
   规则内容：配件柜应按“侧边封口板+配件柜+配件柜+侧边封口板”组合
   排布，配件柜组的头部和尾部均须布置侧边封口板。
10. 将配件柜匹配到最近的平行墙面并计算沿墙投影；同墙两个配件柜的
    投影区间之间没有其它同墙道具时，两柜净距须不超过0.03m。
    规则内容：配件柜应连续排布，中间无间隔。
11. 根据型号属性及明确的挂钩柜分类统计挂钩柜数量，数量不超过1个
    为符合，超过1个为不符合。
    规则内容：一个门店只能出现一个挂钩柜，其余配件柜使用层板柜；
    潮玩配件为挂钩柜，智能家居、运动健康、影音娱乐和2.4m影像创作
    为层板柜。
"""

import math

import geometry_utils as gu
import layout_data as L
from model_specs import lookup_attributes
from findings import Finding, SEV_ERROR, SEV_INFO
from findings import STATUS_NOT_RELEVANT

MODULE = "accessory_cabinet"
_WALL_CABINET_CATEGORIES = {
    "lightbox_cabinet", "imaging_cabinet", "theme_cabinet",
}
_ACCESSORY_CABINET_CATEGORIES = {
    "lightbox_cabinet", "imaging_cabinet", "theme_cabinet",
    "shelf_cabinet", "hook_cabinet", "side_cabinet",
    "lightbox_side_cabinet",
}
_END_PANEL_CATEGORY = "side_end_panel"


def _lightbox_cabinets(scheme):
    return [item for item in scheme.furniture
            if item.category == "lightbox_cabinet"]


def _long_axis_angle(item):
    """返回柜体长边方向角，方向正反等价。"""
    if len(item.corners) < 2:
        return item.angle % 180.0
    start, end = item.corners[0], item.corners[1]
    return math.degrees(
        math.atan2(end[1] - start[1], end[0] - start[0])) % 180.0


def _parallel_angle(first, second, tolerance=12.0):
    difference = abs(first - second) % 180.0
    return min(difference, 180.0 - difference) <= tolerance


def _center_projection_offset(first, second):
    """返回两个柜体中心沿第一柜长边方向的投影偏差。"""
    angle = math.radians(_long_axis_angle(first))
    axis = (math.cos(angle), math.sin(angle))
    delta = (second.cx - first.cx, second.cy - first.cy)
    return abs(delta[0] * axis[0] + delta[1] * axis[1])


def _wall_line_key(edge, angle_quantum=1.0, offset_quantum=0.05):
    """返回墙边所在直线的量化键，使同一墙面可稳定比较。"""
    start, end = edge
    dx, dy = end[0] - start[0], end[1] - start[1]
    if math.hypot(dx, dy) <= gu.EPS:
        return None
    angle = math.degrees(math.atan2(dy, dx)) % 180.0
    angle_key = round(angle / angle_quantum) * angle_quantum
    radians = math.radians(angle_key)
    normal = (-math.sin(radians), math.cos(radians))
    offset = start[0] * normal[0] + start[1] * normal[1]
    return angle_key, round(offset / offset_quantum) * offset_quantum


def _nearest_parallel_wall(ctx, item, maximum_distance=0.30):
    """返回道具最近的平行CAD墙边及其共线键。"""
    item_angle = _long_axis_angle(item)
    candidates = []
    for wall in ctx.walls:
        for edge in gu.polygon_edges(wall):
            edge_angle = math.degrees(math.atan2(
                edge[1][1] - edge[0][1], edge[1][0] - edge[0][0])) % 180.0
            if not _parallel_angle(item_angle, edge_angle):
                continue
            distance = min(
                gu.segments_distance(start, end, edge[0], edge[1])
                for start, end in gu.polygon_edges(item.corners))
            candidates.append((distance, edge))
    if not candidates:
        return None
    distance, edge = min(candidates, key=lambda value: value[0])
    if distance > maximum_distance:
        return None
    return edge, _wall_line_key(edge), distance


def _nearest_parallel_wall_surface(ctx, item):
    """返回柜体最近的平行墙边、墙体多边形和距离。"""
    item_angle = _long_axis_angle(item)
    candidates = []
    for wall in ctx.walls:
        for edge in gu.polygon_edges(wall):
            edge_angle = math.degrees(math.atan2(
                edge[1][1] - edge[0][1],
                edge[1][0] - edge[0][0])) % 180.0
            if not _parallel_angle(item_angle, edge_angle):
                continue
            distance = gu.segment_polygon_distance(
                edge[0], edge[1], item.corners)
            candidates.append((distance, edge, wall))
    return min(candidates, key=lambda value: value[0]) if candidates else None


def _rule_1(scheme):
    """模块规则1：灯箱配件柜数量、双柜平行对齐及尺寸一致性。"""
    cabinets = _lightbox_cabinets(scheme)
    count = len(cabinets)
    failures = []
    checked = [f"灯箱配件柜数量{count}个"]

    if count < 1 or count > 2:
        failures.append(f"灯箱配件柜数量为{count}个（要求1–2个）")
    elif count == 2:
        first, second = cabinets
        first_angle = _long_axis_angle(first)
        second_angle = _long_axis_angle(second)
        difference = abs(first_angle - second_angle) % 180.0
        angle_deviation = min(difference, 180.0 - difference)
        parallel = _parallel_angle(first_angle, second_angle)
        checked.append(
            f"两柜长边角度{first_angle:.2f}°/{second_angle:.2f}°，"
            f"偏差{angle_deviation:.2f}°")
        if not parallel:
            failures.append(
                f"两个灯箱配件柜长边不平行（角度偏差{angle_deviation:.2f}°＞12°）")

        projection_offset = _center_projection_offset(first, second)
        checked.append(f"沿墙方向中心投影偏差{projection_offset:.2f}m")
        if projection_offset > 0.30 + gu.EPS:
            failures.append(
                f"两个灯箱配件柜未对齐（沿墙方向中心投影偏差"
                f"{projection_offset:.2f}m＞0.30m）")

        length_difference = abs(first.length - second.length)
        width_difference = abs(first.width - second.width)
        same_size = length_difference <= 0.05 and width_difference <= 0.05
        checked.append(
            f"两柜尺寸{first.length:.2f}×{first.width:.2f}m/"
            f"{second.length:.2f}×{second.width:.2f}m")
        if not same_size:
            failures.append(
                "两个灯箱配件柜尺寸不一致："
                f"{first.length:.2f}×{first.width:.2f}m 与 "
                f"{second.length:.2f}×{second.width:.2f}m")

    detail = "；".join(checked)
    if failures:
        detail += "；不符合：" + "；".join(failures)
    else:
        detail += "；符合"
    return Finding(
        "1", MODULE,
        "灯箱配件柜1–2个；双柜须平行对齐且尺寸一致",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_2(ctx, scheme):
    """模块规则2：2.4m影像柜连灯箱配件柜，1.2m影像柜用于包柱。"""
    imaging = [item for item in scheme.furniture
               if item.category == "imaging_cabinet"]
    lightbox_cabinets = _lightbox_cabinets(scheme)
    failures = []
    checked = []

    if not imaging:
        failures.append("未布置影像创作柜")

    for item in imaging:
        if abs(item.length - 2.4) <= 0.05:
            item_wall = _nearest_parallel_wall(ctx, item)
            matches = []
            for cabinet in lightbox_cabinets:
                cabinet_wall = _nearest_parallel_wall(ctx, cabinet)
                parallel = _parallel_angle(
                    _long_axis_angle(item), _long_axis_angle(cabinet))
                same_wall = (item_wall is not None and cabinet_wall is not None
                             and item_wall[1] == cabinet_wall[1])
                distance = gu.polygons_distance(item.corners, cabinet.corners)
                if parallel and same_wall and distance <= 0.10 + gu.EPS:
                    matches.append((distance, cabinet))
            if matches:
                distance, cabinet = min(matches, key=lambda value: value[0])
                checked.append(
                    f"{item.name}为2.4m款，与{cabinet.name}同墙平行相邻，"
                    f"间距{distance:.2f}m")
            else:
                failures.append(
                    f"{item.name}为2.4m款，但未与灯箱配件柜同墙、平行且"
                    "在0.10m内相邻")
        elif abs(item.length - 1.2) <= 0.05:
            nearest_column = min(
                (gu.polygons_distance(item.corners, column)
                 for column in ctx.columns if len(column) >= 2),
                default=float("inf"),
            )
            if nearest_column <= 0.10 + gu.EPS:
                checked.append(
                    f"{item.name}为1.2m包柱款，距柱{nearest_column:.2f}m")
            elif math.isfinite(nearest_column):
                failures.append(
                    f"{item.name}为1.2m包柱款，距最近柱{nearest_column:.2f}m"
                    "＞0.10m")
            else:
                failures.append(f"{item.name}为1.2m包柱款，但方案中未识别到柱子")
        else:
            failures.append(
                f"{item.name}长度{item.length:.2f}m，不是允许的2.4m或1.2m规格")

    detail = "；".join(checked)
    if failures:
        detail = ((detail + "；") if detail else "") + "不符合：" + "；".join(failures)
    elif checked:
        detail += "；符合"
    return Finding(
        "2", MODULE,
        "影像创作柜为2.4m连柜款或1.2m包柱款",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_3(ctx, scheme):
    """模块规则3：同墙两个主题柜之间不得出现灯箱配件柜。"""
    themes = [item for item in scheme.furniture
              if item.category == "theme_cabinet"]
    lightbox_cabinets = _lightbox_cabinets(scheme)
    grouped = {}
    unassigned = []

    for item in themes + lightbox_cabinets:
        wall = _nearest_parallel_wall(ctx, item)
        if wall is None or wall[1] is None:
            unassigned.append(item.name)
            continue
        _edge, wall_key, _distance = wall
        # 使用墙面键中0–180°的统一方向，避免同一墙边正反存储导致
        # 不同道具的投影坐标符号相反。
        radians = math.radians(wall_key[0])
        axis = (math.cos(radians), math.sin(radians))
        position = item.cx * axis[0] + item.cy * axis[1]
        grouped.setdefault(wall_key, []).append((position, item))

    violations = []
    checked_walls = 0
    for wall_key, entries in grouped.items():
        wall_themes = sorted(
            ((position, item) for position, item in entries
             if item.category == "theme_cabinet"),
            key=lambda value: value[0],
        )
        wall_lightboxes = [
            (position, item) for position, item in entries
            if item.category == "lightbox_cabinet"
        ]
        if len(wall_themes) < 2:
            continue
        checked_walls += 1
        for index in range(len(wall_themes) - 1):
            left_position, left = wall_themes[index]
            right_position, right = wall_themes[index + 1]
            between = [item for position, item in wall_lightboxes
                       if left_position < position < right_position]
            if between:
                violations.append(
                    f"同墙主题柜{left.name}与{right.name}之间存在灯箱配件柜"
                    + "、".join(item.name for item in between))

    if violations:
        detail = "不符合：" + "；".join(violations)
    elif len(themes) < 2:
        detail = f"主题配件柜{len(themes)}个，不存在两个主题柜夹灯箱配件柜的情况"
    elif checked_walls == 0:
        detail = "未识别到同一面墙上同时存在两个主题配件柜"
    else:
        detail = f"检查{checked_walls}面含多个主题柜的墙，未发现灯箱配件柜位于两者之间"
    if unassigned:
        detail += "；未匹配墙面：" + "、".join(unassigned)

    return Finding(
        "3", MODULE, "同墙两个主题配件柜之间不得布置灯箱配件柜",
        not violations, SEV_INFO if not violations else SEV_ERROR,
        scheme.index, detail)


def _rule_4(ctx, scheme):
    """模块规则4：所有墙面柜外挂于墙体，不得内嵌。"""
    cabinets = [item for item in scheme.furniture
                if item.category in _WALL_CABINET_CATEGORIES]
    failures = []
    checked = []
    for cabinet in cabinets:
        nearest = _nearest_parallel_wall_surface(ctx, cabinet)
        if nearest is None:
            failures.append(f"{cabinet.name}未找到平行实体墙")
            continue
        distance, wall_edge, wall_polygon = nearest
        if distance > 0.15 + gu.EPS:
            failures.append(
                f"{cabinet.name}距最近平行墙{distance:.2f}m＞0.15m，"
                "未确认为靠墙外挂")
            continue

        wall_dx = wall_edge[1][0] - wall_edge[0][0]
        wall_dy = wall_edge[1][1] - wall_edge[0][1]
        wall_normal = (-wall_dy, wall_dx)
        penetration = gu.polygon_intersection_projection_depth(
            cabinet.corners, wall_polygon, wall_normal)
        checked.append(
            f"{cabinet.name}距墙{distance:.2f}m、进墙{penetration:.3f}m")
        if penetration > 0.02 + gu.EPS:
            failures.append(
                f"{cabinet.name}进入墙体{penetration:.3f}m＞0.02m，"
                "判定为内嵌")

    detail = "；".join(checked)
    if not cabinets:
        detail = "未识别到需检查的墙面柜"
    elif failures:
        detail = ((detail + "；") if detail else "") + \
                 "不符合：" + "；".join(failures)
    else:
        detail += "；全部墙面柜为外挂形式"
    return Finding(
        "4", MODULE, "所有墙面柜子外挂于墙体，非内嵌形式",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_5(ctx, scheme):
    """模块规则5：影像创作柜布置在主客流入口正对面墙体。"""
    imaging_cabinets = [item for item in scheme.furniture
                        if item.category == "imaging_cabinet"]
    if not imaging_cabinets:
        return Finding(
            "5", MODULE, "影像创作柜布置在主入口对面墙体",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未识别到影像创作柜，本规则不涉及（品类缺失由规则12检查）")

    entrance = L.main_entrance(ctx)
    if entrance is None:
        return Finding(
            "5", MODULE, "影像创作柜布置在主入口对面墙体",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "JSON未提供有效crowdDensity，无法确定主入口")

    opposite = gu.opposite_wall_from_door(
        entrance, ctx.walls, ctx.boundary)
    if opposite is None:
        return Finding(
            "5", MODULE, "影像创作柜布置在主入口对面墙体",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未识别到主入口向店内正对的平行实体墙")

    wall_edge = opposite["segment"]
    wall_angle = math.degrees(math.atan2(
        wall_edge[1][1] - wall_edge[0][1],
        wall_edge[1][0] - wall_edge[0][0])) % 180.0
    failures = []
    checked = []
    for cabinet in imaging_cabinets:
        cabinet_angle = _long_axis_angle(cabinet)
        parallel = _parallel_angle(cabinet_angle, wall_angle)
        distance = gu.polygon_line_distance(cabinet.corners, *wall_edge)
        span_start, span_end = gu.polygon_segment_span(
            cabinet.corners, wall_edge)
        on_wall_span = span_end >= -gu.EPS and span_start <= 1.0 + gu.EPS
        checked.append(
            f"{cabinet.name}距主入口对面墙{distance:.2f}m、"
            f"与墙{'平行' if parallel else '不平行'}、"
            f"沿墙投影{'命中完整墙段' if on_wall_span else '超出完整墙段'}")
        if (not parallel or distance > 0.15 + gu.EPS
                or not on_wall_span):
            reasons = []
            if not parallel:
                reasons.append("柜体长边与对面墙不平行")
            if distance > 0.15 + gu.EPS:
                reasons.append(f"距对面墙{distance:.2f}m＞0.15m")
            if not on_wall_span:
                reasons.append("柜体沿墙投影未落入完整墙段")
            failures.append(f"{cabinet.name}（{'、'.join(reasons)}）")

    detail = (f"主入口crowdDensity={entrance.raw.get('crowdDensity')}，"
              f"对面完整墙段长{opposite['length']:.2f}m、"
              f"距入口{opposite['distance']:.2f}m；"
              + "；".join(checked))
    if failures:
        detail += "；不符合：" + "；".join(failures)
    else:
        detail += "；影像创作柜位于主入口对面墙体"
    return Finding(
        "5", MODULE, "影像创作柜布置在主入口对面墙体",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_6(scheme):
    """模块规则6：整体店内配件柜数量为3–8组。"""
    cabinets = [item for item in scheme.furniture
                if item.category in _WALL_CABINET_CATEGORIES]
    count = len(cabinets)
    passed = 3 <= count <= 8
    by_category = {}
    for cabinet in cabinets:
        by_category[cabinet.category] = \
            by_category.get(cabinet.category, 0) + 1
    category_labels = {
        "lightbox_cabinet": "灯箱配件柜",
        "imaging_cabinet": "影像创作柜",
        "theme_cabinet": "主题配件柜",
    }
    breakdown = "、".join(
        f"{category_labels.get(category, category)}{amount}组"
        for category, amount in by_category.items())
    detail = f"店内共{count}组配件柜"
    if breakdown:
        detail += f"（{breakdown}）"
    detail += "，要求3–8组"
    if not passed:
        detail += "；不符合"
    else:
        detail += "；符合"
    return Finding(
        "6", MODULE, "整体店内配件柜数量为3–8组",
        passed, SEV_INFO if passed else SEV_ERROR,
        scheme.index, detail)


def _rule_7(scheme):
    """模块规则7：主题配件柜按四级优先顺序不得跳级布置。"""
    priorities = ["影音娱乐", "智能家居", "潮玩配件", "运动健康"]
    cabinets = [item for item in scheme.furniture
                if item.category == "theme_cabinet"]
    counts = {theme: 0 for theme in priorities}
    unknown = []
    for cabinet in cabinets:
        matched = next(
            (theme for theme in priorities
             if theme in cabinet.name or theme in cabinet.model),
            None,
        )
        if matched is None:
            unknown.append(cabinet.name)
        else:
            counts[matched] += 1

    failures = []
    for index, theme in enumerate(priorities):
        if counts[theme] == 0:
            continue
        missing_higher = [higher for higher in priorities[:index]
                          if counts[higher] == 0]
        if missing_higher:
            failures.append(
                f"已布置{theme}，但更高优先级缺少"
                + "、".join(missing_higher))

    presence = "、".join(
        f"{theme}{counts[theme]}组" for theme in priorities)
    detail = f"主题柜：{presence}"
    if unknown:
        detail += "；未归入四类：" + "、".join(unknown)
    if failures:
        detail += "；不符合：" + "；".join(failures)
    else:
        detail += "；优先级符合"
    return Finding(
        "7", MODULE,
        "主题配件柜优先级：影音娱乐＞智能家居＞潮玩配件＞运动健康",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_8(ctx, scheme):
    """模块规则8：入口侧真实封口板近门端贴墙/垛，远门端留白≥0.8m。"""
    entrance = L.main_entrance(ctx)
    if entrance is None:
        return Finding(
            "8", MODULE, "入口侧封口板近门贴墙/垛、远门外侧留白≥0.8m",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "JSON未提供有效crowdDensity，无法确定主入口")

    frontage_polygons = [
        opening.polygon for opening in ctx.openings
        if opening.kind == "glassWall"
    ]
    adjacent = gu.entrance_adjacent_side_wall_runs(
        entrance, ctx.walls, frontage_polygons, ctx.boundary)
    end_panels = [item for item in scheme.furniture
                  if item.category == _END_PANEL_CATEGORY]
    all_furniture = list(scheme.furniture)

    def angle(segment):
        return math.degrees(math.atan2(
            segment[1][1] - segment[0][1],
            segment[1][0] - segment[0][0])) % 180.0

    def angle_difference(first, second):
        difference = abs((first - second) % 180.0)
        return min(difference, 180.0 - difference)

    def segment_midpoint(segment):
        return ((segment[0][0] + segment[1][0]) / 2.0,
                (segment[0][1] + segment[1][1]) / 2.0)

    def overlaps_segment(item, segment):
        lower, upper = gu.polygon_segment_span(item.corners, segment)
        return upper >= -gu.EPS and lower <= 1.0 + gu.EPS

    def door_distance(item):
        return gu.polygons_distance(item.corners, entrance.polygon)

    def perpendicular_barrier_distance(panel, host_segment):
        """近门封口板到与主墙垂直的墙体/垛边的最短距。"""
        host_angle = angle(host_segment)
        candidates = []
        for wall in ctx.walls:
            for edge in gu.polygon_edges(wall):
                difference = angle_difference(angle(edge), host_angle)
                if abs(difference - 90.0) > 15.0:
                    continue
                candidates.append(gu.segment_polygon_distance(
                    edge[0], edge[1], panel.corners))
        return min(candidates, default=float("inf"))

    def outer_edge_and_direction(panel, near_panel, host_segment):
        """返回远门封口板的外侧边，以及严格垂直于该边的外向向量。"""
        host_angle = angle(host_segment)
        cross_edges = [
            edge for edge in gu.polygon_edges(panel.corners)
            if abs(angle_difference(angle(edge), host_angle) - 90.0)
            <= 15.0
        ]
        if not cross_edges:
            return None, None

        # 两条横跨柜体深度的边中，离入口更远的一条是封口板外侧边。
        outer_edge = max(
            cross_edges,
            key=lambda edge: gu.segment_polygon_distance(
                edge[0], edge[1], entrance.polygon),
        )
        start, end = outer_edge
        edge_dx, edge_dy = end[0] - start[0], end[1] - start[1]
        normals = [(-edge_dy, edge_dx), (edge_dy, -edge_dx)]
        outer_center = segment_midpoint(outer_edge)
        away = (outer_center[0] - near_panel.cx,
                outer_center[1] - near_panel.cy)
        direction = max(
            normals,
            key=lambda normal: normal[0] * away[0] + normal[1] * away[1],
        )
        return outer_edge, direction

    def projected_blank_distance(panel, direction, excluded_cabinets,
                                 full_segment):
        """封口板沿外向投影到最近道具/垛，无命中时量到墙段端点。"""
        candidates = []
        for other in all_furniture:
            if any(other is cabinet for cabinet in excluded_cabinets):
                continue
            distance = gu.edge_directional_polygon_distance(
                panel, direction, other.corners)
            if distance is not None:
                candidates.append((distance, other.name))

        host_angle = angle(full_segment)
        for wall_index, wall in enumerate(ctx.walls):
            perpendicular_edges = [
                edge for edge in gu.polygon_edges(wall)
                if abs(angle_difference(angle(edge), host_angle) - 90.0)
                <= 15.0
            ]
            for edge in perpendicular_edges:
                distance = gu.edge_directional_polygon_distance(
                    panel, direction, [edge[0], edge[1]])
                if distance is not None:
                    candidates.append((distance, f"墙/垛{wall_index + 1}"))

        panel_center = segment_midpoint(panel)
        direction_length = math.hypot(*direction)
        unit = (direction[0] / direction_length,
                direction[1] / direction_length)
        endpoint_distances = []
        for endpoint in full_segment:
            forward = ((endpoint[0] - panel_center[0]) * unit[0]
                       + (endpoint[1] - panel_center[1]) * unit[1])
            if forward >= -gu.EPS:
                endpoint_distances.append((max(0.0, forward), "完整墙段端点"))
        candidates.extend(endpoint_distances)
        return min(candidates, key=lambda value: value[0]) \
            if candidates else (float("inf"), "无投影目标")

    matched = []
    failures = []
    details = []
    for side_name, side_label in (("left", "左侧"), ("right", "右侧")):
        side = adjacent[side_name]
        if side is None:
            continue
        full_segment = side["full_segment"]
        near_half = side["near_half"]
        wall_panels = [
            panel for panel in end_panels
            if gu.polygon_line_distance(panel.corners, *full_segment)
            <= 0.15 + gu.EPS
            and overlaps_segment(panel, full_segment)
        ]
        near_half_panels = [panel for panel in wall_panels
                            if overlaps_segment(panel, near_half)]
        if not near_half_panels:
            continue
        # 靠门半段出现封口板即触发规则；与它配套的远门封口板可能已经
        # 跨过半段分界，因此在同一完整侧墙上寻找近、远两块封口板。
        matched.extend(wall_panels)
        group_label = f"{side_label}入口侧墙"
        if len(wall_panels) != 2:
            failures.append(
                f"{group_label}识别到{len(wall_panels)}块封口板，"
                "应为近门、远门各1块")
            continue

        near_panel, far_panel = sorted(wall_panels, key=door_distance)
        near_distance = perpendicular_barrier_distance(
            near_panel, full_segment)
        if near_distance > 0.10 + gu.EPS:
            failures.append(
                f"{group_label}近门封口板距墙/垛"
                f"{near_distance:.2f}m＞0.10m")

        outer_edge, outward = outer_edge_and_direction(
            far_panel, near_panel, full_segment)
        if outer_edge is None:
            failures.append(f"{group_label}远门封口板轮廓方向无法识别")
            continue
        blank_distance, target = projected_blank_distance(
            outer_edge, outward, wall_panels, full_segment)
        if blank_distance < 0.80 - gu.EPS:
            failures.append(
                f"{group_label}远门封口板外侧留白"
                f"{blank_distance:.2f}m＜0.80m（至{target}）")
        details.append(
            f"{group_label}：近门板距墙/垛"
            f"{near_distance:.2f}m，远门板外侧留白"
            f"{blank_distance:.2f}m（至{target}）")

    if not matched:
        side_status = []
        for key, label in (("left", "左侧"), ("right", "右侧")):
            value = adjacent[key]
            side_status.append(
                f"{label}{'未识别到相邻侧墙' if value is None else '靠门半段无封口板'}")
        return Finding(
            "8", MODULE, "入口侧封口板近门贴墙/垛、远门外侧留白≥0.8m",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "；".join(side_status) + "，规则不涉及")

    detail = "；".join(details)
    if failures:
        detail += ("；" if detail else "") + "不符合：" + "；".join(failures)
    else:
        detail += "；近门封口板贴墙/垛且另一侧留白符合"
    return Finding(
        "8", MODULE, "入口侧封口板近门贴墙/垛、远门外侧留白≥0.8m",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_9(scheme):
    """模块规则9：每个配件柜两侧只能紧贴配件柜或侧边封口板。"""
    cabinets = [
        item for item in scheme.furniture
        if item.category in _ACCESSORY_CABINET_CATEGORIES
    ]
    allowed_categories = _ACCESSORY_CABINET_CATEGORIES | {
        _END_PANEL_CATEGORY,
    }
    failures = []
    checked = []

    for cabinet in cabinets:
        edges = gu.polygon_edges(cabinet.corners)
        if len(edges) < 4:
            failures.append(f"{cabinet.name}缺少有效柜体轮廓")
            continue
        edge_lengths = [gu.dist(*edge) for edge in edges]
        shortest = min(edge_lengths)
        side_edges = [
            (edge_index, edge)
            for edge_index, (edge, edge_length) in enumerate(
                zip(edges, edge_lengths))
            if abs(edge_length - shortest) <= 0.05
        ][:2]
        if len(side_edges) != 2:
            failures.append(f"{cabinet.name}无法识别两个侧边")
            continue

        for side_number, (_edge_index, edge) in enumerate(side_edges, 1):
            midpoint = (
                (edge[0][0] + edge[1][0]) / 2.0,
                (edge[0][1] + edge[1][1]) / 2.0,
            )
            outward = (midpoint[0] - cabinet.cx,
                       midpoint[1] - cabinet.cy)
            distance, neighbor = gu.nearest_object_in_edge_direction(
                edge, outward, scheme.furniture, exclude=cabinet)
            side_label = f"{cabinet.name}侧边{side_number}"
            if distance is None or neighbor is None:
                failures.append(f"{side_label}外侧未找到相邻道具")
                continue

            checked.append(
                f"{side_label}至{neighbor.name}{distance:.2f}m")
            if distance > 0.03 + gu.EPS:
                failures.append(
                    f"{side_label}未紧贴{neighbor.name}：净距"
                    f"{distance:.2f}m＞0.03m")
            elif neighbor.category not in allowed_categories:
                failures.append(
                    f"{side_label}紧贴的是{neighbor.name}"
                    f"（{neighbor.category}），不是配件柜或侧边封口板")

    if not cabinets:
        return Finding(
            "9", MODULE, "配件柜两侧须紧贴配件柜或侧边封口板",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未识别到配件柜，规则不涉及")

    detail = f"检查{len(cabinets)}个配件柜的{len(cabinets) * 2}个侧边"
    if checked:
        detail += "；" + "；".join(checked)
    if failures:
        detail += "；不符合：" + "；".join(failures)
    else:
        detail += "；所有侧边均紧贴配件柜或侧边封口板"
    return Finding(
        "9", MODULE, "配件柜两侧须紧贴配件柜或侧边封口板",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_10(ctx, scheme):
    """模块规则10：同墙且中间无其它道具的配件柜须连续紧贴。"""
    cabinets = [
        item for item in scheme.furniture
        if item.category in _ACCESSORY_CABINET_CATEGORIES
    ]
    grouped_cabinets = {}
    grouped_objects = {}
    unmatched = []

    def projection_interval(item, axis):
        values = [point[0] * axis[0] + point[1] * axis[1]
                  for point in item.corners]
        return min(values), max(values)

    # 只把能够匹配到同一平行墙线的道具作为“同墙道具”。桌类等离墙较远的
    # 家具不会因为平面投影落在两柜之间而错误阻断连续性判断。
    for item in scheme.furniture:
        if not item.corners:
            continue
        wall = _nearest_parallel_wall(ctx, item)
        if wall is None or wall[1] is None:
            if item in cabinets:
                unmatched.append(item.name)
            continue
        _edge, wall_key, _distance = wall
        radians = math.radians(wall_key[0])
        axis = (math.cos(radians), math.sin(radians))
        entry = (projection_interval(item, axis), item)
        grouped_objects.setdefault(wall_key, []).append(entry)
        if item.category in _ACCESSORY_CABINET_CATEGORIES:
            grouped_cabinets.setdefault(wall_key, []).append(entry)

    checked = []
    failures = []
    for wall_key, entries in grouped_cabinets.items():
        entries.sort(key=lambda value: value[0][0])
        wall_objects = grouped_objects.get(wall_key, [])
        for index, (left_interval, left) in enumerate(entries):
            for right_interval, right in entries[index + 1:]:
                gap_start = left_interval[1]
                gap_end = right_interval[0]
                if gap_end <= gap_start + gu.EPS:
                    continue

                blockers = []
                for other_interval, other in wall_objects:
                    if other is left or other is right:
                        continue
                    overlap = min(gap_end, other_interval[1]) - max(
                        gap_start, other_interval[0])
                    if overlap > gu.EPS:
                        blockers.append(other)
                if blockers:
                    continue

                distance = gu.polygons_distance(
                    left.corners, right.corners)
                checked.append(
                    f"{left.name}—{right.name}净距{distance:.2f}m")
                if distance > 0.03 + gu.EPS:
                    failures.append(
                        f"同墙{left.name}与{right.name}之间无其它道具，"
                        f"但净距{distance:.2f}m＞0.03m")

    if not cabinets:
        return Finding(
            "10", MODULE, "配件柜连续排布且中间无间隔",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未识别到配件柜，规则不涉及")

    detail = f"识别到{len(cabinets)}个配件柜"
    if checked:
        detail += "；检查无其它同墙道具间隔的柜体对：" + "；".join(checked)
    else:
        detail += "；未发现需要直接连续排布的同墙柜体对"
    if unmatched:
        detail += "；未匹配墙面：" + "、".join(unmatched)
    if failures:
        detail += "；不符合：" + "；".join(failures)
    else:
        detail += "；符合"
    return Finding(
        "10", MODULE, "配件柜连续排布且中间无间隔",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_11(scheme):
    """模块规则11：一个门店的挂钩柜数量不得超过1个。"""
    hook_cabinets = []
    for item in scheme.furniture:
        attributes = lookup_attributes(item.model or item.name)
        if (item.category == "hook_cabinet"
                or attributes.get("cabinet_style") == "hook"):
            hook_cabinets.append(item)

    count = len(hook_cabinets)
    passed = count <= 1
    detail = f"识别到挂钩柜{count}个"
    if hook_cabinets:
        detail += "：" + "、".join(item.name for item in hook_cabinets)
    if passed:
        detail += "；数量不超过1个，符合"
    else:
        detail += "；不符合：一个门店最多只能出现1个挂钩柜"
    return Finding(
        "11", MODULE, "一个门店的挂钩柜数量不超过1个",
        passed, SEV_INFO if passed else SEV_ERROR,
        scheme.index, detail)


def check(ctx, schemes):
    findings = []
    for scheme in schemes:
        findings.extend((_rule_1(scheme), _rule_2(ctx, scheme),
                         _rule_3(ctx, scheme), _rule_4(ctx, scheme),
                         _rule_5(ctx, scheme), _rule_6(scheme),
                         _rule_7(scheme), _rule_8(ctx, scheme),
                         _rule_9(scheme), _rule_10(ctx, scheme),
                         _rule_11(scheme)))
    return findings
