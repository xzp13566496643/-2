"""一般要求。

当前文件实现的模块内规则（本文件独立从1开始）：
1. 根据门头方向计算门店面宽W和进深D，判定横店/竖店；再按对应的
   道具布置优先级检查道具类型是否存在。低优先级类型存在时，其前面的
   高优先级类型不得缺失；第一处侧边封口板要求至少1块，第二处要求
   至少2块，分别代表配件柜组头部和尾部。
   规则内容：竖长条门店的布置优先级为体验台＞侧边封口板＞灯箱配件柜
   ＞影像创作柜＞主题配件柜＞侧边封口板＞开机服务台＞背景墙灯箱；
   横长条门店最后一级为背景墙灯箱柜、主题配件柜；按门店净平面的
   面宽W/进深D判定，W/D≥1为横长门店，W/D＜1为竖长门店。
2. 检查展示道具是否过度集中、空白墙比例是否不超过25%，以及最大连续
   空白矩形是否不超过售卖区面积的20%。不使用旧版AI均匀性判断。
   规则内容：墙面应尽可能布置灯箱配件柜、主题配件柜和灯箱，避免空白
   墙面积过大；售卖区空白墙总长不超过所有墙面的25%，中岛家具摆放
   应均匀，场地不能有大面积空场。
4. 消防栓暗门前方保持至少1.5m安全净空，暗门开启角度不小于130°；
   沿用旧版5°几何测量容差。
   规则内容：消防栓暗门前方应保证至少1.5m的安全距离，暗门开口角度
   不小于130°。
5. 疏散门前1.5m范围内禁止摆放道具。当前JSON暂无疏散门（安全门）
   数据，本阶段输出“规则不涉及”。
   规则内容：疏散门前1.5m范围内禁止摆放任何道具。
6. 防火卷闸正下方及两侧各0.5m范围禁止摆放道具。当前JSON暂无
   防火卷闸数据，本阶段跳过几何判断。
   规则内容：店内防火卷闸正下方及两侧各0.5m范围内禁止摆放任何道具。
7. 靠墙及墙面类道具不得影响门正常开启；道具与门相交或距门口
    小于0.10m均判为不符合。
   规则内容：靠墙以及墙面类的所有道具均不可影响门的正常开启。
8. 靠墙及墙面类道具不得布置在玻璃墙前；与玻璃墙相交或净距
    小于0.05m均判为不符合。
   规则内容：靠墙以及墙面类的所有道具不可布置在玻璃墙前。
9. 方案必须包含体验台、灯箱配件柜、影像创作柜、开机服务台和
   背景墙灯箱；
    任一品类缺失即判为不符合。
   规则内容：生成方案不可缺失体验台、灯箱配件柜、影像创作柜和
   开机服务台。
10. 检查每个入口左右两侧的入口墙垛；墙垛长度应为0.30–0.90m、
     厚度应为0.43m（保留±0.05m施工容差）。无墙垛时规则不涉及，
     尺寸不符时输出警告。
    规则内容：入口侧如生成墙垛，墙垛须长300–900mm、厚430mm，
    正常情况下长度600mm最佳。
11. 门店左右侧墙平行时，两侧墙柜道具的类别、长宽高和
     沿墙投影位置应一一对称，几何容差为0.05m。
    规则内容：门店两侧墙体平行时，左右墙柜道具应保持绝对对称。
12. 背景墙灯箱中心线应与主入口中心线对齐，偏离超过0.05m
     时输出警告。
    规则内容：背景墙灯箱优先居中主入口的中心线布置。
"""

import math

import geometry_utils as gu
import layout_data as L
from findings import (
    Finding, SEV_ERROR, SEV_INFO, SEV_WARN,
    STATUS_NOT_RELEVANT, STATUS_PASS, STATUS_WARN,
)

MODULE = "general"
_SALES_ROOM_TYPES = {"businessRoom", "vipRoom"}
_DISPLAY_CATEGORIES = {
    "lightbox_cabinet", "theme_cabinet", "light_box",
    "background_lightbox_cabinet",
}
_WALL_ITEM_CATEGORIES = {
    "lightbox_cabinet", "imaging_cabinet", "theme_cabinet",
    "light_box", "background_lightbox_cabinet", "authorization_sign",
}
_WALL_CABINET_CATEGORIES = {
    "lightbox_cabinet", "imaging_cabinet", "theme_cabinet",
    "background_lightbox_cabinet",
}


