# 3D MMORPG 游戏自动化任务系统

这是一个基于 ok-script 框架的可扩展游戏自动化任务系统，支持采集和战斗功能。

## 功能特性

### 已实现的功能

1. **采集任务** (`GatheringTask`)
   - 自动识别可采集资源
   - 小地图导航到资源位置
   - 自动采集并计数
   - 支持多种资源配置

2. **战斗任务** (`CombatTask`)
   - 自动识别敌人
   - 智能技能循环
   - 多种战斗模式（自动、防御、Boss战、刷怪）
   - 血量/蓝量管理

3. **游戏任务系统** (`GameQuestTask`)
   - 整合采集和战斗
   - UI配置支持
   - 可扩展架构
   - 任务优先级管理

4. **基础游戏功能** (`BaseGameTask`)
   - 移动控制（WASD）
   - 视角调整
   - 战斗状态检测
   - 小地图导航
   - 任务列表交互
   - 技能释放

## 项目结构

```
src/tasks/
├── BaseGameTask.py      # 游戏基础任务类（提供通用游戏操作）
├── QuestManager.py      # 任务管理器（管理任务队列和状态）
├── GatheringTask.py     # 采集任务
├── CombatTask.py        # 战斗任务
├── GameQuestTask.py     # 主任务系统（整合所有功能）
├── MyBaseTask.py        # 框架基础任务
└── MyOneTimeTask.py     # 示例任务
```

## 配置说明

### 游戏配置 (`config.py`)

```python
'windows': {
    'exe': ['YourGame.exe'],        # 修改为你的游戏进程名
    'interaction': 'Pynput',        # 交互方式
    'capture_method': ['WGC', 'BitBlt_RenderFull'],
    'require_bg': True              # 后台运行
}
```

### UI 配置选项

运行程序后，在GUI界面中可以配置：

#### 采集任务配置
- **采集目标选择**: 所有/仅矿点/仅草药/仅树木
- **采集循环执行**: 是否循环采集
- **采集循环间隔**: 循环间隔时间（秒）
- **战斗时是否反击**: 遇到敌人是否反击
- **血量低于%自动逃离**: 血量阈值

#### 战斗任务配置
- **战斗模式**: auto/defensive/boss/farm
- **目标敌人选择**: 所有/精英怪/Boss/自定义
- **技能释放顺序**: 用短横线分隔（如 1-2-3-4）
- **血量低于%使用血药**: 血药阈值
- **蓝量低于%使用蓝药**: 蓝药阈值
- **战斗循环次数**: 战斗次数
- **是否自动拾取**: 战斗后自动拾取

#### 主任务系统配置
- **任务执行模式**: 顺序执行/优先级执行/循环执行
- **采集任务_启用**: 是否启用采集
- **战斗任务_启用**: 是否启用战斗
- **死亡后停止任务**: 角色死亡后是否停止

## 使用方法

### 1. 准备图片模板

在 `assets/images/` 目录下准备以下图片模板：

#### 采集资源模板
```
assets/images/
├── ore_deposit.png      # 矿点（在屏幕中）
├── herb_plant.png       # 草药（在屏幕中）
├── tree.png             # 树木（在屏幕中）
├── minimap_ore.png      # 小地图上的矿点标记
├── minimap_herb.png     # 小地图上的草药标记
└── minimap_tree.png     # 小地图上的树木标记
```

#### 敌人模板
```
assets/images/
├── enemy_normal.png     # 普通怪物
├── enemy_elite.png      # 精英怪物
└── enemy_boss.png       # Boss
```

#### 战斗UI模板
```
assets/images/
└── combat_hp_bar.png    # 战斗血条（用于检测是否进入战斗）
```

### 2. 更新 COCO 标注文件

在 `assets/result.json` 中添加图片标注：

```json
{
  "images": [
    {
      "id": 1,
      "file_name": "ore_deposit.png",
      "annotations": [
        {
          "id": 1,
          "image_id": 1,
          "category_id": 1,
          "bbox": [x, y, width, height]
        }
      ]
    }
  ]
}
```

