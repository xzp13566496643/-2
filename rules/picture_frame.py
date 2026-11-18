"""画框布局原则。

当前文件实现的模块内规则（本文件独立从1开始）：
1. 有画框时，每个画框到最近后场分区的净距须不超过0.10m；恰好存在
   两个画框时，两个画框须至少有一组侧边投影共线，或一组长边投影
   共线。平行容差5°、投影偏移容差0.05m；不满足时输出警告。
   规则内容：画框用于后场留白区域做设计填补，并且两侧都有画框时
   注意左右对称。（可选）
2. 对每根柱子连接柱心与主客流入口中心，保留以原线段为长、柱半径为
   总宽的方向矩形；实际检测靠柱端区域：从柱心朝入口延伸一个柱半径，
   宽度为柱半径。该区域须覆盖至少一个其它道具，否则输出警告。
   规则内容：包柱空白主客流方向可做画框等设计填补。（可选）
"""

import math

import geometry_utils as gu
import layout_data as L
from findings import (
    Finding, SEV_INFO, SEV_WARN, STATUS_NOT_RELEVANT,
    STATUS_PASS, STATUS_WARN,
)

MODULE = "picture_frame"


def _edge_angle(edge):
    return math.degrees(math.atan2(
        edge[1][1] - edge[0][1], edge[1][0] - edge[0][0])) % 180.0


def _angle_difference(first, second):
    difference = abs(first - second) % 180.0
    return min(difference, 180.0 - difference)


def _edge_groups(frame):
    """返回画框的 ``(长边, 侧边)``。"""
    edges = gu.polygon_edges(frame.corners)
    if len(edges) < 4:
        return [], []
    lengths = [gu.dist(*edge) for edge in edges]
    longest = max(lengths)
    shortest = min(lengths)
    long_edges = [edge for edge, length in zip(edges, lengths)
                  if abs(length - longest) <= 0.01][:2]
    side_edges = [edge for edge, length in zip(edges, lengths)
                  if abs(length - shortest) <= 0.01][:2]
    return long_edges, side_edges


def _projected_edges_align(first_edges, second_edges,
                           angle_tolerance=5.0,
                           offset_tolerance=0.05):
    """任意两条同组边平行且无限直线投影偏移≤容差时返回True。"""
    for first in first_edges:
        first_angle = _edge_angle(first)
        for second in second_edges:
            if _angle_difference(first_angle, _edge_angle(second)) \
                    > angle_tolerance:
                continue
            midpoint = ((second[0][0] + second[1][0]) / 2.0,
                        (second[0][1] + second[1][1]) / 2.0)
            if gu.point_line_distance(midpoint, first[0], first[1]) \
                    <= offset_tolerance + gu.EPS:
                return True
    return False


