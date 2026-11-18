"""灯箱布局原则。

当前文件实现的模块内规则（本文件独立从1开始）：
4. 查找与其它道具轮廓净距不超过0.03m的灯箱组合；连接主客流入口
   中点与灯箱、相邻道具的中心，灯箱到入口的距离须不大于相邻道具。
   规则内容：灯箱与其它配件搭配使用时，灯箱需要靠近主客流侧对面
   放置，保证客户第一视觉能看到。
6. 存在背景墙灯箱时，逐个检查其它普通灯箱的两个侧边；普通灯箱须有
   侧边在0.03m内紧贴道具，且所有紧贴对象只能是灯箱配件柜。
   规则内容：放置背景墙灯箱后不能再有单独灯箱，但普通灯箱可以搭配
   灯箱配件柜使用。
7. 先判断横长/竖长门店并将背景墙灯箱、主题配件柜匹配到合并后的完整
   墙段。竖店每段最多一个背景墙灯箱；横店每个含背景墙灯箱的墙段须
   恰好形成“主题柜+背景墙灯箱+主题柜”，两侧净距不超过0.03m、主题柜
   尺寸一致，且全店主题柜模型不得重复。
   规则内容：竖长门店一面墙只能布置一个背景墙灯箱；横长门店一面墙
   只能布置一套背景墙灯箱柜组合，两侧主题配件柜尺寸相同，店内模型
   不得重复。
"""

import math

import geometry_utils as gu
import layout_data as L
from rules import general
from findings import (
    Finding, SEV_ERROR, SEV_INFO,
    STATUS_NOT_RELEVANT,
)

MODULE = "light_box"