### 3. 运行程序

```bash
python main.py
```

### 4. 在GUI中配置任务

1. 选择任务类型（采集/战斗/游戏任务系统）
2. 配置任务参数
3. 点击"开始"按钮执行

## 扩展开发

### 添加新的采集资源

```python
# 在代码中调用
from src.tasks.GameQuestTask import GameQuestTask

# 假设 task 是 GameQuestTask 实例
task.add_gathering_resource(
    resource_id='special_ore',      # 对应图片模板文件名
    resource_name='稀有矿石',         # 资源名称
    minimap_marker='minimap_rare'   # 小地图标记
)
```

### 添加新的敌人目标

```python
task.add_enemy_target(
    enemy_id='enemy_special',      # 对应图片模板文件名
    enemy_name='特殊怪物',          # 敌人名称
    priority=3,                    # 优先级
    is_boss=False                  # 是否是Boss
)
```

### 创建自定义任务

```python
from src.tasks.QuestManager import QuestTask, TaskType
from src.tasks.GameQuestTask import GameTaskConfig

# 方法1: 使用GameQuestTask注册
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

# 方法2: 直接使用QuestManager
from src.tasks.QuestManager import QuestManager

quest_manager = QuestManager(game_task)

custom_task = QuestTask(
    task_id='custom_task',
    task_type=TaskType.CUSTOM,
    name='自定义任务',
    config={
        'executor': lambda: your_logic()
    }
)

quest = QuestConfig(
    quest_id='custom_quest',
    quest_name='自定义任务链',
    tasks=[custom_task]
)

quest_manager.register_quest(quest)
quest_manager.execute_quest('custom_quest')
```

## 注意事项

1. **图片模板质量**: 确保图片模板清晰，与游戏中显示的一致
2. **坐标配置**: 任务列表和小地图的位置可能需要根据你的游戏调整
3. **按键配置**: 确保游戏内按键与代码中的按键一致
4. **分辨率**: 系统支持16:9分辨率，会自动缩放
5. **性能**: 确保游戏能稳定运行在60 FPS以上

## 架构设计

### 类关系图

```
BaseTask (ok-script框架)
    ↑
    ├── MyBaseTask (包装interaction)
    │       ↑
    │       └── BaseGameTask (游戏通用功能)
    │               ↑
    │               ├── GatheringTask (采集任务)
    │               ├── CombatTask (战斗任务)
    │               └── GameQuestTask (主任务系统)
    │
    └── QuestManager (任务管理器)
```

### 设计模式

1. **策略模式**: 不同战斗模式（Auto/Defensive/Boss/Farm）
2. **工厂模式**: 任务创建和管理
3. **观察者模式**: 任务状态变化回调
4. **模板方法模式**: BaseGameTask定义通用流程

## 调试技巧

1. **启用Debug模式**: 在config.py中设置 `'debug': True`
2. **查看截图**: 检查 `screenshots/` 目录下的截图
3. **日志输出**: 查看 `logs/` 目录下的日志文件
4. **测试单个功能**: 先测试采集或战斗，再整合使用

## 常见问题

### Q: 找不到采集目标
A: 检查图片模板是否正确，threshold 是否需要调整

### Q: 无法识别战斗状态
A: 检查 `combat_hp_bar.png` 是否正确，或添加OCR检测

### Q: 移动不准确
A: 调整移动持续时间，或使用小地图导航

### Q: 技能释放不对
A: 检查技能按键配置，确保与游戏内一致

## 后续开发计划

- [ ] 支持多角色配置
- [ ] 添加更多战斗模式
- [ ] 实现自动贩卖功能
- [ ] 支持任务自动接取
- [ ] 添加路径规划系统
- [ ] 支持多开游戏

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 许可证

本项目基于 ok-script 框架开发，遵循相同的许可证。
