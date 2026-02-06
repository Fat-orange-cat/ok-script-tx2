"""
游戏基础任务类 - 提供3D MMORPG游戏的通用功能
"""
import re
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Tuple, List

from ok import BaseTask
from src.tasks.MyBaseTask import MyBaseTask


class GameState(Enum):
    """游戏状态枚举"""
    IDLE = "idle"           # 空闲
    MOVING = "moving"       # 移动中
    IN_COMBAT = "combat"    # 战斗中
    GATHERING = "gathering" # 采集中
    QUESTING = "questing"   # 任务中
    DEAD = "dead"           # 死亡
    INVENTORY_FULL = "full" # 背包满


class BaseGameTask(MyBaseTask, ABC):
    """
    游戏基础任务类
    提供3D MMORPG游戏的通用功能：
    - 移动控制
    - 状态检测
    - 小地图导航
    - 战斗检测
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 游戏窗口坐标区域配置
        self.quest_list_area = {
            'x_start': 0.80,  # 右侧任务列表起始X
            'x_end': 0.98,    # 右侧任务列表结束X
            'y_start': 0.10,  # 右侧任务列表起始Y
            'y_end': 0.90     # 右侧任务列表结束Y
        }

        self.minimap_area = {
            'x_start': 0.82,  # 右上角小地图起始X
            'x_end': 0.98,    # 右上角小地图结束X
            'y_start': 0.02,  # 右上角小地图起始Y
            'y_end': 0.18     # 右上角小地图结束Y
        }

        # 角色位置（角色在屏幕中心）
        self.character_center = (0.5, 0.5)

        # 当前游戏状态
        self.current_state = GameState.IDLE

    # ==================== 移动控制 ====================

    def move_forward(self, duration: float = 1.0):
        """向前移动"""
        self.operate(lambda: self.do_move_forward(duration))

    def do_move_forward(self, duration: float):
        """执行向前移动"""
        self.do_send_key_down('w')
        self.sleep(0.1)
        self.do_mouse_down(key='right')  # 按住右键控制视角
        self.sleep(duration)
        self.do_mouse_up(key='right')
        self.do_send_key_up('w')

    def move_backward(self, duration: float = 1.0):
        """向后移动"""
        self.operate(lambda: self.do_move_backward(duration))

    def do_move_backward(self, duration: float):
        """执行向后移动"""
        self.do_send_key_down('s')
        self.sleep(duration)
        self.do_send_key_up('s')

    def move_left(self, duration: float = 1.0):
        """向左移动"""
        self.operate(lambda: self.do_move_left(duration))

    def do_move_left(self, duration: float):
        """执行向左移动"""
        self.do_send_key_down('a')
        self.sleep(duration)
        self.do_send_key_up('a')

    def move_right(self, duration: float = 1.0):
        """向右移动"""
        self.operate(lambda: self.do_move_right(duration))

    def do_move_right(self, duration: float):
        """执行向右移动"""
        self.do_send_key_down('d')
        self.sleep(duration)
        self.do_send_key_up('d')

    def stop_movement(self):
        """停止所有移动"""
        self.operate(lambda: self.do_stop_movement())

    def do_stop_movement(self):
        """执行停止移动"""
        for key in ['w', 'a', 's', 'd']:
            self.do_send_key_up(key)

    def jump(self):
        """跳跃"""
        self.operate(lambda: self.send_key('space'))

    # ==================== 视角控制 ====================

    def adjust_camera(self, angle: float):
        """
        调整摄像机视角
        :param angle: 角度（正数向右，负数向左）
        """
        self.operate(lambda: self.do_adjust_camera(angle))

    def do_adjust_camera(self, angle: float):
        """执行视角调整"""
        # 移动鼠标来调整视角
        pixels = int(angle * 10)  # 角度转换成像素
        self.executor.interaction.do_mouse_move(x=pixels, y=0)

    # ==================== 战斗检测 ====================

    def is_in_combat(self) -> bool:
        """
        检测是否进入战斗状态
        可以通过检测血条、战斗UI、怒气条等判断
        """
        # 方式1: 检测血条出现
        if self.check_exists('combat_hp_bar', threshold=0.7):
            return True

        # 方式2: OCR检测"战斗中"文字
        # if self.ocr(match=re.compile(r'战斗|combat'), log=False):
        #     return True

        return False

    def check_hp_low(self, threshold_percent: float = 30.0) -> bool:
        """
        检测血量是否低于阈值
        :param threshold_percent: 血量百分比阈值
        """
        # TODO: 实现血量检测逻辑
        # 可以通过识别血条的长度比例来判断
        return False

    def check_mp_low(self, threshold_percent: float = 20.0) -> bool:
        """
        检测蓝量是否低于阈值
        :param threshold_percent: 蓝量百分比阈值
        """
        # TODO: 实现蓝量检测逻辑
        return False

    # ==================== 小地图导航 ====================

    def get_minimap_center(self) -> Tuple[float, float]:
        """获取小地图中心点"""
        x = (self.minimap_area['x_start'] + self.minimap_area['x_end']) / 2
        y = (self.minimap_area['y_start'] + self.minimap_area['y_end']) / 2
        return x, y

    def check_target_on_minimap(self, target_name: str) -> Optional[Tuple[float, float]]:
        """
        在小地图上检测目标标记
        :param target_name: 目标名称（对应assets中的图片标记）
        :return: 返回目标在小地图上的相对位置，如果未找到返回None
        """
        # 在小地图区域内查找目标标记
        result = self.find_one(
            target_name,
            box={
                'x_start': self.minimap_area['x_start'],
                'x_end': self.minimap_area['x_end'],
                'y_start': self.minimap_area['y_start'],
                'y_end': self.minimap_area['y_end']
            }
        )
        return result

    def navigate_to_minimap_target(self, target_name: str) -> bool:
        """
        根据小地图上的目标标记进行导航
        :param target_name: 目标标记名称
        :return: 是否成功找到并开始导航
        """
        target_pos = self.check_target_on_minimap(target_name)
        if not target_pos:
            self.log_warn(f"小地图上未找到目标: {target_name}")
            return False

        # 计算目标相对于小地图中心的方向
        minimap_center = self.get_minimap_center()
        dx = target_pos[0] - minimap_center[0]
        dy = target_pos[1] - minimap_center[1]

        # 调整视角朝向目标
        if abs(dx) > 0.02:  # 如果偏移量足够大
            # 调整摄像机
            if dx > 0:
                self.adjust_camera(15)  # 向右转
            else:
                self.adjust_camera(-15)  # 向左转
            self.sleep(0.3)

        # 向前移动
        self.log_info(f"向目标导航: {target_name}")
        self.move_forward(duration=2.0)

        return True

    # ==================== 任务列表交互 ====================

    def click_quest_track(self, quest_index: int = 0):
        """
        点击任务追踪
        :param quest_index: 任务索引（0为第一个任务）
        """
        # 计算任务在任务列表中的位置
        quest_y = self.quest_list_area['y_start'] + (quest_index * 0.08)
        quest_x = (self.quest_list_area['x_start'] + self.quest_list_area['x_end']) / 2

        self.click(quest_x, quest_y)
        self.log_info(f"点击任务追踪: 索引{quest_index}")
        self.sleep(0.5)

    def find_quest_in_list(self, quest_name: str) -> bool:
        """
        在任务列表中查找指定任务
        :param quest_name: 任务名称（支持OCR）
        :return: 是否找到任务
        """
        # 在任务列表区域使用OCR查找任务名称
        result = self.ocr(
            box={
                'x_start': self.quest_list_area['x_start'],
                'x_end': self.quest_list_area['x_end'],
                'y_start': self.quest_list_area['y_start'],
                'y_end': self.quest_list_area['y_end']
            },
            match=re.compile(quest_name),
            log=True
        )
        return result is not None

    # ==================== 技能释放 ====================

    def cast_skill(self, skill_key: str):
        """
        释放技能
        :param skill_key: 技能按键（如 '1', '2', '3', 'q', 'e', 'r'）
        """
        self.operate(lambda: self.send_key(skill_key))
        self.log_debug(f"释放技能: {skill_key}")
        self.sleep(0.3)  # 技能后摇

    def cast_skill_sequence(self, skill_keys: List[str]):
        """
        按顺序释放技能序列
        :param skill_keys: 技能按键列表
        """
        for skill_key in skill_keys:
            self.cast_skill(skill_key)
            self.sleep(0.5)

    # ==================== 交互操作 ====================

    def interact(self):
        """交互（默认F键）"""
        self.operate(lambda: self.send_key('f'))
        self.log_debug("执行交互")
        self.sleep(0.5)

    def pick_up_item(self):
        """拾取物品"""
        self.operate(lambda: self.send_key('f'))
        self.log_debug("拾取物品")
        self.sleep(0.3)

    # ==================== 状态检测 ====================

    def check_game_state(self) -> GameState:
        """
        检测当前游戏状态
        :return: 游戏状态
        """
        # 优先级检测：死亡 > 战斗 > 其他
        if self.check_exists('dead_indicator', threshold=0.8):
            self.current_state = GameState.DEAD
        elif self.is_in_combat():
            self.current_state = GameState.IN_COMBAT
        else:
            self.current_state = GameState.IDLE

        return self.current_state

    def wait_until_out_of_combat(self, timeout: float = 30.0) -> bool:
        """
        等待脱离战斗状态
        :param timeout: 超时时间（秒）
        :return: 是否成功脱离战斗
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self.is_in_combat():
                return True
            self.sleep(1)
        return False

    # ==================== 抽象方法 ====================

    @abstractmethod
    def run(self):
        """任务执行入口 - 子类必须实现"""
        pass