def _rule_4(ctx, scheme):
    """模块规则4：紧贴其它道具的灯箱应比相邻道具更靠近主入口。"""
    light_box_categories = {"light_box", "background_lightbox_cabinet"}
    light_boxes = [item for item in scheme.furniture
                   if item.category in light_box_categories]
    pairs = []
    for light_box in light_boxes:
        if not light_box.corners:
            continue
        for other in scheme.furniture:
            if other is light_box or other.category in light_box_categories:
                continue
            if not other.corners:
                continue
            gap = gu.polygons_distance(light_box.corners, other.corners)
            if gap <= 0.03 + gu.EPS:
                pairs.append((light_box, other, gap))

    if not pairs:
        return Finding(
            "4", MODULE, "灯箱搭配其它道具时位于主客流近侧",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            ("未布置灯箱，规则不涉及" if not light_boxes
             else "灯箱未与其它道具紧贴搭配，规则不涉及"))

    entrance = L.main_entrance(ctx)
    if entrance is None:
        return Finding(
            "4", MODULE, "灯箱搭配其它道具时位于主客流近侧",
            False, SEV_ERROR, scheme.index,
            "存在灯箱与其它道具紧贴组合，但JSON未提供有效crowdDensity，"
            "无法确定主客流入口")

    door_center = gu.polygon_centroid(entrance.polygon)
    failures = []
    checked = []
    for light_box, other, gap in pairs:
        light_distance = math.hypot(
            light_box.cx - door_center[0], light_box.cy - door_center[1])
        other_distance = math.hypot(
            other.cx - door_center[0], other.cy - door_center[1])
        checked.append(
            f"{light_box.name}+{other.name}紧贴{gap:.2f}m："
            f"灯箱距主入口{light_distance:.2f}m/"
            f"相邻道具{other_distance:.2f}m")
        if light_distance > other_distance + gu.EPS:
            failures.append(
                f"{light_box.name}距主入口{light_distance:.2f}m，"
                f"比相邻{other.name}{other_distance:.2f}m更远")

    detail = "；".join(checked)
    if failures:
        detail += "；不符合：" + "；".join(failures)
    else:
        detail += "；所有搭配灯箱均位于相邻道具的主客流近侧"
    return Finding(
        "4", MODULE, "灯箱搭配其它道具时位于主客流近侧",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _side_edges(item):
    """返回矩形道具的两个短边（侧面边）。"""
    edges = gu.polygon_edges(item.corners)
    if len(edges) < 4:
        return []
    lengths = [gu.dist(*edge) for edge in edges]
    shortest = min(lengths)
    return [edge for edge, length in zip(edges, lengths)
            if abs(length - shortest) <= 0.01][:2]


def _rule_6(scheme):
    """模块规则6：有背景墙灯箱时，普通灯箱只能连灯箱配件柜使用。"""
    backgrounds = [
        item for item in scheme.furniture
        if item.category == "background_lightbox_cabinet"
    ]
    if not backgrounds:
        return Finding(
            "6", MODULE, "背景墙灯箱存在时普通灯箱只能搭配灯箱配件柜",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未布置背景墙灯箱，规则不涉及")

    ordinary_boxes = [item for item in scheme.furniture
                      if item.category == "light_box"]
    if not ordinary_boxes:
        return Finding(
            "6", MODULE, "背景墙灯箱存在时普通灯箱只能搭配灯箱配件柜",
            True, SEV_INFO, scheme.index,
            f"已布置{len(backgrounds)}个背景墙灯箱，无其它普通灯箱；符合")

    failures = []
    checked = []
    for light_box in ordinary_boxes:
        sides = _side_edges(light_box)
        if len(sides) != 2:
            failures.append(f"{light_box.name}无法识别两个侧边")
            continue

        touching = []
        for side_index, edge in enumerate(sides, 1):
            midpoint = ((edge[0][0] + edge[1][0]) / 2.0,
                        (edge[0][1] + edge[1][1]) / 2.0)
            outward = (midpoint[0] - light_box.cx,
                       midpoint[1] - light_box.cy)
            distance, neighbor = gu.nearest_object_in_edge_direction(
                edge, outward, scheme.furniture, exclude=light_box)
            if (distance is None or neighbor is None
                    or distance > 0.03 + gu.EPS):
                continue
            touching.append((side_index, distance, neighbor))

        if not touching:
            failures.append(
                f"{light_box.name}两个侧边均未在0.03m内紧贴道具，属于单独灯箱")
            continue

        checked.append(
            f"{light_box.name}紧贴" + "、".join(
                f"侧边{side_index}-{neighbor.name}({distance:.2f}m)"
                for side_index, distance, neighbor in touching))
        invalid = [neighbor for _side_index, _distance, neighbor in touching
                   if neighbor.category != "lightbox_cabinet"]
        if invalid:
            failures.append(
                f"{light_box.name}侧边紧贴了非灯箱配件柜："
                + "、".join(item.name for item in invalid))

    detail = (f"背景墙灯箱{len(backgrounds)}个，"
              f"其它普通灯箱{len(ordinary_boxes)}个")
    if checked:
        detail += "；" + "；".join(checked)
    if failures:
        detail += "；不符合：" + "；".join(failures)
    else:
        detail += "；普通灯箱均只与灯箱配件柜搭配使用"
    return Finding(
        "6", MODULE, "背景墙灯箱存在时普通灯箱只能搭配灯箱配件柜",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _angle_difference(first, second):
    difference = abs(first - second) % 180.0
    return min(difference, 180.0 - difference)


def _assign_to_wall_runs(ctx, items, distance_tolerance=0.30,
                         angle_tolerance=12.0):
    """将靠墙道具分配到最近的平行完整墙段。"""
    runs = gu.build_wall_runs(ctx.walls)
    groups = {}
    unmatched = []
    for item in items:
        if len(item.corners) < 3:
            unmatched.append(item)
            continue
        long_edge = max(gu.polygon_edges(item.corners),
                        key=lambda edge: gu.dist(*edge))
        item_angle = math.degrees(math.atan2(
            long_edge[1][1] - long_edge[0][1],
            long_edge[1][0] - long_edge[0][0])) % 180.0
        candidates = []
        for run_index, (start, end, _length) in enumerate(runs):
            run_angle = math.degrees(math.atan2(
                end[1] - start[1], end[0] - start[0])) % 180.0
            if _angle_difference(item_angle, run_angle) > angle_tolerance:
                continue
            distance = gu.polygon_line_distance(item.corners, start, end)
            if distance > distance_tolerance + gu.EPS:
                continue
            lower, upper = gu.polygon_segment_span(
                item.corners, (start, end))
            if upper < -gu.EPS or lower > 1.0 + gu.EPS:
                continue
            candidates.append((distance, run_index))
        if not candidates:
            unmatched.append(item)
            continue
        _distance, run_index = min(candidates, key=lambda value: value[0])
        groups.setdefault(run_index, []).append(item)
    return runs, groups, unmatched


def _rule_7(ctx, scheme):
    """模块规则7：按横/竖店检查背景墙灯箱墙段组合。"""
    backgrounds = [
        item for item in scheme.furniture
        if item.category == "background_lightbox_cabinet"
    ]
    if not backgrounds:
        return Finding(
            "7", MODULE, "横竖店背景墙灯箱墙段组合符合规定",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未布置背景墙灯箱，规则不涉及")

    storefront_angle = general._storefront_angle(ctx)
    if storefront_angle is None:
        return Finding(
            "7", MODULE, "横竖店背景墙灯箱墙段组合符合规定",
            False, SEV_ERROR, scheme.index,
            "未识别到有效玻璃门，无法判断横长或竖长门店")
    try:
        store = gu.classify_store_orientation(ctx.boundary, storefront_angle)
    except ValueError as error:
        return Finding(
            "7", MODULE, "横竖店背景墙灯箱墙段组合符合规定",
            False, SEV_ERROR, scheme.index,
            f"无法判断横长或竖长门店：{error}")

    themes = [item for item in scheme.furniture
              if item.category == "theme_cabinet"]
    runs, groups, unmatched = _assign_to_wall_runs(
        ctx, backgrounds + themes)
    failures = []
    checked = []
    unmatched_backgrounds = [item for item in unmatched
                             if item.category ==
                             "background_lightbox_cabinet"]
    if unmatched_backgrounds:
        failures.append("背景墙灯箱未匹配完整墙段：" + "、".join(
            item.name for item in unmatched_backgrounds))

    if store["store_type"] == "vertical":
        for run_index, items in groups.items():
            wall_backgrounds = [
                item for item in items
                if item.category == "background_lightbox_cabinet"
            ]
            if not wall_backgrounds:
                continue
            checked.append(
                f"墙段{run_index + 1}背景墙灯箱{len(wall_backgrounds)}个")
            if len(wall_backgrounds) > 1:
                failures.append(
                    f"竖长门店墙段{run_index + 1}布置了"
                    f"{len(wall_backgrounds)}个背景墙灯箱（最多1个）")
    else:
        # “一个门店不能出现一样的模型”按本组合中的主题柜模型检查。
        model_counts = {}
        for theme in themes:
            model_counts[theme.model] = model_counts.get(theme.model, 0) + 1
        duplicates = [model for model, count in model_counts.items()
                      if count > 1]
        if duplicates:
            failures.append("主题配件柜模型重复：" + "、".join(duplicates))

        for run_index, items in groups.items():
            wall_backgrounds = [
                item for item in items
                if item.category == "background_lightbox_cabinet"
            ]
            if not wall_backgrounds:
                continue
            wall_themes = [item for item in items
                           if item.category == "theme_cabinet"]
            if len(wall_backgrounds) != 1:
                failures.append(
                    f"横长门店墙段{run_index + 1}有"
                    f"{len(wall_backgrounds)}个背景墙灯箱（要求1个）")
                continue
            if len(wall_themes) != 2:
                failures.append(
                    f"横长门店墙段{run_index + 1}背景墙灯箱两侧识别到"
                    f"{len(wall_themes)}个主题柜（要求2个）")
                continue

            start, end, _length = runs[run_index]
            dx, dy = end[0] - start[0], end[1] - start[1]
            run_length = math.hypot(dx, dy)
            axis = (dx / run_length, dy / run_length)
            background = wall_backgrounds[0]

            def position(item):
                return gu.axis_projection((item.cx, item.cy), axis, start)

            ordered = sorted(wall_themes + [background], key=position)
            if ordered[1] is not background:
                failures.append(
                    f"墙段{run_index + 1}未形成主题柜+背景墙灯箱+主题柜顺序")
                continue
            left, _middle, right = ordered
            left_gap = gu.polygons_distance(left.corners, background.corners)
            right_gap = gu.polygons_distance(background.corners, right.corners)
            checked.append(
                f"墙段{run_index + 1}：{left.name}+{background.name}+"
                f"{right.name}，两侧净距{left_gap:.2f}/{right_gap:.2f}m")
            if left_gap > 0.03 + gu.EPS or right_gap > 0.03 + gu.EPS:
                failures.append(
                    f"墙段{run_index + 1}主题柜未紧贴背景墙灯箱："
                    f"净距{left_gap:.2f}/{right_gap:.2f}m（要求≤0.03m）")

            dimension_pairs = (
                ("长", left.length, right.length),
                ("宽", left.width, right.width),
                ("高", left.height, right.height),
            )
            different = [
                f"{label}{first:.2f}/{second:.2f}m"
                for label, first, second in dimension_pairs
                if abs(first - second) > 0.05 + gu.EPS
            ]
            if different:
                failures.append(
                    f"墙段{run_index + 1}两侧主题柜尺寸不同："
                    + "、".join(different))

    detail = (f"{store['store_type_cn']}：W={store['width']:.2f}m，"
              f"D={store['depth']:.2f}m，背景墙灯箱{len(backgrounds)}个")
    if checked:
        detail += "；" + "；".join(checked)
    if failures:
        detail += "；不符合：" + "；".join(failures)
    else:
        detail += "；符合"
    return Finding(
        "7", MODULE, "横竖店背景墙灯箱墙段组合符合规定",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def check(ctx, schemes):
    findings = []
    for scheme in schemes:
        findings.extend((_rule_4(ctx, scheme), _rule_6(scheme),
                         _rule_7(ctx, scheme)))
    return findings
