"""
师门任务 - 自动接取、完成、提交师门任务
"""
import re
import time
from typing import Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from qfluentwidgets import FluentIcon

from src.tasks.BaseGameTask import BaseGameTask, GameState
from src.tasks.GatheringTask import GatheringTask
from src.tasks.CombatTask import CombatTask


class TaskType(Enum):
    """任务类型"""
    COMBAT = "combat"       # 战斗任务：消灭xxx
    GATHERING = "gathering" # 采集任务：采集xxx
    DELIVERY = "delivery"   # 递交任务：交给xxx
    UNKNOWN = "unknown"     # 未知类型


class ShimenState(Enum):
    """师门任务状态"""
    IDLE = "idle"               # 空闲
    CHECKING_TASK = "checking"  # 检查任务
    ACCEPTING = "accepting"     # 接取任务
    EXECUTING = "executing"     # 执行任务
    SUBMITTING = "submitting"   # 提交任务
    CHECKING_SCHEDULE = "schedule" # 检查日程
    FINISHED = "finished"       # 完成


@dataclass
class ShimenTaskInfo:
    """师门任务信息"""
    task_name: str          # 任务名称
    task_type: TaskType     # 任务类型
    target_name: str        # 目标名称（怪物/物品/NPC）
    target_count: int = 1   # 目标数量


