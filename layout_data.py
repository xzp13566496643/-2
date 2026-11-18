"""读取荣耀 5.0 server_layout_result JSON 并构建统一检测上下文。"""

import json
import math
from dataclasses import dataclass, field

import geometry_utils as gu
from model_specs import lookup

SALES_ROOM_TYPES = frozenset({"businessRoom", "vipRoom"})


@dataclass
class Opening:
    """门、窗、玻璃墙和玻璃门等 CAD 开口。"""
    kind: str
    polygon: list
    raw: dict = field(default_factory=dict)
    wall_edge: list | None = None


@dataclass
class FireHydrant:
    """消防栓柜体及与其配对的暗门。"""
    cabinet: list
    door: list = field(default_factory=list)
    angle: float = 0.0
    raw: dict = field(default_factory=dict)

    def _triangle(self):
        points = []
        for point in self.door:
            if not points or gu.dist(point, points[-1]) > 1e-6:
                points.append(point)
        if len(points) >= 2 and gu.dist(points[0], points[-1]) <= 1e-6:
            points.pop()
        return points if len(points) >= 3 else []

    @staticmethod
    def _hinge_index(triangle):
        opposite = [gu.dist(triangle[1], triangle[2]),
                    gu.dist(triangle[0], triangle[2]),
                    gu.dist(triangle[0], triangle[1])]
        return opposite.index(max(opposite))

    @property
    def open_angle(self):
        triangle = self._triangle()
        if not triangle:
            return None
        index = self._hinge_index(triangle)
        hinge = triangle[index]
        others = [triangle[i] for i in range(3) if i != index]
        first = (others[0][0] - hinge[0], others[0][1] - hinge[1])
        second = (others[1][0] - hinge[0], others[1][1] - hinge[1])
        denominator = math.hypot(*first) * math.hypot(*second)
        if denominator <= gu.EPS:
            return None
        cosine = max(-1.0, min(1.0,
            (first[0] * second[0] + first[1] * second[1]) / denominator))
        return math.degrees(math.acos(cosine))

    @property
    def front_dir(self):
        triangle = self._triangle()
        if not triangle or len(self.cabinet) < 3:
            return None
        index = self._hinge_index(triangle)
        hinge = triangle[index]
        others = [triangle[i] for i in range(3) if i != index]
        cabinet_center = gu.polygon_centroid(self.cabinet)
        target = max(others, key=lambda point: gu.dist(point, cabinet_center))
        dx, dy = target[0] - hinge[0], target[1] - hinge[1]
        length = math.hypot(dx, dy)
        return (dx / length, dy / length) if length > gu.EPS else None

    @property
    def front_edge(self):
        direction = self.front_dir
        if direction is None or len(self.cabinet) < 2:
            return None
        signed_area = sum(
            self.cabinet[i][0] * self.cabinet[(i + 1) % len(self.cabinet)][1]
            - self.cabinet[(i + 1) % len(self.cabinet)][0] * self.cabinet[i][1]
            for i in range(len(self.cabinet))) / 2.0
        counterclockwise = signed_area > 0
        best = None
        for start, end in gu.polygon_edges(self.cabinet):
            ex, ey = end[0] - start[0], end[1] - start[1]
            nx, ny = ((ey, -ex) if counterclockwise else (-ey, ex))
            length = math.hypot(nx, ny)
            if length <= gu.EPS:
                continue
            score = nx / length * direction[0] + ny / length * direction[1]
            if best is None or score > best[0]:
                best = score, start, end
        return (best[1], best[2]) if best else None


@dataclass
class Furniture:
    name: str
    category: str
    length: float
    width: float
    height: float
    angle: float
    cx: float
    cy: float
    corners: list
    room_type: str
    raw: dict
    model: str = ""

    @property
    def center(self):
        return self.cx, self.cy

    @property
    def is_long_edge_horizontal(self):
        angle = self.angle % 180
        return angle < 45 or angle > 135


@dataclass
class Niche:
    """布局协议 niches 数组中的墙面凹龛。"""
    id: int
    polygon: list
    cavity: list | None = None
    back_edge: list | None = None
    depth: float | None = None
    opening_len: float | None = None
    item_name: str = "wall"
    library_name: str = ""
    material: dict = field(default_factory=dict)
    room_type: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def has_cavity(self):
        return self.cavity is not None

    @property
    def center(self):
        return gu.polygon_centroid(self.cavity if self.cavity else self.polygon)


@dataclass
class Room:
    room_type: str
    polygon: list
    key_objects: list = field(default_factory=list)
    niches: list = field(default_factory=list)
    furniture: list = field(default_factory=list)
    doors: list = field(default_factory=list)
    key_attributes: dict = field(default_factory=dict)


