"""开机服务台布局原则。

当前文件实现的模块内规则（本文件独立从1开始）：
1. 开机服务台在双出入口时位于两入口之间，并遵循体验台的对齐规则。
   规则内容：开机服务台在双出入口时宜放在中间位置，并遵循体验台的
   对齐规则。
2. 背景墙灯箱与背景墙灯箱柜按同一道具处理，检查开机服务台到该
   道具的投影净距，要求0.8–1.4m。
   规则内容：开机服务台与背景墙灯箱或背景墙灯箱柜为一体，二者间距
   保持0.8–1.4m；没有背景墙灯箱时优先布置在后场。
3. 开机服务台与体验台共用同一套主/副通道净宽规则。
   规则内容：开机服务台与体验台共用同一套主、副通道净宽规则。

模块规则1的对齐部分与体验台模块规则4共用判断；模块规则3
与体验台模块规则5共用判断，但均独立输出。
"""

import geometry_utils as gu
from findings import Finding, SEV_ERROR, SEV_INFO
from rules import experience_table, general

MODULE = "service_desk"


def _service_desks(scheme):
    return [item for item in scheme.furniture
            if item.category == "service_desk"]


def _glass_doors(ctx):
    return [opening.polygon for opening in ctx.openings
            if opening.kind == "glassDoor" and len(opening.polygon) >= 2]


def _background_lightbox_cabinets(scheme):
    """返回明确标识为背景墙灯箱柜的道具，不混入普通灯箱配件柜。"""
    return [
        item for item in scheme.furniture
        if item.category == "background_lightbox_cabinet"
        or "背景墙灯箱柜" in item.name
        or "背景墙灯箱柜" in item.model
    ]


def _projected_distance(source, targets):
    """返回源道具四边向外投影到目标道具的最小净距及目标。"""
    best = None
    for edge_index, edge in enumerate(gu.polygon_edges(source.corners)):
        midpoint = ((edge[0][0] + edge[1][0]) / 2.0,
                    (edge[0][1] + edge[1][1]) / 2.0)
        direction = (midpoint[0] - source.cx, midpoint[1] - source.cy)
        for target in targets:
            distance = gu.edge_directional_polygon_distance(
                edge, direction, target.corners)
            if distance is None:
                continue
            if best is None or distance < best[0]:
                best = distance, target, edge_index
    return best


def _rule_1(ctx, scheme):
    """模块规则1：双出入口时居中，并遵循体验台对齐规则。"""
    services = _service_desks(scheme)
    failures = []
    checked = []

    if not services:
        failures.append("未识别到开机服务台")

    doors = _glass_doors(ctx)
    if len(doors) >= 2 and services:
        first = gu.polygon_centroid(doors[0])
        second = gu.polygon_centroid(doors[1])
        vx, vy = second[0] - first[0], second[1] - first[1]
        denominator = vx * vx + vy * vy
        if denominator <= gu.EPS:
            failures.append("两个入口中心重合，无法判断中间位置")
        else:
            for desk in services:
                # 沿两个入口中心的连线投影。保留旧版0.1–0.9范围，避免
                # 服务台仅仅落在线段端点附近也被视为“位于中间”。
                t = ((desk.cx - first[0]) * vx +
                     (desk.cy - first[1]) * vy) / denominator
                message = f"{desk.name}在双入口连线上的位置比例为{t:.2f}"
                checked.append(message)
                if not 0.1 <= t <= 0.9:
                    failures.append(message + "（要求0.10–0.90）")
    elif len(doors) < 2:
        checked.append(f"识别到{len(doors)}个玻璃门入口，不触发双入口居中判断")

    alignment = experience_table._rule_4(scheme)
    checked.append("共同对齐判断：" + alignment.detail)
    if not alignment.passed:
        failures.append("未满足体验台共同对齐规则：" + alignment.detail)

    detail = ("不符合：" + "；".join(failures) if failures
              else "符合：" + "；".join(checked))
    return Finding(
        "1", MODULE, "开机服务台双出入口时位于中间，并遵循体验台对齐规则",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_2(ctx, scheme):
    """模块规则2：按横/竖店检查开机服务台到背景墙道具的投影净距。"""
    services = _service_desks(scheme)
    failures = []
    checked = []

    angle = general._storefront_angle(ctx)
    if angle is None:
        return Finding(
            "2", MODULE, "开机服务台距背景墙灯箱/灯箱柜0.8–1.4m",
            False, SEV_ERROR, scheme.index,
            "未识别到有效玻璃门，无法判断横店或竖店")
    try:
        store = gu.classify_store_orientation(ctx.boundary, angle)
    except ValueError as error:
        return Finding(
            "2", MODULE, "开机服务台距背景墙灯箱/灯箱柜0.8–1.4m",
            False, SEV_ERROR, scheme.index,
            f"无法判断横店或竖店：{error}")

    # 背景墙灯箱与背景墙灯箱柜现已确认是同一道具类别，横店和竖店
    # 均直接使用明确型号，不再把普通light_box误当背景墙灯箱。
    targets = _background_lightbox_cabinets(scheme)
    target_label = "背景墙灯箱（柜）"

    if not services:
        failures.append("未识别到开机服务台")
    if not targets:
        failures.append(f"{store['store_type_cn']}未识别到{target_label}")

    for service in services:
        measured = _projected_distance(service, targets)
        if measured is None:
            failures.append(
                f"{service.name}没有可投影到的{target_label}")
            continue
        distance, target, edge_index = measured
        measurement = (
            f"{service.name}边{edge_index + 1}到{target.name}投影净距"
            f"{distance:.2f}m")
        checked.append(measurement)
        if distance < 0.8 - gu.EPS or distance > 1.4 + gu.EPS:
            failures.append(measurement + "（要求0.8–1.4m）")

    geometry = (f"{store['store_type_cn']}：W={store['width']:.2f}m，"
                f"D={store['depth']:.2f}m，W/D={store['ratio']:.3f}")
    detail = geometry
    if checked:
        detail += "；" + "；".join(checked)
    if failures:
        detail += "；不符合：" + "；".join(failures)
    else:
        detail += "；符合"
    return Finding(
        "2", MODULE, "开机服务台距背景墙灯箱/灯箱柜0.8–1.4m",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def _rule_3(ctx, scheme):
    """模块规则3：与体验台共用同一套主/副通道净宽规则。"""
    services = _service_desks(scheme)
    shared = experience_table._rule_5(ctx, scheme)
    failures = []
    if not services:
        failures.append("未识别到开机服务台")
    if not shared.passed:
        failures.append(shared.detail)

    detail = ("不符合：" + "；".join(failures) if failures
              else "符合：共同通道判断：" + shared.detail)
    return Finding(
        "3", MODULE, "开机服务台与体验台共用同一套主/副通道净宽规则",
        not failures, SEV_INFO if not failures else SEV_ERROR,
        scheme.index, detail)


def check(ctx, schemes):
    findings = []
    for scheme in schemes:
        findings.extend((_rule_1(ctx, scheme), _rule_2(ctx, scheme),
                         _rule_3(ctx, scheme)))
    return findings
