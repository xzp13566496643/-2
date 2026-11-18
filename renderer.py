"""门店、房间和道具的基础平面图。"""

import re

import geometry_utils as gu
import annotation_utils as au
from findings import STATUS_FAIL

ROOM_COLORS = {"businessRoom": "#D3D3D3", "powerRoom": "#ADD8E6"}
CATEGORY_COLORS = {
    "experience_table": "#F7D774", "service_desk": "#E5B95C",
    "theme_cabinet": "#E77FA4", "imaging_cabinet": "#D9689A",
    "cash_desk": "#9B8178", "authorization_sign": "#D71313",
    "lightbox_cabinet": "#C45AA0", "light_box": "#9C27B0",
    "background_lightbox_cabinet": "#6A1B9A",
    "unknown": "#9E9E9E",
}


def _compact_failure_reason(finding, max_chars=46):
    """提取适合图纸右栏显示的简短不符合原因。

    JSON/Excel仍保留完整详情；这里只去掉检测过程、全部测量和重复的规则
    标题，并限制每项长度，避免右栏把平面图区域挤窄。
    """
    detail = re.sub(r"\s+", " ", (finding.detail or "").strip())
    if not detail:
        reason = finding.title
    elif "不符合：" in detail:
        reason = detail.split("不符合：", 1)[1]
    elif "缺失品类：" in detail:
        reason = "缺失品类：" + detail.split("缺失品类：", 1)[1]
    else:
        reason = detail

    # “全部测量/全部连线”等内容是复核数据，不在图纸摘要中重复展示。
    reason = re.split(r"[。；]全部(?:测量|连线|结果|数据)", reason, 1)[0]
    reason = reason.replace("不符合：", "")
    reason = reason.strip(" ；。")
    parts = [part.strip() for part in reason.split("；") if part.strip()]
    if len(parts) > 1:
        reason = parts[0] + "等"
    if len(reason) > max_chars:
        reason = reason[:max_chars - 1].rstrip(" ；，") + "…"
    return reason


def _add_polygon(ax, points, **kwargs):
    from matplotlib.patches import Polygon
    if len(points) >= 3:
        ax.add_patch(Polygon(points, closed=True, **kwargs))


def render(ctx, scheme, path, report=None):
    import matplotlib
    import plot_font
    plot_font.configure(matplotlib)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(18, 14))
    for room in scheme.rooms:
        _add_polygon(ax, room.polygon, facecolor=ROOM_COLORS.get(room.room_type, "#EEEEEE"),
                     edgecolor="none", alpha=0.35, label=room.room_type)
    if ctx.boundary:
        xs = [p[0] for p in ctx.boundary] + [ctx.boundary[0][0]]
        ys = [p[1] for p in ctx.boundary] + [ctx.boundary[0][1]]
        ax.plot(xs, ys, color="#222222", linewidth=2, label="boundary")

    for obj in ctx.cad_objects:
        name = obj.get("itemName", "")
        skip = name in {"column", "door", "glassDoor", "openedDoor", "window"}
        points = gu.parse_coords(obj.get("data", []), skip_first=skip)
        if name == "wall":
            _add_polygon(ax, points, facecolor="#E8E8E8", edgecolor="#333333", alpha=0.75)
        elif name == "column":
            _add_polygon(ax, points, facecolor="#8B4513", edgecolor="#8B4513", alpha=0.6)
        elif points:
            xs, ys = zip(*points)
            color = "#228B22" if "Door" in name or name == "door" else "#4682B4"
            ax.plot(xs, ys, color=color, linestyle="--", linewidth=1.5, label=name)

    failed_rules = []
    if report is not None:
        failed_rules = [item for item in report.findings
                        if item.scheme in (scheme.index, -1)
                        and item.status == STATUS_FAIL]
    for item in scheme.furniture:
        color = CATEGORY_COLORS.get(item.category, "#9E9E9E")
        if item.corners:
            _add_polygon(ax, item.corners, facecolor=color, edgecolor="#333333",
                         alpha=0.65, label=item.category)
        else:
            ax.plot(item.cx, item.cy, "o", color=color)
        ax.annotate(item.name, (item.cx, item.cy), ha="center", va="center", fontsize=7)

    # 独立标注层：体验台和开机服务台共同组成桌类区域；每个其它道具
    # 仅标一条到该区域中最近桌类实体的最小平行间距。
    au.draw_experience_region_spacing(fig, ax, scheme)

    # 总体规则18（体验台模块内规则3）专用标注层。
    if any(item.rule_id == "18" for item in failed_rules):
        au.draw_rule17_violations(fig, ax, scheme)

    # 规则21专用标注层：仅标出不满足出入口净距的尺寸。
    if any(item.rule_id == "22" for item in failed_rules):
        au.draw_rule21_violations(fig, ax, ctx, scheme)

    ax.set_aspect("equal")
    ax.grid(True, linestyle="--", alpha=0.25)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(f"荣耀 5.0 门店布局 - 方案 {scheme.index + 1}")
    handles, labels = ax.get_legend_handles_labels()
    unique = {}
    for handle, label in zip(handles, labels):
        unique.setdefault(label, handle)
    if unique:
        ax.legend(unique.values(), unique.keys(), loc="upper left", bbox_to_anchor=(1.01, 1))

    if failed_rules:
        import textwrap
        lines = [f"不符合项（{len(failed_rules)}）"]
        for finding in failed_rules:
            reason = _compact_failure_reason(finding)
            wrapped = textwrap.wrap(
                f"{finding.rule_id}.不符合：{reason}", width=26,
                break_long_words=True, break_on_hyphens=False,
            )
            lines.extend(wrapped[:2])
        ax.text(1.01, 0.53, "\n".join(lines), transform=ax.transAxes,
                ha="left", va="top", fontsize=8, color="#9C0006",
                bbox=dict(boxstyle="round,pad=0.6", facecolor="#FFF5F5",
                          edgecolor="#D71313", alpha=0.95), zorder=10)


    plt.tight_layout()
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()