@dataclass
class Scheme:
    index: int
    rooms: list = field(default_factory=list)
    walls: list = field(default_factory=list)

    @property
    def furniture(self):
        return [item for room in self.rooms for item in room.furniture]

    @property
    def niches(self):
        return [item for room in self.rooms for item in room.niches]

    def by_category(self, category):
        return [item for item in self.furniture if item.category == category]

    def count(self, category):
        return len(self.by_category(category))


@dataclass
class LayoutContext:
    source_path: str
    raw: dict
    brand: str
    brand_type: str
    model_library: str
    store_type: str
    boundary: list
    cad_objects: list
    schemes: list
    client: dict = field(default_factory=dict)
    server: dict = field(default_factory=dict)
    properties: dict = field(default_factory=dict)
    prerequisites: dict = field(default_factory=dict)
    boundary_bbox: tuple | None = None
    walls: list = field(default_factory=list)
    columns: list = field(default_factory=list)
    openings: list = field(default_factory=list)
    fire_hydrants: list = field(default_factory=list)
    rooms_client: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    server_path: str = ""
    unknown_models: list = field(default_factory=list)


def _properties(data):
    props = data.get("properties") or [{}]
    return props[0] if isinstance(props, list) and props else {}


def _store_type(brand_type):
    return "experience" if not str(brand_type or "").strip() else "authorized"


def _parse_prerequisites(items):
    return {
        item["category"]: item.get("data")
        for item in items or []
        if isinstance(item, dict) and "category" in item
    }


def _door_wall_edge(polygon):
    if len(polygon) >= 3 and gu.dist(polygon[0], polygon[1]) > gu.EPS:
        return [polygon[0], polygon[1]]
    return None


def make_niche(raw, room_type=""):
    """将 niches 原始对象映射为旧版兼容的 Niche。

    凹腔的派生几何暂不猜测；原始多边形、材质、型号和房间归属完整保留。
    """
    return Niche(
        id=raw.get("id", 0),
        polygon=gu.parse_coords(raw.get("data", [])),
        item_name=raw.get("itemName", "wall"),
        library_name=raw.get("libraryName", ""),
        material=raw.get("material") or {},
        room_type=room_type,
        raw=raw,
    )


def _cad_geometry(cad):
    boundary, walls, columns, openings, hydrants = [], [], [], [], []
    if not isinstance(cad, list) or len(cad) < 2:
        return boundary, walls, columns, openings, hydrants
    if isinstance(cad[0], dict):
        boundary = gu.parse_coords(cad[0].get("data", []))

    cad_objects = ((cad[1] or {}).get("keyObjects") or []
                   if isinstance(cad[1], dict) else [])
    cabinets, hydrant_doors = [], []
    for raw in cad_objects:
        if not isinstance(raw, dict):
            continue
        name, data = raw.get("itemName"), raw.get("data", [])
        if name == "wall":
            walls.append(gu.parse_coords(data))
        elif name == "column":
            columns.append(gu.parse_coords(data, skip_first=True))
        elif name in {"door", "openedDoor", "window", "glassDoor"}:
            polygon = gu.parse_coords(data, skip_first=True)
            openings.append(Opening(
                kind="door" if name == "openedDoor" else name,
                polygon=polygon, raw=raw, wall_edge=_door_wall_edge(polygon)))
        elif name == "glassWall":
            openings.append(Opening(
                kind="glassWall", polygon=gu.parse_coords(data), raw=raw))
        elif name == "fireHydrant":
            angle = float(data[0]) if data else 0.0
            cabinets.append((gu.parse_coords(data, skip_first=True), raw, angle))
        elif name == "fireHydrantDoor":
            hydrant_doors.append(gu.parse_coords(data, skip_first=True))

    used = set()
    for cabinet, raw, angle in cabinets:
        center = gu.polygon_centroid(cabinet) if cabinet else None
        candidates = [
            (gu.dist(center, gu.polygon_centroid(door)), index, door)
            for index, door in enumerate(hydrant_doors)
            if index not in used and door and center is not None
        ]
        door = []
        if candidates:
            _distance, index, door = min(candidates, key=lambda item: item[0])
            used.add(index)
        hydrants.append(FireHydrant(
            cabinet=cabinet, door=door, angle=angle, raw=raw))
    return boundary, walls, columns, openings, hydrants


def _make_furniture(obj, room_type, unknown_models):
    name = obj.get("itemName", "")
    values = obj.get("data") or []
    if len(values) < 3:
        return None
    spec = lookup(name)
    if spec is None:
        unknown_models.add(name)
        category, length, width, height = "unknown", 0.0, 0.0, 0.0
    else:
        category, length, width, height = spec
    angle = float(values[0])
    cx, cy = float(values[1]) / 1000.0, float(values[2]) / 1000.0
    corners = gu.rotated_rect(cx, cy, length, width, angle) if length and width else []
    return Furniture(
        name=name, category=category, length=length, width=width, height=height,
        angle=angle, cx=cx, cy=cy, corners=corners, room_type=room_type, raw=obj,
        model=name,
    )