def _storefront_angle(ctx):
    """返回主玻璃门门口边的方向角；没有玻璃门时返回 ``None``。

    多个玻璃门时优先选择 ``crowdDensity`` 最大的门。门数据前两个点是
    门口边，直接作为门头方向。
    """
    doors = [opening for opening in ctx.openings
             if opening.kind == "glassDoor" and len(opening.polygon) >= 2]
    if not doors:
        return None

    def crowd_density(opening):
        try:
            return float(opening.raw.get("crowdDensity", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    door = max(doors, key=crowd_density)
    start, end = door.polygon[0], door.polygon[1]
    if gu.dist(start, end) <= gu.EPS:
        return None
    return math.degrees(
        math.atan2(end[1] - start[1], end[0] - start[0])) % 180.0


def _priority_presence(scheme, levels):
    """检查“低优先级存在时，之前所有高优先级均存在”。

    ``levels`` 为 ``[(显示名称, {分类...}, 最少数量), ...]``。返回每级
    存在性和缺失关系；同一级可包含多个可替代分类，合计达到最少数量
    即视为该级存在。
    """
    category_counts = {}
    for item in scheme.furniture:
        category_counts[item.category] = \
            category_counts.get(item.category, 0) + 1
    presence = [
        sum(category_counts.get(category, 0) for category in accepted)
        >= minimum_count
        for _name, accepted, minimum_count in levels
    ]
    failures = []
    for lower_index, lower_exists in enumerate(presence):
        if not lower_exists:
            continue
        missing = [levels[index][0] for index in range(lower_index)
                   if not presence[index]]
        if missing:
            failures.append(
                f"已布置{levels[lower_index][0]}，但更高优先级缺少"
                + "、".join(missing))
    return presence, failures


def _rule_1(ctx, scheme):
    """模块规则1：先判断横/竖店，再检查对应道具类型优先级。"""
    angle = _storefront_angle(ctx)
    if angle is None:
        return Finding(
            "1", MODULE, "按横店/竖店类型检查道具布置优先级",
            False, SEV_ERROR, scheme.index,
            "未识别到有效玻璃门，无法确定门头方向和门店类型")
    try:
        store = gu.classify_store_orientation(ctx.boundary, angle)
    except ValueError as error:
        return Finding(
            "1", MODULE, "按横店/竖店类型检查道具布置优先级",
            False, SEV_ERROR, scheme.index,
            f"无法判断门店类型：{error}")

    common_levels = [
        ("体验台", {"experience_table"}, 1),
        ("侧边封口板（头部）", {"side_end_panel"}, 1),
        ("灯箱配件柜", {"lightbox_cabinet"}, 1),
        ("配件柜（影像创作）", {"imaging_cabinet"}, 1),
        ("配件柜（主题类）", {"theme_cabinet"}, 1),
        ("侧边封口板（尾部）", {"side_end_panel"}, 2),
        ("开机服务台", {"service_desk"}, 1),
    ]
    if store["store_type"] == "vertical":
        levels = common_levels + [
            ("背景墙灯箱", {"background_lightbox_cabinet"}, 1)
        ]
        sequence = ("体验台＞侧边封口板（头部）＞灯箱配件柜＞影像创作柜＞"
                    "主题柜＞侧边封口板（尾部）＞开机服务台＞背景墙灯箱")
    else:
        levels = common_levels + [
            ("背景墙灯箱柜或补充主题柜",
             {"background_lightbox_cabinet", "theme_cabinet"}, 1)
        ]
        sequence = ("体验台＞侧边封口板（头部）＞灯箱配件柜＞影像创作柜＞"
                    "主题柜＞侧边封口板（尾部）＞开机服务台＞"
                    "背景墙灯箱柜/补充主题柜")

    presence, failures = _priority_presence(scheme, levels)
    status = "、".join(
        f"{name}{'有' if exists else '无'}"
        for (name, _accepted, _minimum_count), exists in zip(levels, presence))
    geometry = (
        f"{store['store_type_cn']}：门头{store['storefront_angle']:.2f}°，"
        f"W={store['width']:.2f}m，D={store['depth']:.2f}m，"
        f"W/D={store['ratio']:.3f}")
    detail = f"{geometry}；优先顺序：{sequence}；道具：{status}"
    if failures:
        detail += "；不符合：" + "；".join(failures)
    return Finding(
        "1", MODULE, "按横店/竖店类型检查道具布置优先级",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _line_key(start, end, angle_quantum=1.0, offset_quantum=0.05):
    """生成与旧版一致的共线墙面分组键。"""
    dx, dy = end[0] - start[0], end[1] - start[1]
    if math.hypot(dx, dy) <= gu.EPS:
        return None
    angle = math.degrees(math.atan2(dy, dx)) % 180.0
    angle_key = round(angle / angle_quantum) * angle_quantum
    radians = math.radians(angle_key)
    normal = (-math.sin(radians), math.cos(radians))
    offset = start[0] * normal[0] + start[1] * normal[1]
    return angle_key, round(offset / offset_quantum) * offset_quantum


def _parallel(first, second, tolerance=12.0):
    difference = abs(first - second) % 180.0
    return min(difference, 180.0 - difference) <= tolerance


def _wall_groups(ctx, furniture, tolerance=0.30):
    """按最近且平行的CAD实体墙面给靠墙展示道具分组。

    迁移旧版 ``wall_grouping.group_against_wall`` 的核心判定。当前项目没有
    旧版售卖区实体墙内皮模块，因此候选墙面直接使用CAD墙体多边形的边；
    共线边通过 ``_line_key`` 合并为同一面墙。
    """
    wall_edges = [edge for wall in ctx.walls for edge in gu.polygon_edges(wall)
                  if gu.dist(*edge) >= 0.05]
    groups = {}
    for item in furniture:
        if len(item.corners) < 2:
            continue
        item_angle = math.degrees(math.atan2(
            item.corners[1][1] - item.corners[0][1],
            item.corners[1][0] - item.corners[0][0]))
        candidates = []
        for edge in wall_edges:
            edge_angle = math.degrees(math.atan2(
                edge[1][1] - edge[0][1], edge[1][0] - edge[0][0]))
            if not _parallel(item_angle, edge_angle):
                continue
            distance = min(
                gu.segments_distance(a, b, edge[0], edge[1])
                for a, b in gu.polygon_edges(item.corners))
            candidates.append((distance, edge))
        if not candidates:
            continue
        distance, edge = min(candidates, key=lambda value: value[0])
        if distance > tolerance:
            continue
        key = _line_key(*edge)
        if key is not None:
            groups.setdefault(key, []).append(item)
    return groups


def _sales_display_items(scheme):
    """返回售卖区中的灯箱配件柜、主题柜和灯箱。"""
    items = []
    for room in scheme.rooms:
        if room.room_type not in _SALES_ROOM_TYPES:
            continue
        items.extend(item for item in room.furniture
                     if item.category in _DISPLAY_CATEGORIES)
    return items


def _blank_wall_ratio(scheme):
    """读取布局生成端提供的售卖区空白墙比例。"""
    ratios = []
    for room in scheme.rooms:
        if room.room_type not in _SALES_ROOM_TYPES:
            continue
        raw = room.key_attributes.get("wallItemLengthRatio")
        value = raw[0] if isinstance(raw, list) and raw else raw
        try:
            ratio = float(value)
        except (TypeError, ValueError):
            continue
        if 0.0 <= ratio <= 1.0:
            ratios.append(ratio)
    return max(ratios) if ratios else None


def _largest_blank_rect_ratio(scheme, grid_size=0.20):
    """迁移旧版网格算法，计算最大连续空白矩形/售卖区面积。"""
    try:
        from shapely.geometry import Polygon, box
        from shapely.ops import unary_union

        room_polygons = []
        for room in scheme.rooms:
            if room.room_type not in _SALES_ROOM_TYPES or len(room.polygon) < 3:
                continue
            polygon = Polygon(room.polygon)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if not polygon.is_empty:
                room_polygons.append(polygon)
        if not room_polygons:
            return None, "无法取得售卖区"
        sales_region = unary_union(room_polygons)
        sales_area = sales_region.area
        if sales_area <= gu.EPS:
            return None, "售卖区面积为0"

        furniture_polygons = []
        for item in scheme.furniture:
            if len(item.corners) < 3:
                continue
            polygon = Polygon(item.corners)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if not polygon.is_empty:
                furniture_polygons.append(polygon)
        occupied = unary_union(furniture_polygons) if furniture_polygons else None
        free_space = (sales_region.difference(occupied)
                      if occupied is not None and not occupied.is_empty
                      else sales_region)
        if free_space.is_empty:
            return 0.0, (f"售卖区{sales_area:.2f}㎡，最大连续空白矩形0.00㎡，"
                         "占比0.0%")

        min_x, min_y, max_x, max_y = sales_region.bounds
        columns = int((max_x - min_x) // grid_size)
        rows = int((max_y - min_y) // grid_size)
        if rows <= 0 or columns <= 0:
            return None, "售卖区尺寸不足一个计算网格"

        heights = [0] * columns
        best_cells = best_width = best_height = 0
        for row in range(rows):
            y = min_y + row * grid_size
            for column in range(columns):
                x = min_x + column * grid_size
                cell = box(x, y, x + grid_size, y + grid_size)
                heights[column] = (heights[column] + 1
                                   if free_space.covers(cell) else 0)

            stack = []
            for column in range(columns + 1):
                height = heights[column] if column < columns else 0
                start = column
                while stack and stack[-1][1] > height:
                    left, old_height = stack.pop()
                    width = column - left
                    cells = width * old_height
                    if cells > best_cells:
                        best_cells = cells
                        best_width = width
                        best_height = old_height
                    start = left
                if not stack or stack[-1][1] < height:
                    stack.append((start, height))

        area = best_cells * grid_size * grid_size
        ratio = area / sales_area
        detail = (f"售卖区{sales_area:.2f}㎡，最大连续空白矩形约"
                  f"{best_width * grid_size:.1f}m×{best_height * grid_size:.1f}m="
                  f"{area:.2f}㎡，占比{ratio:.1%}")
        return ratio, detail
    except Exception as error:
        return None, f"空白面积计算异常：{type(error).__name__}: {error}"


def _rule_2(ctx, scheme):
    """模块规则2：旧版前三项，不执行AI中岛均匀性判断。"""
    display_items = _sales_display_items(scheme)
    groups = _wall_groups(ctx, display_items)
    concentrated = len(display_items) >= 2 and len(groups) <= 1

    blank_ratio = _blank_wall_ratio(scheme)
    blank_wall_ok = blank_ratio is not None and blank_ratio <= 0.25

    blank_rect_ratio, blank_rect_detail = _largest_blank_rect_ratio(scheme)
    blank_rect_ok = blank_rect_ratio is not None and blank_rect_ratio <= 0.20

    failures = []
    if concentrated:
        failures.append(f"{len(display_items)}件展示道具集中在{len(groups)}面墙")
    if blank_ratio is None:
        failures.append("缺少有效wallItemLengthRatio")
    elif not blank_wall_ok:
        failures.append(f"空白墙比例{blank_ratio:.1%}＞25%")
    if blank_rect_ratio is None:
        failures.append(blank_rect_detail)
    elif not blank_rect_ok:
        failures.append(f"最大连续空白矩形占比{blank_rect_ratio:.1%}＞20%")

    wall_detail = (f"{len(display_items)}件展示道具分布在{len(groups)}面墙；"
                   + (f"空白墙比例{blank_ratio:.1%}"
                      if blank_ratio is not None else "空白墙比例无法计算"))
    detail = wall_detail + "；" + blank_rect_detail
    if failures:
        detail += "；不符合：" + "；".join(failures)
    return Finding(
        "2", MODULE,
        "展示道具墙面分布、空白墙≤25%、最大连续空白矩形占售卖区≤20%",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_4(ctx, scheme):
    """模块规则4：消防栓暗门开口角≥130°，正前方1.5m内无道具。

    完整沿用旧版几何口径：暗门角度保留5°测量容差，即小于125°才判
    不符合；消防栓柜体正面边沿暗门开启方向外推1.5m形成净空矩形，任何
    道具与该矩形相交均判不符合。
    """
    if not ctx.fire_hydrants:
        return Finding(
            "4", MODULE, "消防栓暗门前方净空≥1.5m且开口角≥130°",
            True, SEV_INFO, scheme.index, "未识别到消防栓")

    angle_minimum = 130.0
    angle_tolerance = 5.0
    clearance = 1.5
    failures = []
    unverifiable = []
    checked = []

    for index, hydrant in enumerate(ctx.fire_hydrants, 1):
        label = (f"消防栓{index}" if len(ctx.fire_hydrants) > 1 else "消防栓")
        angle = hydrant.open_angle
        front_edge = hydrant.front_edge
        front_direction = hydrant.front_dir
        if angle is None or front_edge is None or front_direction is None:
            unverifiable.append(f"{label}无暗门或暗门几何异常，无法校验")
            continue

        if angle < angle_minimum - angle_tolerance:
            failures.append(f"{label}开口角{angle:.1f}°＜130°")
        elif angle < angle_minimum:
            checked.append(f"{label}开口角{angle:.1f}°，在5°容差内达标")
        else:
            checked.append(f"{label}开口角{angle:.1f}°≥130°")

        first, second = front_edge
        clearance_area = [
            first,
            second,
            (second[0] + clearance * front_direction[0],
             second[1] + clearance * front_direction[1]),
            (first[0] + clearance * front_direction[0],
             first[1] + clearance * front_direction[1]),
        ]
        blockers = [item.name for item in scheme.furniture
                    if item.corners
                    and L.polygons_intersect(item.corners, clearance_area)]
        if blockers:
            failures.append(
                f"{label}前方1.5m内有道具：{'、'.join(blockers)}")
        else:
            checked.append(f"{label}前方1.5m内无道具")

    if failures:
        detail = "不符合：" + "；".join(failures)
        if checked:
            detail += "；其余检查：" + "；".join(checked)
        if unverifiable:
            detail += "；无法校验：" + "；".join(unverifiable)
    elif checked:
        detail = "符合：" + "；".join(checked)
        if unverifiable:
            detail += "；" + "；".join(unverifiable)
    else:
        detail = "；".join(unverifiable) + "；无有效暗门几何数据，默认符合"

    return Finding(
        "4", MODULE, "消防栓暗门前方净空≥1.5m且开口角≥130°",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_5(scheme):
    """模块规则5：当前JSON暂无疏散门数据，暂不进行几何判断。"""
    return Finding(
        "5", MODULE, "疏散门前1.5m范围内禁止摆放任何道具",
        True, SEV_INFO, scheme.index,
        "JSON 暂无疏散门（安全门）数据，规则不涉及")


def _rule_6(scheme):
    """模块规则6：当前JSON暂无防火卷闸数据，暂不进行几何判断。"""
    return Finding(
        "6", MODULE, "防火卷闸正下方及两侧各0.5m范围禁止摆放道具",
        True, SEV_INFO, scheme.index,
        "JSON 暂无防火卷闸数据，规则跳过")


def _rule_7(ctx, scheme):
    """模块规则7：墙面类道具不得与门相交或紧贴门口。"""
    blocked = []
    too_close = []
    checked = []
    doors = L.doors(ctx)
    wall_items = [item for item in scheme.furniture
                  if item.category in _WALL_ITEM_CATEGORIES]

    for item in wall_items:
        if L.furniture_blocks_opening(ctx, item, "door"):
            blocked.append(item.name)
            continue
        distance = L.nearest_opening_distance(ctx, item, "door")
        if distance < 0.10:
            too_close.append(f"{item.name}（{distance:.2f}m）")
        elif math.isfinite(distance):
            checked.append(f"{item.name}距最近门{distance:.2f}m")

    failures = []
    if blocked:
        failures.append("堵门（相交）：" + "、".join(blocked))
    if too_close:
        failures.append("紧贴门口（＜0.10m）：" + "、".join(too_close))

    if failures:
        detail = "不符合：" + "；".join(failures)
    elif not doors:
        detail = "未识别到普通门，墙面类道具未影响门开启"
    elif not wall_items:
        detail = "未识别到墙面类道具"
    else:
        detail = (f"检查{len(wall_items)}件墙面类道具、{len(doors)}处普通门，"
                  "均未堵门或紧贴门口")
        if checked:
            detail += "；" + "；".join(checked)
    return Finding(
        "7", MODULE, "靠墙及墙面类道具不得影响门正常开启",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_8(ctx, scheme):
    """模块规则8：墙面类道具不得与玻璃墙相交或紧贴玻璃墙。"""
    glass_walls = L.glass_walls(ctx)
    wall_items = [item for item in scheme.furniture
                  if item.category in _WALL_ITEM_CATEGORIES]
    violations = [item.name for item in wall_items
                  if L.furniture_on_glasswall(ctx, item, tol=0.05)]

    if violations:
        detail = "不符合，布置在玻璃墙前：" + "、".join(violations)
    elif not glass_walls:
        detail = "未识别到玻璃墙，规则不涉及"
    elif not wall_items:
        detail = "未识别到墙面类道具"
    else:
        detail = (f"检查{len(wall_items)}件墙面类道具、"
                  f"{len(glass_walls)}处玻璃墙，均未压住或紧贴玻璃墙")
    return Finding(
        "8", MODULE, "靠墙及墙面类道具不可布置在玻璃墙前",
        not violations, SEV_INFO if not violations else SEV_ERROR,
        scheme.index, detail)


def _rule_9(scheme):
    """模块规则9：五类必需道具均不得缺失。"""
    required = [
        ("体验台", "experience_table"),
        ("灯箱配件柜", "lightbox_cabinet"),
        ("配件柜（影像创作）", "imaging_cabinet"),
        ("开机服务台", "service_desk"),
        ("背景墙灯箱", "background_lightbox_cabinet"),
    ]
    counts = [(name, scheme.count(category)) for name, category in required]
    missing = [name for name, count in counts if count == 0]
    count_detail = "、".join(f"{name}{count}件" for name, count in counts)
    detail = count_detail
    if missing:
        detail += "；缺失品类：" + "、".join(missing)
    else:
        detail += "；必需道具品类齐全"
    return Finding(
        "9", MODULE,
        "体验台、灯箱配件柜、影像创作柜、开机服务台、背景墙灯箱不可缺失",
        not missing, SEV_INFO if not missing else SEV_ERROR,
        scheme.index, detail)


def _rule_10(ctx, scheme):
    """模块规则10：入口墙垛长度0.30–0.90m、厚度0.43m±0.05m。"""
    wall_entries = []
    wall_segments = []
    for wall_index, wall in enumerate(ctx.walls):
        for edge in gu.polygon_edges(wall):
            if gu.dist(*edge) <= 0.05:
                continue
            wall_segments.append(edge)
            wall_entries.append((edge, wall_index, wall))

    frontage_segments = []
    for opening in ctx.openings:
        if opening.kind != "glassWall":
            continue
        frontage_segments.extend(
            edge for edge in gu.polygon_edges(opening.polygon)
            if gu.dist(*edge) > 0.05)
    # 只用玻璃墙扩展门头立面。若把全部实体墙放入候选，
    # 入口侧的普通墙可能被连锁吸收，从而掩盖真正的第一次转折。

    entrances = [
        opening for opening in ctx.openings
        if opening.kind in {"glassDoor", "openedDoor", "safetyDoor"}
        and len(opening.polygon) >= 2
    ]
    if not entrances:
        return Finding(
            "10", MODULE, "入口墙垛长0.30–0.90m、厚0.43m",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未识别到入口门，规则不涉及")

    def source_wall(segment):
        """将入口侧转折线段映射回最接近的CAD墙体多边形。"""
        candidates = []
        for edge, wall_index, wall in wall_entries:
            direct = gu.dist(segment[0], edge[0]) + gu.dist(segment[1], edge[1])
            reverse = gu.dist(segment[0], edge[1]) + gu.dist(segment[1], edge[0])
            candidates.append((min(direct, reverse), wall_index, wall))
        return min(candidates, key=lambda value: value[0]) if candidates else None

    piers = []
    ordinary_walls = []
    missing_turns = []
    for entrance_index, entrance in enumerate(entrances, 1):
        sides = gu.entrance_side_wall_segments(
            entrance, wall_segments, frontage_segments, ctx.boundary)
        for side_name, side_label in (("left", "左侧"), ("right", "右侧")):
            turn = sides[side_name]
            label = f"入口{entrance_index}{side_label}"
            if turn is None:
                missing_turns.append(label + "未识别到垂直转折墙")
                continue
            if turn["length"] > 1.5 + gu.EPS:
                ordinary_walls.append(
                    f"{label}首次转折为普通侧墙（墙段{turn['length']:.2f}m）")
                continue
            mapped = source_wall(turn["segment"])
            if mapped is None:
                piers.append({"label": label, "length": turn["length"],
                              "thickness": None})
                continue
            _error, _wall_index, wall_polygon = mapped
            dimensions = gu.minimum_rotated_rectangle_dimensions(wall_polygon)
            if dimensions is None:
                length, thickness = turn["length"], None
            else:
                rectangle_length, rectangle_thickness, _angle = dimensions
                # 转折墙段是墙垛内侧的长度；墙体最小旋转矩形短边作为厚度。
                length = min(turn["length"], rectangle_length)
                thickness = rectangle_thickness
            piers.append({"label": label, "length": length,
                          "thickness": thickness})

    if not piers:
        details = ordinary_walls + missing_turns
        return Finding(
            "10", MODULE, "入口墙垛长0.30–0.90m、厚0.43m",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            ("未检测到入口墙垛，规则不涉及"
             + (("；" + "；".join(details)) if details else "")))

    violations = []
    measurements = []
    for pier in piers:
        length = pier["length"]
        thickness = pier["thickness"]
        thickness_text = (f"{thickness:.2f}m" if thickness is not None
                          else "无法计算")
        best = "（接近0.60m最佳长度）" if abs(length - 0.60) <= 0.05 else ""
        measurements.append(
            f"{pier['label']}墙垛{length:.2f}×{thickness_text}{best}")
        if length < 0.30 - gu.EPS or length > 0.90 + gu.EPS:
            violations.append(
                f"{pier['label']}墙垛长度{length:.2f}m不在0.30–0.90m")
        if thickness is None:
            violations.append(f"{pier['label']}墙垛厚度无法计算")
        elif thickness < 0.38 - gu.EPS or thickness > 0.48 + gu.EPS:
            violations.append(
                f"{pier['label']}墙垛厚度{thickness:.2f}m不在0.43±0.05m")

    detail = "；".join(measurements)
    if violations:
        detail += "；警告：" + "；".join(violations)
        status, severity = STATUS_WARN, SEV_WARN
    else:
        detail += "；尺寸符合"
        status, severity = STATUS_PASS, SEV_INFO
    if ordinary_walls:
        detail += "；" + "；".join(ordinary_walls)
    if missing_turns:
        detail += "；" + "；".join(missing_turns)
    return Finding(
        "10", MODULE, "入口墙垛长0.30–0.90m、厚0.43m",
        status, severity, scheme.index, detail)


def _rule_11(ctx, scheme):
    """模块规则11：平行左右侧墙的墙柜道具尺寸和位置绝对对称。"""
    storefront_angle = _storefront_angle(ctx)
    if storefront_angle is None:
        return Finding(
            "11", MODULE, "左右墙柜道具保持绝对对称",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未识别到有效门头方向，无法确定左右侧墙")

    side_walls = gu.parallel_side_walls(
        ctx.boundary, ctx.walls, storefront_angle)
    if side_walls is None:
        return Finding(
            "11", MODULE, "左右墙柜道具保持绝对对称",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未识别到一组有效的平行左右侧墙，规则不涉及")

    left_wall, right_wall, wall_axis = side_walls
    wall_items = [item for item in scheme.furniture
                  if item.category in _WALL_CABINET_CATEGORIES]

    def assigned_items(wall, other_wall):
        result = []
        for item in wall_items:
            # CAD侧墙常被拆成多个短线段；归墙时只量到墙所在
            # 直线的垂距，沿墙方向的位置由后续投影单独比较。
            distance = gu.polygon_line_distance(item.corners, *wall)
            other_distance = gu.polygon_line_distance(item.corners, *other_wall)
            if distance <= 0.30 + gu.EPS and distance < other_distance:
                position = gu.axis_projection(item.center, wall_axis)
                center_distance = gu.point_line_distance(item.center, *wall)
                result.append((position, center_distance, item))
        return sorted(result, key=lambda value: value[0])

    left_items = assigned_items(left_wall, right_wall)
    right_items = assigned_items(right_wall, left_wall)
    failures = []
    comparisons = []
    if len(left_items) != len(right_items):
        failures.append(
            f"左侧{len(left_items)}件、右侧{len(right_items)}件，数量不对称")

    pair_count = min(len(left_items), len(right_items))
    for index in range(pair_count):
        left_position, left_depth, left_item = left_items[index]
        right_position, right_depth, right_item = right_items[index]
        prefix = f"第{index + 1}组{left_item.name}/{right_item.name}"
        issues = []
        if left_item.category != right_item.category:
            issues.append(
                f"类别{left_item.category}/{right_item.category}不同")
        dimensions = (
            ("长", left_item.length, right_item.length),
            ("宽", left_item.width, right_item.width),
            ("高", left_item.height, right_item.height),
        )
        for label, left_value, right_value in dimensions:
            if abs(left_value - right_value) > 0.05 + gu.EPS:
                issues.append(
                    f"{label}{left_value:.2f}/{right_value:.2f}m")
        position_difference = abs(left_position - right_position)
        if position_difference > 0.05 + gu.EPS:
            issues.append(f"沿墙位置偏差{position_difference:.2f}m")
        depth_difference = abs(left_depth - right_depth)
        if depth_difference > 0.05 + gu.EPS:
            issues.append(f"距墙中心深度偏差{depth_difference:.2f}m")
        comparisons.append(
            f"{prefix}：" + ("、".join(issues) if issues else "对称"))
        if issues:
            failures.append(f"{prefix}（{'、'.join(issues)}）")

    detail = (
        f"识别平行左右侧墙；左侧{len(left_items)}件、"
        f"右侧{len(right_items)}件墙面道具")
    if comparisons:
        detail += "；" + "；".join(comparisons)
    if failures:
        detail += "；警告：" + "；".join(failures)
        status, severity = STATUS_WARN, SEV_WARN
    else:
        detail += "；尺寸和位置对称"
        status, severity = STATUS_PASS, SEV_INFO
    return Finding(
        "11", MODULE, "左右墙柜道具保持绝对对称",
        status, severity,
        scheme.index, detail)


def _rule_12(ctx, scheme):
    """模块规则12：背景墙灯箱中心线与主入口中心线对齐。"""
    entrance = L.main_entrance(ctx)
    if entrance is None:
        return Finding(
            "12", MODULE, "背景墙灯箱对齐主入口中心线",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "JSON未提供有效crowdDensity，无法确定主入口")

    door_start, door_end = entrance.polygon[:2]
    door_center = ((door_start[0] + door_end[0]) / 2.0,
                   (door_start[1] + door_end[1]) / 2.0)
    store_center = gu.polygon_centroid(ctx.boundary)
    inward = (store_center[0] - door_center[0],
              store_center[1] - door_center[1])
    inward_length = math.hypot(*inward)
    if inward_length <= gu.EPS:
        return Finding(
            "12", MODULE, "背景墙灯箱对齐主入口中心线",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "主入口中心与门店中心重合，无法确定入店中心线")
    inward_unit = (inward[0] / inward_length, inward[1] / inward_length)

    candidates = []
    for item in scheme.furniture:
        if (item.category != "background_lightbox_cabinet"
                or len(item.corners) < 2):
            continue
        inward_position = gu.axis_projection(
            item.center, inward_unit, door_center)
        # 型号已经明确标识背景墙灯箱，无需再用“与门头平行”猜测类别；
        # 多个背景墙灯箱中取沿入店方向最深的一件检查中心线。
        candidates.append((inward_position, item))

    if not candidates:
        return Finding(
            "12", MODULE, "背景墙灯箱对齐主入口中心线",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未识别到背景墙灯箱")

    _depth, light_box = max(candidates, key=lambda value: value[0])
    offset = gu.point_line_distance(
        light_box.center, door_center,
        (door_center[0] + inward_unit[0],
         door_center[1] + inward_unit[1]))
    outside = _depth <= gu.EPS
    if outside or offset > 0.05 + gu.EPS:
        detail = (f"{light_box.name}中心偏离主入口中心线"
                  f"{offset:.2f}m（0.05m容差）"
                  + ("，且不在入口内侧" if outside else "")
                  + "；警告：未对齐")
        status, severity = STATUS_WARN, SEV_WARN
    else:
        detail = (f"{light_box.name}中心偏离主入口中心线"
                  f"{offset:.2f}m，对齐")
        status, severity = STATUS_PASS, SEV_INFO
    return Finding(
        "12", MODULE, "背景墙灯箱对齐主入口中心线",
        status, severity, scheme.index, detail)


def check(ctx, schemes):
    findings = []
    for scheme in schemes:
        findings.extend((_rule_1(ctx, scheme), _rule_2(ctx, scheme),
                         _rule_4(ctx, scheme), _rule_5(scheme),
                         _rule_6(scheme), _rule_7(ctx, scheme),
                         _rule_8(ctx, scheme), _rule_9(scheme),
                         _rule_10(ctx, scheme),
                         _rule_11(ctx, scheme),
                         _rule_12(ctx, scheme)))
    return findings