def _rule_1(ctx, scheme):
    """模块规则1：画框靠近后场；两个画框至少一组侧边或长边对齐。"""
    frames = [item for item in scheme.furniture
              if item.category == "picture_frame"]
    if not frames:
        return Finding(
            "1", MODULE, "画框位于后场留白区域，两个画框左右对称",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未布置画框，可选规则不涉及")

    backstage = L.backstage_polygons(ctx, scheme)
    warnings = []
    details = []
    if not backstage:
        warnings.append("未识别到有效后场分区，无法确认画框靠近后场")
    else:
        for index, frame in enumerate(frames, 1):
            if not frame.corners:
                warnings.append(f"画框{index}（{frame.name}）缺少有效轮廓")
                continue
            distance = min(
                gu.polygons_distance(frame.corners, polygon)
                for polygon in backstage)
            details.append(f"画框{index}距最近后场{distance:.2f}m")
            if distance > 0.10 + gu.EPS:
                warnings.append(
                    f"画框{index}距最近后场{distance:.2f}m＞0.10m")

    if len(frames) == 2:
        first_long, first_side = _edge_groups(frames[0])
        second_long, second_side = _edge_groups(frames[1])
        side_aligned = _projected_edges_align(first_side, second_side)
        long_aligned = _projected_edges_align(first_long, second_long)
        details.append(
            f"双画框侧边投影{'对齐' if side_aligned else '未对齐'}、"
            f"长边投影{'对齐' if long_aligned else '未对齐'}")
        if not side_aligned and not long_aligned:
            warnings.append("两个画框的侧边投影和长边投影均未对齐，不对称")

    detail = f"识别到{len(frames)}个画框"
    if details:
        detail += "；" + "；".join(details)
    if warnings:
        detail += "；警告：" + "；".join(warnings)
        status, severity = STATUS_WARN, SEV_WARN
    else:
        detail += "；符合"
        status, severity = STATUS_PASS, SEV_INFO
    return Finding(
        "1", MODULE, "画框位于后场留白区域，两个画框左右对称",
        status, severity, scheme.index, detail)


def _segment_rectangle(start, end, width):
    """返回以线段为中心轴、总宽为 ``width`` 的矩形。"""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= gu.EPS or width <= gu.EPS:
        return []
    normal = (-dy / length, dx / length)
    half_width = width / 2.0
    offset = (normal[0] * half_width, normal[1] * half_width)
    return [
        (start[0] + offset[0], start[1] + offset[1]),
        (end[0] + offset[0], end[1] + offset[1]),
        (end[0] - offset[0], end[1] - offset[1]),
        (start[0] - offset[0], start[1] - offset[1]),
    ]


def _rule_2(ctx, scheme):
    """模块规则2：柱体朝主入口方向的近柱区域须有其它道具填补。"""
    columns = [column for column in ctx.columns if len(column) >= 3]
    if not columns:
        return Finding(
            "2", MODULE, "包柱朝主客流方向近柱区域有其它道具填补",
            STATUS_NOT_RELEVANT, SEV_INFO, scheme.index,
            "未识别到柱子，可选规则不涉及")

    entrance = L.main_entrance(ctx)
    if entrance is None:
        return Finding(
            "2", MODULE, "包柱朝主客流方向近柱区域有其它道具填补",
            STATUS_WARN, SEV_WARN, scheme.index,
            "识别到柱子，但JSON未提供有效crowdDensity，无法确定主客流入口")

    door_center = gu.polygon_centroid(entrance.polygon)
    fillers = [item for item in scheme.furniture if item.corners]
    warnings = []
    details = []
    for column_index, column in enumerate(columns, 1):
        column_center = gu.polygon_centroid(column)
        radius = max(
            (gu.dist(column_center, point) for point in column),
            default=0.0)
        full_region = _segment_rectangle(column_center, door_center, radius)
        direction = (door_center[0] - column_center[0],
                     door_center[1] - column_center[1])
        direction_length = math.hypot(*direction)
        if not full_region or direction_length <= gu.EPS:
            warnings.append(
                f"柱{column_index}无法生成柱心至主入口检测区域")
            continue

        unit = (direction[0] / direction_length,
                direction[1] / direction_length)
        near_end = (column_center[0] + unit[0] * radius,
                    column_center[1] + unit[1] * radius)
        near_region = _segment_rectangle(column_center, near_end, radius)

        covered = [
            item for item in fillers
            if L.polygons_intersect(full_region, item.corners)
            and L.polygons_intersect(near_region, item.corners)
        ]
        line_length = gu.dist(column_center, door_center)
        details.append(
            f"柱{column_index}至主入口{line_length:.2f}m，"
            f"近柱检测区{radius:.2f}m×{radius:.2f}m，覆盖"
            + ("、".join(item.name for item in covered)
               if covered else "无"))
        if not covered:
            warnings.append(
                f"柱{column_index}朝主客流方向一个柱半径范围内没有其它道具")

    detail = f"识别到{len(columns)}根柱子"
    if details:
        detail += "；" + "；".join(details)
    if warnings:
        detail += "；警告：" + "；".join(warnings)
        status, severity = STATUS_WARN, SEV_WARN
    else:
        detail += "；各柱朝主客流方向均有设计填补"
        status, severity = STATUS_PASS, SEV_INFO
    return Finding(
        "2", MODULE, "包柱朝主客流方向近柱区域有其它道具填补",
        status, severity, scheme.index, detail)


def check(ctx, schemes):
    findings = []
    for scheme in schemes:
        findings.extend((_rule_1(ctx, scheme), _rule_2(ctx, scheme)))
    return findings