def _make_scheme(index, layout, unknown_models):
    scheme = Scheme(index=index)
    if not isinstance(layout, list):
        return scheme
    for entry in layout:
        if not isinstance(entry, dict) or entry.get("itemName") != "basicStuff":
            continue
        for raw in entry.get("keyObjects") or []:
            if raw.get("itemName") == "wall":
                scheme.walls.append(gu.parse_coords(raw.get("data", [])))
    for raw_room in layout:
        if not isinstance(raw_room, dict) or "roomType" not in raw_room:
            continue
        key_attributes = {
            item.get("itemName"): item.get("data")
            for item in raw_room.get("keyAttributes") or []
            if isinstance(item, dict) and item.get("itemName")
        }
        room = Room(
            room_type=raw_room.get("roomType", ""),
            polygon=gu.parse_coords(raw_room.get("data", [])),
            key_objects=raw_room.get("keyObjects") or [],
            key_attributes=key_attributes,
        )
        for raw in room.key_objects:
            if raw.get("itemName") == "door":
                polygon = gu.parse_coords(raw.get("data", []), skip_first=True)
                room.doors.append(Opening(
                    kind="door", polygon=polygon, raw=raw,
                    wall_edge=_door_wall_edge(polygon)))
        for raw in raw_room.get("niches") or []:
            if isinstance(raw, dict) and isinstance(raw.get("data"), list):
                room.niches.append(make_niche(raw, room.room_type))
        for obj in raw_room.get("layout_objects") or []:
            if not isinstance(obj, dict):
                continue
            item = _make_furniture(obj, room.room_type, unknown_models)
            if item is not None:
                room.furniture.append(item)
        scheme.rooms.append(room)
    return scheme


def _parse_partition_rooms(data):
    rooms = []
    partitions = data.get("partitions") or []
    raw_rooms = partitions[0] if partitions and isinstance(partitions[0], list) else []
    for raw in raw_rooms:
        if not isinstance(raw, dict):
            continue
        room = Room(
            room_type=raw.get("itemName", ""),
            polygon=gu.parse_coords(raw.get("data", [])),
            key_objects=raw.get("keyObjects") or [],
        )
        for opening in room.key_objects:
            if opening.get("itemName") == "door":
                polygon = gu.parse_coords(opening.get("data", []), skip_first=True)
                room.doors.append(Opening(
                    kind="door", polygon=polygon, raw=opening,
                    wall_edge=_door_wall_edge(polygon)))
        rooms.append(room)
    return rooms


