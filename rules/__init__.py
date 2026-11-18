"""荣耀体验店的 9 个规则模块，按报告展示顺序注册。"""

from . import prerequisites
from . import general
from . import experience_table
from . import service_desk
from . import accessory_cabinet
from . import light_box
from . import picture_frame
from . import other_props
from . import prohibited

CHECKERS = [
    prerequisites, general, experience_table, service_desk,
    accessory_cabinet, light_box, picture_frame, other_props, prohibited,
]
