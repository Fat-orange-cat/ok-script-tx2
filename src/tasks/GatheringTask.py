"""
采集任务模块 - 自动采集资源
"""
import re
from typing import List, Dict, Optional
from dataclasses import dataclass

from qfluentwidgets import FluentIcon

from src.tasks.BaseGameTask import BaseGameTask, GameState
from src.tasks.QuestManager import QuestManager, QuestConfig, QuestTask, TaskType, QuestStatus


@dataclass
class GatheringResource:
    """采集资源配置"""
    resource_id: str              # 资源ID（对应图片模板名称）
    resource_name: str            # 资源名称
    minimap_marker: str           # 小地图标记名称
    gather_count: int = 1         # 采集数量
    gather_key: str = 'f'         # 采集按键
    gather_duration: float = 3.0  # 单次采集耗时
    search_radius: float = 100.0  # 搜索半径（米）


class GatheringTask(BaseGameTask):
    """
    采集任务

    功能：
    1. 自动识别可采集资源
    2. 小地图导航到资源位置
    3. 自动采集
    4. 采集数量统计
    5. 支持多种资源配置
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "采集任务"
        self.description = "自动采集指定资源"
        self.group_name = "日常任务"
        self.group_icon = FluentIcon.ROBOT
        self.icon = FluentIcon.DOWNLOAD

        # 任务管理器
        self.quest_manager = QuestManager(self)

        # 默认配置
        self.default_config.update({
            '采集目标选择': '所有',
            '采集循环执行': False,
            '采集循环间隔(秒)': 10,
            '战斗时是否反击': True,
            '血量低于%自动逃离': 30,
            '背包满检测': False,
            '采集优先级列表': ['矿点', '草药', '树木'],  # 优先采集的资源类型
        })

        self.config_type["采集目标选择"] = {
            'type': "drop_down",
            'options': ['所有', '仅矿点', '仅草药', '仅树木', '自定义']
        }

        # 统计信息
        self.gathering_stats = {
            'total_gathered': 0,
            'by_type': {}
        }

        # 资源配置（可以根据游戏实际情况修改）
        self.resource_configs: Dict[str, GatheringResource] = {
            '矿点': GatheringResource(
                resource_id='ore_deposit',
                resource_name='铁矿',
                minimap_marker='minimap_ore',
                gather_count=1,
                gather_key='f'
            ),
            '草药': GatheringResource(
                resource_id='herb_plant',
                resource_name='草药',
                minimap_marker='minimap_herb',
                gather_count=1,
                gather_key='f'
            ),
            '树木': GatheringResource(
                resource_id='tree',
                resource_name='树木',
                minimap_marker='minimap_tree',
                gather_count=1,
                gather_key='f'
            ),
        }

    def run(self):
        """任务执行入口"""
        self.log_info('采集任务开始', notify=True)

        # 重置统计
        self.gathering_stats = {'total_gathered': 0, 'by_type': {}}

        try:
            # 获取配置
            target_selection = self.config.get('采集目标选择', '所有')
            loop_enabled = self.config.get('采集循环执行', False)
            loop_delay = self.config.get('采集循环间隔(秒)', 10)
            fight_back = self.config.get('战斗时是否反击', True)
            hp_threshold = self.config.get('血量低于%自动逃离', 30)

            # 确定要采集的资源类型
            resource_types = self._get_resource_types(target_selection)
            if not resource_types:
                self.log_warn("没有可采集的资源类型")
                return

            # 构建任务链
            quest = self._build_gathering_quest(resource_types, loop_enabled, loop_delay)

            # 注册任务
            self.quest_manager.register_quest(quest)

            # 执行任务
            while True:
                # 检查状态
                state = self.check_game_state()
                if state == GameState.DEAD:
                    self.log_error("角色已死亡，停止采集")
                    break

                if state == GameState.IN_COMBAT:
                    if fight_back:
                        self.log_info("进入战斗，反击中...")
                        self._handle_combat(hp_threshold)
                    else:
                        self.log_warn("进入战斗，等待脱战...")
                        self.wait_until_out_of_combat()

                # 检查血量
                if self.check_hp_low(hp_threshold):
                    self.log_warn(f"血量低于{hp_threshold}%，使用血药")
                    self._use_hp_potion()

                # 执行采集
                success = self.quest_manager.execute_quest(quest.quest_id)
                if not success:
                    self.log_warn("采集任务执行失败")
                    break

                # 如果不循环，执行一次后退出
                if not loop_enabled:
                    break

                # 循环延迟
                self.log_info(f"等待 {loop_delay} 秒后继续采集")
                self.sleep(loop_delay)

            # 显示统计
            self._show_statistics()

        except Exception as e:
            self.log_error(f"采集任务异常: {e}")
            raise
        finally:
            self.log_info('采集任务结束', notify=True)

    def _get_resource_types(self, selection: str) -> List[str]:
        """根据配置获取要采集的资源类型"""
        if selection == '所有':
            return list(self.resource_configs.keys())
        elif selection == '仅矿点':
            return ['矿点']
        elif selection == '仅草药':
            return ['草药']
        elif selection == '仅树木':
            return ['树木']
        else:
            # 自定义：从配置中获取优先级列表
            return self.config.get('采集优先级列表', [])

    def _build_gathering_quest(self, resource_types: List[str],
                               loop_enabled: bool, loop_delay: float) -> QuestConfig:
        """构建采集任务链"""
        tasks = []

        for resource_type in resource_types:
            if resource_type not in self.resource_configs:
                continue

            config = self.resource_configs[resource_type]

            # 创建采集任务
            task = QuestTask(
                task_id=f"gather_{resource_type}",
                task_type=TaskType.GATHERING,
                name=f"采集{config.resource_name}",
                description=f"采集 {config.gather_count} 个 {config.resource_name}",
                priority=0,
                config={
                    'resource_name': config.resource_id,
                    'minimap_marker': config.minimap_marker,
                    'gather_count': config.gather_count,
                    'gather_key': config.gather_key,
                    'timeout': 60.0
                },
                on_complete=lambda r=resource_type: self._on_gather_complete(r)
            )

            tasks.append(task)

        # 构建任务链
        quest = QuestConfig(
            quest_id='daily_gathering',
            quest_name='日常采集',
            description='自动采集日常资源',
            enabled=True,
            loop=loop_enabled,
            loop_delay=loop_delay,
            tasks=tasks
        )

        return quest

    def _on_gather_complete(self, resource_type: str):
        """采集完成回调"""
        self.gathering_stats['total_gathered'] += 1
        if resource_type not in self.gathering_stats['by_type']:
            self.gathering_stats['by_type'][resource_type] = 0
        self.gathering_stats['by_type'][resource_type] += 1
        self.log_info(f"采集成功: {resource_type}")

    def _handle_combat(self, hp_threshold: float):
        """处理战斗"""
        # 简单的战斗逻辑
        skill_sequence = self.config.get('战斗技能顺序', '1-2-3').split('-')

        while self.is_in_combat():
            # 检查血量
            if self.check_hp_low(hp_threshold):
                self.log_warn("血量过低，逃离战斗")
                self._flee_combat()
                break

            # 释放技能
            for skill in skill_sequence:
                if self.is_in_combat():
                    self.cast_skill(skill)
                else:
                    break

            self.sleep(0.5)

    def _use_hp_potion(self):
        """使用血药"""
        # 假设血药快捷键是数字键0
        self.cast_skill('0')
        self.sleep(1)

    def _flee_combat(self):
        """逃离战斗"""
        # 停止攻击，向后逃跑
        self.stop_movement()
        self.sleep(0.3)
        self.move_backward(duration=3.0)
        self.wait_until_out_of_combat(timeout=10.0)

    def _show_statistics(self):
        """显示统计信息"""
        stats = self.gathering_stats
        self.log_info("=" * 40)
        self.log_info("采集任务统计")
        self.log_info("=" * 40)
        self.log_info(f"总采集数: {stats['total_gathered']}")
        for resource_type, count in stats['by_type'].items():
            self.log_info(f"  {resource_type}: {count}")
        self.log_info("=" * 40)

    # ==================== 辅助方法 ====================

    def find_nearest_resource(self, resource_type: str) -> Optional[tuple]:
        """
        查找最近的采集资源
        :param resource_type: 资源类型
        :return: 资源坐标 (x, y)，未找到返回None
        """
        if resource_type not in self.resource_configs:
            return None

        config = self.resource_configs[resource_type]
        return self.find_one(config.resource_id)

    def click_resource(self, resource_type: str) -> bool:
        """
        点击采集资源
        :param resource_type: 资源类型
        :return: 是否成功点击
        """
        pos = self.find_nearest_resource(resource_type)
        if pos:
            self.click(pos[0], pos[1])
            self.log_debug(f"点击采集资源: {resource_type}")
            return True
        return False

    def gather_resource(self, resource_type: str) -> bool:
        """
        执行采集动作
        :param resource_type: 资源类型
        :return: 是否成功采集
        """
        if resource_type not in self.resource_configs:
            return False

        config = self.resource_configs[resource_type]

        # 1. 查找并点击资源
        if not self.click_resource(resource_type):
            return False

        # 2. 等待到达采集位置
        self.sleep(0.5)

        # 3. 按下采集键
        self.send_key(config.gather_key)

        # 4. 等待采集完成
        self.sleep(config.gather_duration)

        # 5. 等待采集动画结束
        self.sleep(0.5)

        return True