def load(path):
    with open(path, "r", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须是对象")
    if not isinstance(data.get("CAD"), list) or len(data["CAD"]) < 2:
        raise ValueError("缺少有效的 CAD 段")
    if not isinstance(data.get("layouts"), list) or not data["layouts"]:
        raise ValueError("缺少 layouts，或 layouts 中没有候选方案")

    props = _properties(data)
    model_libraries = props.get("modelLibraries") or []
    boundary, walls, columns, openings, fire_hydrants = _cad_geometry(data["CAD"])
    cad_objects = (data["CAD"][1] or {}).get("keyObjects") or []
    unknown_models = set()
    schemes = [
        _make_scheme(index, layout, unknown_models)
        for index, layout in enumerate(data["layouts"])
    ]
    return LayoutContext(
        source_path=path,
        raw=data,
        brand=str(props.get("brandName") or ""),
        brand_type=str(props.get("brandType") or ""),
        model_library=str(model_libraries[0]) if model_libraries else "",
        store_type=_store_type(props.get("brandType")),
        boundary=boundary,
        cad_objects=cad_objects,
        schemes=schemes,
        client=data,
        server=data,
        properties=props,
        prerequisites=_parse_prerequisites(data.get("prerequisites")),
        boundary_bbox=gu.bbox(boundary),
        walls=walls,
        columns=columns,
        openings=openings,
        fire_hydrants=fire_hydrants,
        rooms_client=_parse_partition_rooms(data),
        notes=[],
        server_path=path,
        unknown_models=sorted(unknown_models),
    )


def doors(ctx):
    return [opening for opening in ctx.openings if opening.kind == "door"]


def glass_walls(ctx):
    return [opening for opening in ctx.openings if opening.kind == "glassWall"]


def glass_doors(ctx):
    return [opening for opening in ctx.openings if opening.kind == "glassDoor"]


def entrances(ctx, require_crowd_density=False):
    """返回可作为客流入口的门对象。

    ``require_crowd_density=True`` 时只保留JSON中明确提供
    ``crowdDensity`` 的入口。
    """
    kinds = {"glassDoor", "openedDoor", "safetyDoor"}
    result = [opening for opening in ctx.openings
              if opening.kind in kinds and len(opening.polygon) >= 2]
    if require_crowd_density:
        result = [opening for opening in result
                  if "crowdDensity" in opening.raw]
    return result


def backstage_polygons(ctx, scheme=None):
    """返回后场房间分区多边形，完整迁移旧版统一口径。

    ``businessRoom``/``vipRoom`` 为售卖区；除此之外具有有效多边形的
    房间分区均为后场。优先使用当前方案的房间，未传方案时使用客户端
    分区；不把墙体或未命名的几何差集当作后场。
    """
    rooms = scheme.rooms if scheme is not None else ctx.rooms_client
    return [
        room.polygon for room in rooms
        if room.room_type not in SALES_ROOM_TYPES and len(room.polygon) >= 3
    ]


def main_entrance(ctx):
    """返回 ``crowdDensity`` 最大的主入口，无人流量数据时返回 ``None``。"""
    candidates = entrances(ctx, require_crowd_density=True)
    scored = []
    for opening in candidates:
        try:
            crowd = float(opening.raw["crowdDensity"])
        except (TypeError, ValueError):
            continue
        scored.append((crowd, opening))
    return max(scored, key=lambda value: value[0])[1] if scored else None


def furniture_edges(furniture):
    return gu.polygon_edges(furniture.corners)


def furniture_to_polygon_distance(furniture, polygon):
    return min(
        (gu.segments_distance(a, b, c, d)
         for a, b in furniture_edges(furniture)
         for c, d in gu.polygon_edges(polygon)),
        default=float("inf"),
    )


def furniture_to_point_distance(furniture, point):
    return min(
        (gu.point_segment_distance(point, start, end)
         for start, end in furniture_edges(furniture)),
        default=float("inf"),
    )


def polygons_intersect(first, second):
    for a, b in gu.polygon_edges(first):
        for c, d in gu.polygon_edges(second):
            if gu.segments_intersect(a, b, c, d):
                return True
    return bool((first and gu.point_in_polygon(first[0], second))
                or (second and gu.point_in_polygon(second[0], first)))


def nearest_wall_distance(ctx, furniture):
    return min(
        (furniture_to_polygon_distance(furniture, wall) for wall in ctx.walls),
        default=float("inf"),
    )


def nearest_column_distance(ctx, furniture):
    return min(
        (furniture_to_polygon_distance(furniture, column) for column in ctx.columns),
        default=float("inf"),
    )


def nearest_opening_distance(ctx, furniture, kind):
    return min(
        (furniture_to_polygon_distance(furniture, opening.polygon)
         for opening in ctx.openings if opening.kind == kind),
        default=float("inf"),
    )


def furniture_blocks_opening(ctx, furniture, kind="door"):
    return any(
        opening.kind == kind
        and polygons_intersect(furniture.corners, opening.polygon)
        for opening in ctx.openings
    )


def furniture_on_glasswall(ctx, furniture, tol=0.05):
    return any(
        opening.kind == "glassWall"
        and (polygons_intersect(furniture.corners, opening.polygon)
             or furniture_to_polygon_distance(furniture, opening.polygon) < tol)
        for opening in ctx.openings
    )


def is_against_wall(ctx, furniture, tol=0.15):
    return nearest_wall_distance(ctx, furniture) <= tol


def is_against_business_room_wall(ctx, furniture, tol=0.15):
    sales_rooms = [
        room for scheme in ctx.schemes for room in scheme.rooms
        if room.room_type in {"businessRoom", "vipRoom"}
    ]
    distance = min(
        (furniture_to_polygon_distance(furniture, room.polygon)
         for room in sales_rooms),
        default=float("inf"),
    )
    return distance <= tol if sales_rooms else is_against_wall(ctx, furniture, tol)


def furniture_distance(first, second):
    return min(
        (gu.segments_distance(a, b, c, d)
         for a, b in furniture_edges(first)
         for c, d in furniture_edges(second)),
        default=float("inf"),
    )


def point_in_furniture_local(furniture, point):
    radians = math.radians(furniture.angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    dx, dy = point[0] - furniture.cx, point[1] - furniture.cy
    return dx * cosine + dy * sine, -dx * sine + dy * cosine


def classify_point_edge(local_long, local_short, length, width, tol=0.05):
    half_length, half_width = length / 2, width / 2
    long_value, short_value = abs(local_long), abs(local_short)
    if long_value <= half_length + tol and short_value <= half_width + tol:
        return "inside", 0.0
    if long_value <= half_length + tol:
        return "long", short_value - half_width
    if short_value <= half_width + tol:
        return "short", long_value - half_length
    return "corner", math.hypot(
        long_value - half_length, short_value - half_width)
