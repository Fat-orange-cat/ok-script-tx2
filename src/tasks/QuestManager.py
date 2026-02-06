"""
任务管理器 - 管理任务状态、导航和执行流程
"""
import re
import time
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

from ok import Logger

logger = Logger.get_logger(__name__)


class QuestStatus(Enum):
    """任务状态"""
    PENDING = "pending"       # 待执行
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    SKIPPED = "skipped"       # 跳过


class TaskType(Enum):
    """任务类型"""
    GATHERING = "gathering"   # 采集
    COMBAT = "combat"         # 战斗
    INTERACT = "interact"     # 交互
    MOVE_TO = "move_to"       # 移动到指定位置
    WAIT = "wait"             # 等待
    CUSTOM = "custom"         # 自定义


@dataclass
class QuestTask:
    """单个任务数据结构"""
    task_id: str                      # 任务唯一ID
    task_type: TaskType               # 任务类型
    name: str                         # 任务名称
    description: str = ""             # 任务描述
    status: QuestStatus = QuestStatus.PENDING
    priority: int = 0                 # 优先级（数字越大优先级越高）
    max_retry: int = 3                # 最大重试次数
    retry_count: int = 0              # 当前重试次数
    timeout: float = 60.0             # 超时时间（秒）
    config: Dict[str, Any] = field(default_factory=dict)  # 任务配置参数
    pre_condition: Optional[Callable[[], bool]] = None    # 前置条件检查
    post_condition: Optional[Callable[[], bool]] = None   # 后置条件检查
    on_start: Optional[Callable[[], None]] = None         # 任务开始回调
    on_complete: Optional[Callable[[], None]] = None      # 任务完成回调
    on_fail: Optional[Callable[[], None]] = None          # 任务失败回调


@dataclass
class QuestConfig:
    """任务链配置"""
    quest_id: str                      # 任务链ID
    quest_name: str                    # 任务链名称
    description: str = ""              # 描述
    enabled: bool = True               # 是否启用
    loop: bool = False                 # 是否循环执行
    loop_delay: float = 5.0            # 循环间隔（秒）
    tasks: List[QuestTask] = field(default_factory=list)  # 任务列表


