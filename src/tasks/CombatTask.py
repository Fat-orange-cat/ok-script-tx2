"""
战斗任务模块 - 自动战斗系统
"""
import re
import time
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from qfluentwidgets import FluentIcon

from src.tasks.BaseGameTask import BaseGameTask, GameState
from src.tasks.QuestManager import QuestManager, QuestConfig, QuestTask, TaskType


class CombatMode(Enum):
    """战斗模式"""
    AUTO = "auto"           # 自动战斗：自动寻找并攻击敌人
    DEFENSIVE = "defensive" # 防御模式：只反击攻击自己的敌人
    BOSS = "boss"           # Boss战模式：专注单个Boss目标
    FARM = "farm"           # 刷怪模式：在指定区域循环刷怪


class SkillPriority(Enum):
    """技能优先级"""
    HIGH = 3    # 高优先级（如爆发技能）
    MEDIUM = 2  # 中优先级（如常用技能）
    LOW = 1     # 低优先级（如填充技能）


@dataclass
class SkillConfig:
    """技能配置"""
    key: str                    # 技能按键
    name: str                   # 技能名称
    priority: SkillPriority     # 优先级
    cooldown: float = 0.0       # 冷却时间（秒）
    last_used: float = 0.0      # 上次使用时间
    condition: Optional[Callable[[], bool]] = None  # 使用条件
    mp_cost: int = 0            # 蓝量消耗


@dataclass
class EnemyTarget:
    """敌人目标配置"""
    enemy_id: str               # 敌人ID（对应图片模板）
    enemy_name: str             # 敌人名称
    priority: int = 0           # 优先级（数字越大优先级越高）
    kill_count: int = 1         # 击杀目标数量
    is_boss: bool = False       # 是否是Boss