class ShimenTask(BaseGameTask):
    """
    师门任务

    流程：
    1. 检查任务栏是否有"师门任务"
    2. 如果有，点击任务追踪前往
    3. 根据任务类型执行：
       - "消灭xxx" -> 战斗
       - "采集xxx" -> 采集
       - "交给xxx" -> 递交物品
    4. 返回提交任务
    5. 重复2-4直到任务栏没有"师门任务"
    6. 打开日程表
    7. 下拉寻找师门任务
    8. 判断状态：
       - "已完成" -> 停止
       - 还亮着 -> 点击"参与"
    9. 继续执行
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "师门任务"
        self.description = "自动完成师门任务（接取-执行-提交）"
        self.group_name = "日常任务"
        self.group_icon = FluentIcon.ROBOT
        self.icon = FluentIcon.TAG

        # 默认配置
        self.default_config.update({
            '最大任务轮数': 20,          # 最大执行轮数（防止死循环）
            '战斗时反击': True,
            '血量低于%逃离': 30,
            '任务失败重试次数': 3,
            '每次操作间隔(秒)': 1.5,
            '日程检查间隔(秒)': 2.0,
        })

        # 子任务实例（复用）
        self.gathering_task = GatheringTask(*args, **kwargs)
        self.combat_task = CombatTask(*args, **kwargs)

        # 当前状态
        self.current_state = ShimenState.IDLE
        self.completed_rounds = 0
        self.current_task_info: Optional[ShimenTaskInfo] = None

        # 统计信息
        self.statistics = {
            'total_rounds': 0,
            'combat_tasks': 0,
            'gathering_tasks': 0,
            'delivery_tasks': 0,
            'total_time': 0
        }

    def run(self):
        """任务执行入口"""
        self.log_info('师门任务开始', notify=True)

        import time
        start_time = time.time()

        try:
            max_rounds = self.config.get('最大任务轮数', 20)
            operation_delay = self.config.get('每次操作间隔(秒)', 1.5)
            hp_threshold = self.config.get('血量低于%逃离', 30)

            # 重置统计
            self.statistics = {
                'total_rounds': 0,
                'combat_tasks': 0,
                'gathering_tasks': 0,
                'delivery_tasks': 0,
                'total_time': 0
            }

            # 主循环
            while self.completed_rounds < max_rounds:
                # 检查角色状态
                state = self.check_game_state()
                if state == GameState.DEAD:
                    self.log_error("角色已死亡，停止任务")
                    break

                if self.check_hp_low(hp_threshold):
                    self.log_warn("血量过低，使用血药")
                    self._use_hp_potion()
                    time.sleep(2)

                # 步骤1: 检查任务栏是否有师门任务
                self.current_state = ShimenState.CHECKING_TASK
                has_task = self._check_shimen_task_in_list()

                if not has_task:
                    # 任务栏没有师门任务，去日程检查
                    self.log_info("任务栏没有师门任务，检查日程...")
                    schedule_result = self._check_schedule_and_accept()

                    if not schedule_result:
                        # 日程显示已完成，全部结束
                        self.log_info("师门任务全部完成！", notify=True)
                        break

                    # 等待任务出现
                    time.sleep(operation_delay)
                    continue

                # 步骤2: 解析任务信息
                task_info = self._parse_shimen_task()
                if not task_info:
                    self.log_warn("无法解析任务信息，重试...")
                    time.sleep(operation_delay)
                    continue

                self.current_task_info = task_info
                self.log_info(f"任务: {task_info.task_name} ({task_info.task_type.value}) - {task_info.target_name}")

                # 步骤3: 点击任务追踪前往
                self.log_info("点击任务追踪前往...")
                self.click_quest_track(0)  # 点击第一个任务
                time.sleep(operation_delay)

                # 步骤4: 执行任务
                self.current_state = ShimenState.EXECUTING
                success = self._execute_task(task_info)

                if not success:
                    self.log_warn("任务执行失败，重试...")
                    # 简单重试：重新点击任务追踪
                    time.sleep(2)
                    continue

                # 步骤5: 返回提交任务
                self.current_state = ShimenState.SUBMITTING
                self.log_info("返回提交任务...")
                self._submit_task()

                # 等待任务更新
                time.sleep(operation_delay)

                # 完成一轮
                self.completed_rounds += 1
                self.statistics['total_rounds'] += 1
                self.log_info(f"完成第 {self.completed_rounds} 轮任务")

            # 显示统计
            self.statistics['total_time'] = time.time() - start_time
            self._show_statistics()

        except Exception as e:
            self.log_error(f"师门任务异常: {e}")
            raise
        finally:
            self.log_info('师门任务结束', notify=True)

    # ==================== 任务检查 ====================

    def _check_shimen_task_in_list(self) -> bool:
        """
        检查任务栏是否有师门任务
        :return: 是否有师门任务
        """
        # 方法1: OCR识别任务栏中的"师门任务"文字
        result = self.ocr(
            box=self.quest_list_area,
            match=re.compile(r'师门'),
            log=False
        )

        if result:
            self.log_debug("找到师门任务")
            return True

        # 方法2: 使用模板匹配查找任务列表中的师门图标
        # shimen_icon = self.find_one('shimen_task_icon', box=self.quest_list_area)
        # if shimen_icon:
        #     return True

        return False

    def _parse_shimen_task(self) -> Optional[ShimenTaskInfo]:
        """
        解析师门任务信息
        :return: 任务信息
        """
        # OCR识别任务名称
        task_text = self.ocr(
            box=self.quest_list_area,
            log=False
        )

        if not task_text:
            return None

        self.log_debug(f"任务文字: {task_text}")

        # 解析任务类型和目标
        task_type = TaskType.UNKNOWN
        target_name = ""
        task_name = task_text

        # 匹配 "消灭xxx" 或 "击杀xxx"
        combat_match = re.search(r'(消灭|击杀|讨伐)(.+?)(\d+)?个?', task_text)
        if combat_match:
            task_type = TaskType.COMBAT
            target_name = combat_match.group(2).strip()
            self.statistics['combat_tasks'] += 1

        # 匹配 "采集xxx" 或 "收集xxx"
        gather_match = re.search(r'(采集|收集|获取)(.+?)(\d+)?个?', task_text)
        if gather_match:
            task_type = TaskType.GATHERING
            target_name = gather_match.group(2).strip()
            self.statistics['gathering_tasks'] += 1

        # 匹配 "交给xxx" 或 "拜访xxx"
        delivery_match = re.search(r'(交给|拜访|寻找)(.+?)(\d+)?个?', task_text)
        if delivery_match:
            task_type = TaskType.DELIVERY
            target_name = delivery_match.group(2).strip()
            self.statistics['delivery_tasks'] += 1

        if task_type == TaskType.UNKNOWN:
            self.log_warn(f"无法识别任务类型: {task_text}")
            return None

        return ShimenTaskInfo(
            task_name=task_name,
            task_type=task_type,
            target_name=target_name
        )

    # ==================== 任务执行 ====================

    def _execute_task(self, task_info: ShimenTaskInfo) -> bool:
        """
        执行任务
        :param task_info: 任务信息
        :return: 是否成功
        """
        if task_info.task_type == TaskType.COMBAT:
            return self._execute_combat_task(task_info)
        elif task_info.task_type == TaskType.GATHERING:
            return self._execute_gathering_task(task_info)
        elif task_info.task_type == TaskType.DELIVERY:
            return self._execute_delivery_task(task_info)
        else:
            self.log_warn(f"未知任务类型: {task_info.task_type}")
            return False

    def _execute_combat_task(self, task_info: ShimenTaskInfo) -> bool:
        """
        执行战斗任务
        :param task_info: 任务信息
        """
        self.log_info(f"执行战斗任务: {task_info.target_name}")

        # 点击任务追踪后，等待到达战斗地点
        time.sleep(3)

        # 查找敌人
        enemy_found = self.wait_until(
            lambda: self._find_enemy_by_name(task_info.target_name),
            timeout=15
        )

        if not enemy_found:
            self.log_warn(f"未找到敌人: {task_info.target_name}")
            return False

        # 战斗
        max_combat_time = 120  # 最大战斗时间
        start_time = time.time()

        while time.time() - start_time < max_combat_time:
            if not self.is_in_combat():
                # 战斗结束，检查是否还需要继续
                time.sleep(2)
                if not self.is_in_combat():
                    self.log_info("战斗完成")
                    return True

            # 释放技能
            skill_sequence = self.config.get('技能释放顺序', '1-2-3').split('-')
            for skill in skill_sequence:
                if self.is_in_combat():
                    self.cast_skill(skill)
                else:
                    break

            time.sleep(0.5)

        self.log_warn("战斗超时")
        return False

    def _execute_gathering_task(self, task_info: ShimenTaskInfo) -> bool:
        """
        执行采集任务
        :param task_info: 任务信息
        """
        self.log_info(f"执行采集任务: {task_info.target_name}")

        # 点击任务追踪后，等待到达采集地点
        time.sleep(3)

        # 查找采集目标
        # 尝试匹配目标名称对应的图片模板
        resource_id = self._get_resource_id_by_name(task_info.target_name)

        gather_count = 0
        max_gather_time = 120
        start_time = time.time()

        while time.time() - start_time < max_gather_time:
            # 查找采集目标
            if resource_id:
                pos = self.find_one(resource_id)
            else:
                # 如果没有对应模板，尝试OCR识别
                pos = self._find_gather_target_by_ocr(task_info.target_name)

            if not pos:
                self.log_debug("未找到采集目标，等待...")
                time.sleep(2)
                continue

            # 点击采集
            self.click(pos[0], pos[1])
            time.sleep(0.5)

            # 按F采集
            self.interact()
            self.log_info("采集中...")
            time.sleep(3)

            gather_count += 1

            # 检查是否完成（这里简化处理，采集一次后继续）
            # 实际可能需要采集多次
            if gather_count >= 1:
                self.log_info("采集完成")
                return True

        self.log_warn("采集超时")
        return False

    def _execute_delivery_task(self, task_info: ShimenTaskInfo) -> bool:
        """
        执行递交任务
        :param task_info: 任务信息
        """
        self.log_info(f"执行递交任务: {task_info.target_name}")

        # 点击任务追踪后，等待到达NPC位置
        time.sleep(3)

        # 查找NPC
        npc_found = self.wait_until(
            lambda: self._find_npc_by_name(task_info.target_name),
            timeout=15
        )

        if not npc_found:
            self.log_warn(f"未找到NPC: {task_info.target_name}")
            return False

        # 点击NPC对话
        self.log_info("与NPC对话...")
        self.interact()
        time.sleep(2)

        # 提交任务（通常需要点击对话框中的提交按钮）
        # 查找"提交"、"确定"等按钮
        submit_button = self.find_one('submit_button', threshold=0.7)
        if submit_button:
            self.click(submit_button[0], submit_button[1])
            time.sleep(1)
        else:
            # 按F或Enter提交
            self.send_key('enter')
            time.sleep(1)

        self.log_info("递交完成")
        return True

    # ==================== 任务提交 ====================

    def _submit_task(self):
        """提交任务"""
        # 返回NPC处提交
        # 通常点击任务追踪就会自动返回
        self.click_quest_track(0)
        time.sleep(3)

        # 与NPC对话提交
        self.interact()
        time.sleep(2)

        # 点击提交按钮
        submit_button = self.find_one('submit_button', threshold=0.7)
        if submit_button:
            self.click(submit_button[0], submit_button[1])
            time.sleep(1)
        else:
            self.send_key('enter')
            time.sleep(1)

        self.log_info("任务已提交")

    # ==================== 日程检查 ====================

    def _check_schedule_and_accept(self) -> bool:
        """
        检查日程并接取任务
        :return: 是否成功接取（True=继续，False=已完成停止）
        """
        self.current_state = ShimenState.CHECKING_SCHEDULE

        # 打开日程表
        self.log_info("打开日程表...")
        self._open_schedule()
        time.sleep(self.config.get('日程检查间隔(秒)', 2.0))

        # 下拉寻找师门任务
        self.log_info("查找师门任务...")
        shimen_found = self._find_shimen_in_schedule()

        if not shimen_found:
            self.log_warn("日程中未找到师门任务")
            return False

        # 判断任务状态
        is_completed = self._check_shimen_completed()

        if is_completed:
            # 已完成，关闭日程
            self.log_info("师门任务已完成")
            self._close_schedule()
            return False
        else:
            # 还亮着，点击参与
            self.log_info("点击参与师门任务...")
            success = self._click_accept_button()
            self._close_schedule()
            return success

    def _open_schedule(self):
        """打开日程表"""
        # 方法1: 按快捷键打开日程
        self.send_key('l')  # 假设L键打开日程
        time.sleep(0.5)

        # 方法2: 点击日程按钮图标
        schedule_button = self.find_one('schedule_button')
        if schedule_button:
            self.click(schedule_button[0], schedule_button[1])
            time.sleep(0.5)

    def _close_schedule(self):
        """关闭日程表"""
        # 按ESC关闭
        self.send_key('escape')
        time.sleep(0.5)

    def _find_shimen_in_schedule(self) -> bool:
        """
        在日程中查找师门任务
        :return: 是否找到
        """
        # 方法1: OCR识别"师门任务"文字
        result = self.ocr(
            match=re.compile(r'师门'),
            log=False
        )

        if result:
            return True

        # 方法2: 模板匹配师门任务图标
        shimen_icon = self.find_one('schedule_shimen_icon')
        return shimen_icon is not None

    def _check_shimen_completed(self) -> bool:
        """
        检查师门任务是否已完成
        :return: 是否已完成
        """
        # OCR识别"已完成"文字
        result = self.ocr(
            match=re.compile(r'已完成|完成|领取'),
            log=False
        )

        return result is not None

    def _click_accept_button(self) -> bool:
        """
        点击"参与"按钮
        :return: 是否成功点击
        """
        # 方法1: 模板匹配"参与"按钮
        accept_button = self.find_one('accept_button')
        if accept_button:
            self.click(accept_button[0], accept_button[1])
            self.log_info("已点击参与按钮")
            time.sleep(1)
            return True

        # 方法2: OCR识别"参与"文字并点击
        # 这个需要框架支持文字点击

        return False

    # ==================== 辅助方法 ====================

    def _find_enemy_by_name(self, enemy_name: str) -> bool:
        """根据名称查找敌人"""
        # 尝试使用模板匹配
        enemy_id = self._get_enemy_id_by_name(enemy_name)
        if enemy_id:
            return self.find_one(enemy_id) is not None

        # 使用OCR识别
        return self.ocr(match=re.compile(enemy_name), log=False) is not None

    def _find_gather_target_by_ocr(self, target_name: str) -> Optional[Tuple[float, float]]:
        """使用OCR查找采集目标"""
        # 框架需要支持OCR文字定位
        # 这里暂时返回None，使用模板匹配
        return None

    def _find_npc_by_name(self, npc_name: str) -> bool:
        """根据名称查找NPC"""
        # NPC头上通常有名字标注
        return self.ocr(match=re.compile(npc_name), log=False) is not None

    def _get_resource_id_by_name(self, resource_name: str) -> Optional[str]:
        """
        根据资源名称获取对应的图片模板ID
        需要根据游戏实际配置
        """
        # 资源名称到模板ID的映射
        resource_mapping = {
            '铁矿': 'ore_iron',
            '铜矿': 'ore_copper',
            '草药': 'herb_basic',
            '木材': 'wood_basic',
            # 添加更多映射...
        }

        return resource_mapping.get(resource_name)

    def _get_enemy_id_by_name(self, enemy_name: str) -> Optional[str]:
        """
        根据敌人名称获取对应的图片模板ID
        """
        enemy_mapping = {
            '野猪': 'enemy_boar',
            '狼': 'enemy_wolf',
            # 添加更多映射...
        }

        return enemy_mapping.get(enemy_name)

    def _use_hp_potion(self):
        """使用血药"""
        key = self.config.get('血药快捷键', '0')
        self.cast_skill(key)
        time.sleep(1)

    def _show_statistics(self):
        """显示统计信息"""
        stats = self.statistics
        self.log_info("=" * 40)
        self.log_info("师门任务统计")
        self.log_info("=" * 40)
        self.log_info(f"总任务数: {stats['total_rounds']}")
        self.log_info(f"战斗任务: {stats['combat_tasks']}")
        self.log_info(f"采集任务: {stats['gathering_tasks']}")
        self.log_info(f"递交任务: {stats['delivery_tasks']}")
        self.log_info(f"总耗时: {stats['total_time']:.1f}秒")
        self.log_info("=" * 40)