class QuestManager:
    """
    任务管理器

    功能：
    1. 管理任务队列和状态
    2. 控制任务执行流程
    3. 处理任务失败重试
    4. 支持任务前置/后置条件检查
    5. 循环执行任务链
    """

    def __init__(self, game_task):
        """
        初始化任务管理器
        :param game_task: 游戏任务实例（用于调用游戏操作）
        """
        self.game_task = game_task
        self.quests: Dict[str, QuestConfig] = {}  # 所有任务链
        self.current_quest: Optional[QuestConfig] = None
        self.current_task: Optional[QuestTask] = None
        self.quest_history: List[Dict] = []       # 任务执行历史
        self.statistics = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'skipped_tasks': 0
        }

    def register_quest(self, quest: QuestConfig):
        """
        注册任务链
        :param quest: 任务链配置
        """
        self.quests[quest.quest_id] = quest
        logger.info(f"注册任务链: {quest.quest_name} ({quest.quest_id})")

    def unregister_quest(self, quest_id: str):
        """
        注销任务链
        :param quest_id: 任务链ID
        """
        if quest_id in self.quests:
            del self.quests[quest_id]
            logger.info(f"注销任务链: {quest_id}")

    def get_quest(self, quest_id: str) -> Optional[QuestConfig]:
        """获取任务链配置"""
        return self.quests.get(quest_id)

    def list_quests(self) -> List[QuestConfig]:
        """获取所有启用的任务链"""
        return [q for q in self.quests.values() if q.enabled]

    # ==================== 任务执行 ====================

    def execute_quest(self, quest_id: str) -> bool:
        """
        执行指定任务链
        :param quest_id: 任务链ID
        :return: 是否全部成功
        """
        quest = self.get_quest(quest_id)
        if not quest:
            logger.error(f"任务链不存在: {quest_id}")
            return False

        self.current_quest = quest
        logger.info(f"开始执行任务链: {quest.quest_name}")
        self.game_task.log_info(f"开始执行任务链: {quest.quest_name}", notify=True)

        # 重置所有任务状态
        for task in quest.tasks:
            task.status = QuestStatus.PENDING
            task.retry_count = 0

        # 执行任务链
        success = True
        loop_count = 0

        while True:
            loop_count += 1
            if loop_count > 1 and not quest.loop:
                break

            # 执行所有任务
            for task in quest.tasks:
                if not self._execute_single_task(task):
                    success = False
                    if task.retry_count >= task.max_retry:
                        logger.error(f"任务执行失败，已达最大重试次数: {task.name}")
                        if task.on_fail:
                            task.on_fail()
                        break
                    # 重试
                    task.retry_count += 1
                    logger.info(f"任务重试 ({task.retry_count}/{task.max_retry}): {task.name}")
                    if not self._execute_single_task(task):
                        continue
                    else:
                        # 重试成功，继续执行
                        task.status = QuestStatus.COMPLETED
                        if task.on_complete:
                            task.on_complete()

            # 如果不循环，执行一次后退出
            if not quest.loop:
                break

            # 循环延迟
            if loop_count > 1:
                logger.info(f"任务链循环，等待 {quest.loop_delay} 秒后重新开始")
                time.sleep(quest.loop_delay)

        # 记录历史
        self._record_history(quest, success)

        return success

    def _execute_single_task(self, task: QuestTask) -> bool:
        """
        执行单个任务
        :param task: 任务对象
        :return: 是否成功
        """
        self.current_task = task
        self.statistics['total_tasks'] += 1

        logger.info(f"执行任务: {task.name} ({task.task_type.value})")

        # 检查前置条件
        if task.pre_condition and not task.pre_condition():
            logger.warning(f"任务前置条件不满足，跳过: {task.name}")
            task.status = QuestStatus.SKIPPED
            self.statistics['skipped_tasks'] += 1
            return True

        # 任务开始回调
        if task.on_start:
            task.on_start()

        task.status = QuestStatus.IN_PROGRESS

        # 执行任务逻辑
        try:
            result = self._execute_task_by_type(task)

            # 检查后置条件
            if task.post_condition and not task.post_condition():
                logger.warning(f"任务后置条件不满足: {task.name}")
                result = False

            if result:
                task.status = QuestStatus.COMPLETED
                self.statistics['completed_tasks'] += 1
                logger.info(f"任务完成: {task.name}")
                if task.on_complete:
                    task.on_complete()
                return True
            else:
                task.status = QuestStatus.FAILED
                self.statistics['failed_tasks'] += 1
                logger.error(f"任务失败: {task.name}")
                return False

        except Exception as e:
            logger.error(f"任务执行异常: {task.name}, 错误: {e}")
            task.status = QuestStatus.FAILED
            self.statistics['failed_tasks'] += 1
            return False

    def _execute_task_by_type(self, task: QuestTask) -> bool:
        """
        根据任务类型执行具体逻辑
        :param task: 任务对象
        :return: 是否成功
        """
        start_time = time.time()
        timeout = task.config.get('timeout', task.timeout)

        if task.task_type == TaskType.GATHERING:
            return self._execute_gathering_task(task, timeout)
        elif task.task_type == TaskType.COMBAT:
            return self._execute_combat_task(task, timeout)
        elif task.task_type == TaskType.INTERACT:
            return self._execute_interact_task(task, timeout)
        elif task.task_type == TaskType.MOVE_TO:
            return self._execute_move_to_task(task, timeout)
        elif task.task_type == TaskType.WAIT:
            return self._execute_wait_task(task)
        elif task.task_type == TaskType.CUSTOM:
            # 自定义任务，由config中的executor执行
            executor = task.config.get('executor')
            if executor:
                return executor()
            return False
        else:
            logger.warning(f"未知任务类型: {task.task_type}")
            return False

    # ==================== 各类型任务执行逻辑 ====================

    def _execute_gathering_task(self, task: QuestTask, timeout: float) -> bool:
        """
        执行采集任务
        :param task: 任务对象
        :param timeout: 超时时间
        """
        resource_name = task.config.get('resource_name')
        minimap_marker = task.config.get('minimap_marker')
        gather_count = task.config.get('gather_count', 1)
        gather_key = task.config.get('gather_key', 'f')

        if not resource_name:
            logger.error("采集任务缺少resource_name配置")
            return False

        logger.info(f"开始采集: {resource_name}, 目标数量: {gather_count}")

        gathered = 0
        start_time = time.time()

        while gathered < gather_count and (time.time() - start_time) < timeout:
            # 检查是否还在采集范围内
            # 1. 在小地图上查找资源标记
            if minimap_marker:
                found = self.game_task.navigate_to_minimap_target(minimap_marker)
                if not found:
                    logger.warning(f"小地图上未找到资源标记: {minimap_marker}")
                    return False

            # 2. 在屏幕上查找采集目标
            if self.game_task.wait_until(lambda: self._find_gather_target(resource_name), timeout=10):
                # 3. 点击目标
                self.game_task.click_target(resource_name)
                time.sleep(0.5)

                # 4. 采集
                self.game_task.operate(lambda: self.game_task.send_key(gather_key))
                logger.info(f"采集中... ({gathered + 1}/{gather_count})")

                # 5. 等待采集完成（检测采集进度条或等待固定时间）
                time.sleep(3)
                gathered += 1
            else:
                logger.warning(f"未找到采集目标: {resource_name}")
                return False

        logger.info(f"采集完成: {gathered}/{gather_count}")
        return gathered >= gather_count

    def _execute_combat_task(self, task: QuestTask, timeout: float) -> bool:
        """
        执行战斗任务
        :param task: 任务对象
        :param timeout: 超时时间
        """
        target_name = task.config.get('target_name')
        skill_sequence = task.config.get('skill_sequence', ['1', '2', '3'])
        kill_count = task.config.get('kill_count', 1)

        if not target_name:
            logger.error("战斗任务缺少target_name配置")
            return False

        logger.info(f"开始战斗: {target_name}, 目标击杀数: {kill_count}")

        killed = 0
        start_time = time.time()

        while killed < kill_count and (time.time() - start_time) < timeout:
            # 1. 查找敌人
            if self.game_task.wait_until(lambda: self._find_enemy(target_name), timeout=10):
                # 2. 锁定并攻击
                self.game_task.click_target(target_name)
                time.sleep(0.5)

                # 3. 释放技能循环
                while self.game_task.is_in_combat() and (time.time() - start_time) < timeout:
                    for skill in skill_sequence:
                        if self.game_task.is_in_combat():
                            self.game_task.cast_skill(skill)
                        else:
                            break
                    time.sleep(0.5)

                # 4. 等待战斗结束
                time.sleep(2)

                # 5. 检查敌人是否死亡
                if not self._find_enemy(target_name):
                    killed += 1
                    logger.info(f"击杀敌人 ({killed}/{kill_count})")
            else:
                logger.warning(f"未找到敌人: {target_name}")
                return False

        logger.info(f"战斗完成: {killed}/{kill_count}")
        return killed >= kill_count

    def _execute_interact_task(self, task: QuestTask, timeout: float) -> bool:
        """
        执行交互任务
        :param task: 任务对象
        :param timeout: 超时时间
        """
        target_name = task.config.get('target_name')
        interact_key = task.config.get('interact_key', 'f')

        if not target_name:
            logger.error("交互任务缺少target_name配置")
            return False

        logger.info(f"开始交互: {target_name}")

        # 查找交互目标
        if self.game_task.wait_until(lambda: self.game_task.find_one(target_name), timeout=timeout):
            # 点击目标
            self.game_task.click_target(target_name)
            time.sleep(0.5)

            # 交互
            self.game_task.operate(lambda: self.game_task.send_key(interact_key))
            time.sleep(1)

            logger.info(f"交互完成: {target_name}")
            return True
        else:
            logger.error(f"未找到交互目标: {target_name}")
            return False

    def _execute_move_to_task(self, task: QuestTask, timeout: float) -> bool:
        """
        执行移动任务
        :param task: 任务对象
        :param timeout: 超时时间
        """
        # 移动到指定位置（可以结合任务追踪自动寻路）
        quest_index = task.config.get('quest_index', 0)

        # 点击任务追踪
        self.game_task.click_quest_track(quest_index)

        # 等待到达目标位置（这里需要根据具体游戏实现检测逻辑）
        # 例如检测"到达"提示文字或特定坐标
        logger.info("开始移动到目标位置")

        # 简单实现：按下W键一段时间
        self.game_task.move_forward(duration=5.0)

        logger.info("移动任务完成")
        return True

    def _execute_wait_task(self, task: QuestTask) -> bool:
        """
        执行等待任务
        :param task: 任务对象
        """
        wait_time = task.config.get('wait_time', 1.0)
        logger.info(f"等待 {wait_time} 秒")
        time.sleep(wait_time)
        return True

    # ==================== 辅助方法 ====================

    def _find_gather_target(self, resource_name: str) -> bool:
        """查找采集目标"""
        return self.game_task.find_one(resource_name) is not None

    def _find_enemy(self, target_name: str) -> bool:
        """查找敌人"""
        return self.game_task.find_one(target_name) is not None

    def _record_history(self, quest: QuestConfig, success: bool):
        """记录任务执行历史"""
        record = {
            'quest_id': quest.quest_id,
            'quest_name': quest.quest_name,
            'timestamp': time.time(),
            'success': success,
            'statistics': self.statistics.copy()
        }
        self.quest_history.append(record)

        # 保持历史记录不超过100条
        if len(self.quest_history) > 100:
            self.quest_history = self.quest_history[-100:]

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return self.statistics.copy()

    def reset_statistics(self):
        """重置统计信息"""
        self.statistics = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'skipped_tasks': 0
        }

    def stop_current_execution(self):
        """停止当前任务执行"""
        logger.info("停止任务执行")
        # 可以通过设置标志位来中断执行
        self.current_quest = None
        self.current_task = None