class CombatTask(BaseGameTask):
    """
    战斗任务

    功能：
    1. 自动识别敌人
    2. 智能技能循环
    3. 多种战斗模式
    4. 血量/蓝量管理
    5. 战斗统计
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "战斗任务"
        self.description = "自动战斗和刷怪"
        self.group_name = "日常任务"
        self.group_icon = FluentIcon.ROBOT
        self.icon = FluentIcon.GAME

        # 任务管理器
        self.quest_manager = QuestManager(self)

        # 默认配置
        self.default_config.update({
            '战斗模式': 'auto',
            '目标敌人选择': '所有',
            '技能释放顺序': '1-2-3-4',
            '血量低于%使用血药': 30,
            '蓝量低于%使用蓝药': 20,
            '血药快捷键': '0',
            '蓝药快捷键': '9',
            '战斗循环次数': 10,
            '每次战斗间隔(秒)': 5,
            '是否自动拾取': True,
            '背包满自动停止': False,
        })

        self.config_type["战斗模式"] = {
            'type': "drop_down",
            'options': ['auto', 'defensive', 'boss', 'farm']
        }

        self.config_type["目标敌人选择"] = {
            'type': "drop_down",
            'options': ['所有', '精英怪', 'Boss', '自定义']
        }

        # 技能配置
        self.skills: List[SkillConfig] = []

        # 敌人配置
        self.enemy_configs: Dict[str, EnemyTarget] = {
            '普通怪': EnemyTarget(
                enemy_id='enemy_normal',
                enemy_name='普通怪物',
                priority=1,
                kill_count=1,
                is_boss=False
            ),
            '精英怪': EnemyTarget(
                enemy_id='enemy_elite',
                enemy_name='精英怪物',
                priority=2,
                kill_count=1,
                is_boss=False
            ),
            'Boss': EnemyTarget(
                enemy_id='enemy_boss',
                enemy_name='Boss',
                priority=10,
                kill_count=1,
                is_boss=True
            ),
        }

        # 战斗统计
        self.combat_stats = {
            'total_kills': 0,
            'total_deaths': 0,
            'combats': 0,
            'skills_used': 0,
            'potions_used': 0
        }

        # 战斗状态
        self.in_combat = False
        self.current_target = None

    def run(self):
        """任务执行入口"""
        self.log_info('战斗任务开始', notify=True)

        # 重置统计
        self.combat_stats = {
            'total_kills': 0,
            'total_deaths': 0,
            'combats': 0,
            'skills_used': 0,
            'potions_used': 0
        }

        try:
            # 解析技能配置
            self._parse_skill_config()

            # 获取配置
            combat_mode = CombatMode(self.config.get('战斗模式', 'auto'))
            target_selection = self.config.get('目标敌人选择', '所有')
            combat_count = self.config.get('战斗循环次数', 10)
            combat_interval = self.config.get('每次战斗间隔(秒)', 5)
            auto_loot = self.config.get('是否自动拾取', True)

            hp_threshold = self.config.get('血量低于%使用血药', 30)
            mp_threshold = self.config.get('蓝量低于%使用蓝药', 20)

            # 构建战斗任务链
            quest = self._build_combat_quest(combat_mode, target_selection, combat_count)

            # 注册任务
            self.quest_manager.register_quest(quest)

            # 执行战斗循环
            loop_count = 0
            while loop_count < combat_count:
                loop_count += 1

                self.log_info(f"开始第 {loop_count}/{combat_count} 次战斗")

                # 检查角色状态
                state = self.check_game_state()
                if state == GameState.DEAD:
                    self.log_error("角色已死亡")
                    self.combat_stats['total_deaths'] += 1
                    self._handle_death()
                    continue

                # 检查背包
                if self.config.get('背包满自动停止', False):
                    # TODO: 实现背包满检测
                    pass

                # 执行战斗
                self._execute_combat(combat_mode, hp_threshold, mp_threshold)

                # 战斗后处理
                if auto_loot:
                    self._loot_items()

                # 等待间隔
                if loop_count < combat_count:
                    self.log_info(f"等待 {combat_interval} 秒后继续")
                    self.sleep(combat_interval)

            # 显示统计
            self._show_statistics()

        except Exception as e:
            self.log_error(f"战斗任务异常: {e}")
            raise
        finally:
            self.log_info('战斗任务结束', notify=True)

    def _parse_skill_config(self):
        """解析技能配置"""
        skill_sequence = self.config.get('技能释放顺序', '1-2-3-4').split('-')

        self.skills = []
        for i, key in enumerate(skill_sequence):
            # 优先级：前面的技能优先级高
            priority = SkillPriority.HIGH if i < 2 else SkillPriority.MEDIUM
            if i >= len(skill_sequence) - 1:
                priority = SkillPriority.LOW

            skill = SkillConfig(
                key=key.strip(),
                name=f"技能{key}",
                priority=priority,
                cooldown=1.0,  # 默认冷却时间
                last_used=0
            )
            self.skills.append(skill)

    def _build_combat_quest(self, combat_mode: CombatMode,
                           target_selection: str, combat_count: int) -> QuestConfig:
        """构建战斗任务链"""
        tasks = []

        # 根据选择确定敌人类型
        enemy_types = self._get_enemy_types(target_selection)

        for enemy_type in enemy_types:
            if enemy_type not in self.enemy_configs:
                continue

            config = self.enemy_configs[enemy_type]

            # 根据战斗模式设置击杀数量
            if combat_mode == CombatMode.FARM:
                kill_count = combat_count
            else:
                kill_count = config.kill_count

            # 创建战斗任务
            task = QuestTask(
                task_id=f"combat_{enemy_type}",
                task_type=TaskType.COMBAT,
                name=f"战斗{config.enemy_name}",
                description=f"击杀 {kill_count} 个 {config.enemy_name}",
                priority=config.priority,
                config={
                    'target_name': config.enemy_id,
                    'kill_count': kill_count,
                    'skill_sequence': [s.key for s in self.skills],
                    'timeout': 120.0
                },
                on_complete=lambda e=enemy_type: self._on_kill_complete(e)
            )

            tasks.append(task)

        # 构建任务链
        quest = QuestConfig(
            quest_id='daily_combat',
            quest_name='日常战斗',
            description='自动战斗刷怪',
            enabled=True,
            loop=False,
            tasks=tasks
        )

        return quest

    def _get_enemy_types(self, selection: str) -> List[str]:
        """根据配置获取敌人类型"""
        if selection == '所有':
            return ['普通怪', '精英怪']
        elif selection == '精英怪':
            return ['精英怪']
        elif selection == 'Boss':
            return ['Boss']
        else:
            return ['普通怪']

    def _execute_combat(self, combat_mode: CombatMode,
                       hp_threshold: float, mp_threshold: float):
        """执行战斗逻辑"""
        self.in_combat = False
        self.combat_stats['combats'] += 1

        # 根据战斗模式执行不同的逻辑
        if combat_mode == CombatMode.AUTO:
            self._auto_combat(hp_threshold, mp_threshold)
        elif combat_mode == CombatMode.DEFENSIVE:
            self._defensive_combat(hp_threshold, mp_threshold)
        elif combat_mode == CombatMode.BOSS:
            self._boss_combat(hp_threshold, mp_threshold)
        elif combat_mode == CombatMode.FARM:
            self._farm_combat(hp_threshold, mp_threshold)

    def _auto_combat(self, hp_threshold: float, mp_threshold: float):
        """自动战斗模式"""
        # 1. 寻找最近的敌人
        target = self._find_nearest_enemy()
        if not target:
            self.log_warn("未找到敌人")
            return

        # 2. 锁定目标
        self._lock_target(target)
        self.in_combat = True

        # 3. 战斗循环
        while self.is_in_combat():
            # 检查血量蓝量
            if self.check_hp_low(hp_threshold):
                self._use_hp_potion()
            if self.check_mp_low(mp_threshold):
                self._use_mp_potion()

            # 释放技能
            self._execute_skill_rotation()

            self.sleep(0.5)

        self.in_combat = False
        self.log_info("战斗结束")

    def _defensive_combat(self, hp_threshold: float, mp_threshold: float):
        """防御战斗模式 - 只反击"""
        # 等待进入战斗（被攻击）
        if not self.wait_until(self.is_in_combat, timeout=30):
            self.log_info("未遇敌，继续巡逻")
            return

        self.in_combat = True

        # 战斗循环
        while self.is_in_combat():
            # 检查血量蓝量
            if self.check_hp_low(hp_threshold):
                self._use_hp_potion()
            if self.check_mp_low(mp_threshold):
                self._use_mp_potion()

            # 释放技能
            self._execute_skill_rotation()

            self.sleep(0.5)

        self.in_combat = False
        self.log_info("防御战斗结束")

    def _boss_combat(self, hp_threshold: float, mp_threshold: float):
        """Boss战模式"""
        # Boss战逻辑与自动战斗类似，但更注重爆发技能的使用
        target = self._find_nearest_enemy()
        if not target:
            self.log_warn("未找到Boss")
            return

        self._lock_target(target)
        self.in_combat = True

        while self.is_in_combat():
            if self.check_hp_low(hp_threshold):
                self._use_hp_potion()
            if self.check_mp_low(mp_threshold):
                self._use_mp_potion()

            # Boss战优先使用高优先级技能
            self._execute_burst_skill_rotation()

            self.sleep(0.5)

        self.in_combat = False
        self.log_info("Boss战结束")

    def _farm_combat(self, hp_threshold: float, mp_threshold: float):
        """刷怪模式"""
        # 在指定区域循环刷怪
        while True:
            self._auto_combat(hp_threshold, mp_threshold)

            # 移动到下一个位置
            self._move_to_next_farm_spot()

            # 检查是否完成循环次数
            if not self.is_in_combat():
                break

    def _find_nearest_enemy(self) -> Optional[tuple]:
        """查找最近的敌人"""
        # 遍历所有敌人类型，找到最近的
        nearest_enemy = None
        min_distance = float('inf')

        for enemy_type, config in self.enemy_configs.items():
            pos = self.find_one(config.enemy_id)
            if pos:
                # 计算到屏幕中心的距离
                distance = ((pos[0] - 0.5) ** 2 + (pos[1] - 0.5) ** 2) ** 0.5
                if distance < min_distance:
                    min_distance = distance
                    nearest_enemy = (pos, config)

        if nearest_enemy:
            self.current_target = nearest_enemy[1]
            return nearest_enemy[0]
        return None

    def _lock_target(self, target_pos: tuple):
        """锁定目标"""
        # 点击目标
        self.click(target_pos[0], target_pos[1])
        self.sleep(0.3)
        # 按Tab键锁定目标（某些游戏）
        # self.send_key('tab')

    def _execute_skill_rotation(self):
        """执行技能循环"""
        # 按优先级排序技能
        sorted_skills = sorted(self.skills, key=lambda s: s.priority.value, reverse=True)

        current_time = time.time()

        for skill in sorted_skills:
            # 检查冷却
            if current_time - skill.last_used < skill.cooldown:
                continue

            # 检查使用条件
            if skill.condition and not skill.condition():
                continue

            # 释放技能
            self.cast_skill(skill.key)
            skill.last_used = current_time
            self.combat_stats['skills_used'] += 1

            # 只释放一个技能，等待下一次循环
            break

    def _execute_burst_skill_rotation(self):
        """爆发技能循环（Boss战用）"""
        # 只使用高优先级技能
        burst_skills = [s for s in self.skills if s.priority == SkillPriority.HIGH]

        current_time = time.time()

        for skill in burst_skills:
            if current_time - skill.last_used < skill.cooldown:
                continue

            self.cast_skill(skill.key)
            skill.last_used = current_time
            self.combat_stats['skills_used'] += 1
            break

    def _use_hp_potion(self):
        """使用血药"""
        key = self.config.get('血药快捷键', '0')
        self.cast_skill(key)
        self.combat_stats['potions_used'] += 1
        self.log_info("使用血药")

    def _use_mp_potion(self):
        """使用蓝药"""
        key = self.config.get('蓝药快捷键', '9')
        self.cast_skill(key)
        self.combat_stats['potions_used'] += 1
        self.log_info("使用蓝药")

    def _loot_items(self):
        """拾取物品"""
        self.log_info("拾取物品...")
        # 按F键拾取
        self.pick_up_item()
        self.sleep(0.5)

    def _move_to_next_farm_spot(self):
        """移动到下一个刷怪点"""
        # 简单实现：随机移动
        import random
        direction = random.choice(['left', 'right', 'forward'])
        duration = random.uniform(2.0, 5.0)

        if direction == 'left':
            self.move_left(duration)
        elif direction == 'right':
            self.move_right(duration)
        else:
            self.move_forward(duration)

    def _handle_death(self):
        """处理死亡"""
        self.log_error("角色死亡，等待复活...")
        # TODO: 实现复活逻辑
        self.sleep(10)

    def _on_kill_complete(self, enemy_type: str):
        """击杀完成回调"""
        self.combat_stats['total_kills'] += 1
        self.log_info(f"击杀敌人: {enemy_type}")

    def _show_statistics(self):
        """显示战斗统计"""
        stats = self.combat_stats
        self.log_info("=" * 40)
        self.log_info("战斗任务统计")
        self.log_info("=" * 40)
        self.log_info(f"战斗场次: {stats['combats']}")
        self.log_info(f"总击杀数: {stats['total_kills']}")
        self.log_info(f"死亡次数: {stats['total_deaths']}")
        self.log_info(f"技能使用: {stats['skills_used']}")
        self.log_info(f"药水使用: {stats['potions_used']}")
        self.log_info("=" * 40)
