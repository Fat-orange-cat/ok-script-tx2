"""
游戏任务系统 - 整合采集和战斗的主任务
支持UI配置和可扩展的任务系统
"""
from typing import Dict, List, Optional
from dataclasses import dataclass

from qfluentwidgets import FluentIcon, ComboBox, PushButton, CheckBox, SpinBox, DoubleSpinBox

from src.tasks.BaseGameTask import BaseGameTask, GameState
from src.tasks.GatheringTask import GatheringTask
from src.tasks.CombatTask import CombatTask
from src.tasks.QuestManager import QuestManager, QuestConfig, QuestTask, TaskType


@dataclass
class GameTaskConfig:
    """游戏任务配置"""
    task_id: str                      # 任务ID
    task_name: str                    # 任务名称
    task_type: str                    # 任务类型：'gathering' 或 'combat'
    enabled: bool = False             # 是否启用
    priority: int = 0                 # 执行优先级
    loop: bool = False                # 是否循环
    config: Dict = None               # 任务配置参数


class GameQuestTask(BaseGameTask):
    """
    游戏主任务系统

    功能：
    1. 整合采集和战斗任务
    2. 支持UI配置任务队列
    3. 可扩展的任务类型
    4. 任务优先级管理
    5. 自动任务切换
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "游戏任务系统"
        self.description = "可扩展的自动化任务系统（采集+战斗）"
        self.group_name = "游戏任务"
        self.group_icon = FluentIcon.ROBOT
        self.icon = FluentIcon.APPLICATION

        # 任务管理器
        self.quest_manager = QuestManager(self)

        # 子任务实例
        self.gathering_task = GatheringTask(*args, **kwargs)
        self.combat_task = CombatTask(*args, **kwargs)

        # 默认配置
        self.default_config.update({
            '任务执行模式': '顺序执行',  # 顺序执行、优先级执行、循环执行
            '任务列表': [],             # 任务队列

            # 采集任务配置
            '采集任务_启用': False,
            '采集目标': '所有',
            '采集循环': False,
            '采集循环间隔': 10,

            # 战斗任务配置
            '战斗任务_启用': False,
            '战斗模式': 'auto',
            '战斗循环次数': 10,

            # 通用配置
            '血量低于%逃离': 30,
            '蓝量低于%补蓝': 20,
            '背包满自动停止': False,
            '死亡后停止任务': True,
        })

        self.config_type["任务执行模式"] = {
            'type': "drop_down",
            'options': ['顺序执行', '优先级执行', '循环执行']
        }

        self.config_type["采集目标"] = {
            'type': "drop_down",
            'options': ['所有', '仅矿点', '仅草药', '仅树木']
        }

        self.config_type["战斗模式"] = {
            'type': "drop_down",
            'options': ['auto', 'defensive', 'boss', 'farm']
        }

        # 任务统计
        self.task_stats = {
            'total_completed': 0,
            'gathering_completed': 0,
            'combat_completed': 0,
            'total_time': 0
        }

    def run(self):
        """任务执行入口"""
        self.log_info('游戏任务系统启动', notify=True)

        import time
        start_time = time.time()

        try:
            # 获取配置
            exec_mode = self.config.get('任务执行模式', '顺序执行')
            hp_threshold = self.config.get('血量低于%逃离', 30)
            mp_threshold = self.config.get('蓝量低于%补蓝', 20)
            stop_on_death = self.config.get('死亡后停止任务', True)

            # 构建任务队列
            task_queue = self._build_task_queue()

            if not task_queue:
                self.log_warn("没有启用的任务")
                return

            # 根据执行模式执行任务
            if exec_mode == '顺序执行':
                self._execute_sequential(task_queue, hp_threshold, mp_threshold, stop_on_death)
            elif exec_mode == '优先级执行':
                self._execute_by_priority(task_queue, hp_threshold, mp_threshold, stop_on_death)
            elif exec_mode == '循环执行':
                self._execute_loop(task_queue, hp_threshold, mp_threshold, stop_on_death)

            # 显示统计
            self.task_stats['total_time'] = time.time() - start_time
            self._show_statistics()

        except Exception as e:
            self.log_error(f"任务执行异常: {e}")
            raise
        finally:
            self.log_info('游戏任务系统结束', notify=True)

    def _build_task_queue(self) -> List[GameTaskConfig]:
        """构建任务队列"""
        queue = []

        # 添加采集任务
        if self.config.get('采集任务_启用', False):
            gathering_config = GameTaskConfig(
                task_id='gathering_main',
                task_name='日常采集',
                task_type='gathering',
                enabled=True,
                priority=1,
                loop=self.config.get('采集循环', False),
                config={
                    'target_selection': self.config.get('采集目标', '所有'),
                    'loop_delay': self.config.get('采集循环间隔', 10)
                }
            )
            queue.append(gathering_config)

        # 添加战斗任务
        if self.config.get('战斗任务_启用', False):
            combat_config = GameTaskConfig(
                task_id='combat_main',
                task_name='日常战斗',
                task_type='combat',
                enabled=True,
                priority=2,
                loop=False,
                config={
                    'combat_mode': self.config.get('战斗模式', 'auto'),
                    'combat_count': self.config.get('战斗循环次数', 10)
                }
            )
            queue.append(combat_config)

        # 按优先级排序
        queue.sort(key=lambda x: x.priority, reverse=True)

        return queue

    def _execute_sequential(self, task_queue: List[GameTaskConfig],
                           hp_threshold: float, mp_threshold: float,
                           stop_on_death: bool):
        """顺序执行任务"""
        for task_config in task_queue:
            self.log_info(f"执行任务: {task_config.task_name}")

            # 检查角色状态
            state = self.check_game_state()
            if state == GameState.DEAD:
                self.log_error("角色已死亡")
                if stop_on_death:
                    break
                else:
                    self._handle_death()
                    continue

            # 检查血量
            if self.check_hp_low(hp_threshold):
                self.log_warn(f"血量低于{hp_threshold}%，使用血药")
                self._use_potion('hp')

            # 检查蓝量
            if self.check_mp_low(mp_threshold):
                self.log_warn(f"蓝量低于{mp_threshold}%，使用蓝药")
                self._use_potion('mp')

            # 执行任务
            success = self._execute_single_task(task_config)
            if success:
                self.task_stats['total_completed'] += 1
                if task_config.task_type == 'gathering':
                    self.task_stats['gathering_completed'] += 1
                else:
                    self.task_stats['combat_completed'] += 1

    def _execute_by_priority(self, task_queue: List[GameTaskConfig],
                            hp_threshold: float, mp_threshold: float,
                            stop_on_death: bool):
        """按优先级执行任务（动态选择）"""
        while task_queue:
            # 找到优先级最高的任务
            task_config = max(task_queue, key=lambda x: x.priority)
            task_queue.remove(task_config)

            self.log_info(f"执行任务: {task_config.task_name}")

            # 状态检查
            state = self.check_game_state()
            if state == GameState.DEAD:
                if stop_on_death:
                    break
                else:
                    self._handle_death()
                    continue

            # 执行任务
            success = self._execute_single_task(task_config)
            if success:
                self.task_stats['total_completed'] += 1

    def _execute_loop(self, task_queue: List[GameTaskConfig],
                     hp_threshold: float, mp_threshold: float,
                     stop_on_death: bool):
        """循环执行任务"""
        import time

        loop_count = 0
        max_loops = 100  # 最大循环次数

        while loop_count < max_loops:
            loop_count += 1
            self.log_info(f"开始第 {loop_count} 轮循环")

            # 执行所有任务
            for task_config in task_queue:
                self.log_info(f"执行任务: {task_config.task_name}")

                # 状态检查
                state = self.check_game_state()
                if state == GameState.DEAD:
                    if stop_on_death:
                        return
                    else:
                        self._handle_death()
                        continue

                # 执行任务
                self._execute_single_task(task_config)

            # 如果任务不循环，执行一轮后退出
            if not any(t.loop for t in task_queue):
                break

            # 等待下一轮
            self.log_info("等待 10 秒后开始下一轮")
            time.sleep(10)

    def _execute_single_task(self, task_config: GameTaskConfig) -> bool:
        """执行单个任务"""
        try:
            if task_config.task_type == 'gathering':
                # 将配置传递给采集任务
                for key, value in task_config.config.items():
                    self.gathering_task.config[key] = value

                # 执行采集任务
                self.gathering_task.run()
                return True

            elif task_config.task_type == 'combat':
                # 将配置传递给战斗任务
                for key, value in task_config.config.items():
                    self.combat_task.config[key] = value

                # 执行战斗任务
                self.combat_task.run()
                return True

            else:
                self.log_warn(f"未知任务类型: {task_config.task_type}")
                return False

        except Exception as e:
            self.log_error(f"任务执行失败: {task_config.task_name}, 错误: {e}")
            return False

    def _use_potion(self, potion_type: str):
        """使用药水"""
        if potion_type == 'hp':
            key = self.config.get('血药快捷键', '0')
        else:
            key = self.config.get('蓝药快捷键', '9')

        self.cast_skill(key)
        self.sleep(1)

    def _handle_death(self):
        """处理死亡"""
        self.log_error("角色死亡，等待复活...")
        # TODO: 实现复活逻辑
        self.sleep(10)

    def _show_statistics(self):
        """显示任务统计"""
        stats = self.task_stats
        self.log_info("=" * 40)
        self.log_info("任务执行统计")
        self.log_info("=" * 40)
        self.log_info(f"总完成数: {stats['total_completed']}")
        self.log_info(f"采集任务: {stats['gathering_completed']}")
        self.log_info(f"战斗任务: {stats['combat_completed']}")
        self.log_info(f"总耗时: {stats['total_time']:.1f}秒")
        self.log_info("=" * 40)

    # ==================== 扩展接口 ====================

    def register_custom_task(self, task_config: GameTaskConfig):
        """
        注册自定义任务

        使用示例：
        ```python
        config = GameTaskConfig(
            task_id='custom_daily',
            task_name='自定义日常',
            task_type='custom',
            enabled=True,
            priority=5,
            config={
                'executor': lambda: your_custom_function()
            }
        )
        task.register_custom_task(config)
        ```
        """
        # 可以通过修改任务列表来添加自定义任务
        self.log_info(f"注册自定义任务: {task_config.task_name}")

    def add_gathering_resource(self, resource_id: str, resource_name: str,
                              minimap_marker: str):
        """
        添加新的采集资源

        使用示例：
        ```python
        task.add_gathering_resource(
            resource_id='special_ore',
            resource_name='稀有矿石',
            minimap_marker='minimap_rare_ore'
        )
        ```
        """
        from src.tasks.GatheringTask import GatheringResource

        resource = GatheringResource(
            resource_id=resource_id,
            resource_name=resource_name,
            minimap_marker=minimap_marker
        )

        self.gathering_task.resource_configs[resource_name] = resource
        self.log_info(f"添加采集资源: {resource_name}")

    def add_enemy_target(self, enemy_id: str, enemy_name: str,
                        priority: int = 1, is_boss: bool = False):
        """
        添加新的敌人目标

        使用示例：
        ```python
        task.add_enemy_target(
            enemy_id='enemy_special',
            enemy_name='特殊怪物',
            priority=3,
            is_boss=False
        )
        ```
        """
        from src.tasks.CombatTask import EnemyTarget

        enemy = EnemyTarget(
            enemy_id=enemy_id,
            enemy_name=enemy_name,
            priority=priority,
            is_boss=is_boss
        )

        self.combat_task.enemy_configs[enemy_name] = enemy
        self.log_info(f"添加敌人目标: {enemy_name}")
