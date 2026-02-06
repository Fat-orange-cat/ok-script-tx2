# 师门任务使用说明

## 任务流程

```
开始
  ↓
检查任务栏是否有"师门任务"
  ↓ 有任务
解析任务类型 (消灭/采集/交给)
  ↓
点击任务追踪前往
  ↓
根据类型执行任务
  ├─ 消灭xxx → 战斗
  ├─ 采集xxx → 采集
  └─ 交给xxx → 找NPC对话
  ↓
返回提交任务
  ↓
重复直到任务栏没有"师门任务"
  ↓
打开日程表 (快捷键L)
  ↓
下拉寻找"师门任务"
  ↓
判断状态
  ├─ "已完成" → 停止
  └─ 还亮着 → 点击"参与" → 继续
```

## 需要准备的图片模板

在 `assets/images/` 目录下准备以下图片：

### 1. 战斗相关
```
combat_hp_bar.png          # 战斗血条（用于检测是否进入战斗）
```

### 2. 采集资源（根据游戏实际）
```
ore_iron.png               # 铁矿
ore_copper.png             # 铜矿
herb_basic.png             # 基础草药
wood_basic.png             # 基础木材
# 添加游戏中的其他采集资源...
```

### 3. 日程UI
```
schedule_button.png        # 日程按钮图标
schedule_shimen_icon.png   # 日程中的师门任务图标
accept_button.png          # "参与"按钮
```

### 4. 对话框UI
```
submit_button.png          # 提交任务按钮
confirm_button.png         # 确定按钮
```

### 5. 敌人（可选，用于更精确的识别）
```
enemy_boar.png             # 野猪
enemy_wolf.png             # 狼
# 添加游戏中的其他怪物...
```

## 配置说明

### 游戏内配置

1. **日程快捷键**: 默认为 `L` 键，如果不同请修改代码第386行
2. **交互按键**: 默认为 `F` 键，在 `BaseGameTask.py` 中配置
3. **技能按键**: 在UI界面配置（格式：1-2-3-4）

### UI配置选项

运行程序后，在师门任务界面可配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| 最大任务轮数 | 防止死循环的最大执行次数 | 20 |
| 战斗时反击 | 遇到敌人是否反击 | True |
| 血量低于%逃离 | 血量阈值 | 30 |
| 任务失败重试次数 | 单个任务的最大重试次数 | 3 |
| 每次操作间隔(秒) | 操作之间的等待时间 | 1.5 |
| 日程检查间隔(秒) | 检查日程时的等待时间 | 2.0 |

## 资源名称映射

### 采集资源映射

在 `_get_resource_id_by_name()` 方法中配置：

```python
resource_mapping = {
    '铁矿': 'ore_iron',
    '铜矿': 'ore_copper',
    '草药': 'herb_basic',
    '木材': 'wood_basic',
    # 根据游戏添加更多...
}
```

### 敌人映射

在 `_get_enemy_id_by_name()` 方法中配置：

```python
enemy_mapping = {
    '野猪': 'enemy_boar',
    '狼': 'enemy_wolf',
    # 根据游戏添加更多...
}
```

## 调试技巧

### 1. 启用Debug模式

在 `src/config.py` 中设置：
```python
'debug': True,
```

### 2. 查看截图

检查 `screenshots/` 目录下的截图，确认图片匹配是否正确。

### 3. 测试单个步骤

可以注释掉部分代码，单独测试某个功能：

```python
# 只测试日程检查
# success = self._execute_task(task_info)
self._check_schedule_and_accept()
return
```

### 4. 查看日志

查看 `logs/` 目录下的日志文件，了解详细执行过程。

## 常见问题

### Q: 无法识别任务类型

**A**: 检查OCR识别是否正确，可以查看日志中的任务文字。如果识别不对，需要调整正则表达式：

```python
# 在 _parse_shimen_task() 方法中
combat_match = re.search(r'(消灭|击杀|讨伐)(.+?)(\d+)?个?', task_text)
```

### Q: 找不到采集目标

**A**:
1. 检查图片模板是否清晰
2. 确认资源名称映射是否正确
3. 尝试降低 `threshold` 值

### Q: 找不到NPC

**A**: NPC识别依赖OCR，确保：
1. 游戏中NPC名字清晰可见
2. OCR库配置正确（config.py中的ocr配置）
3. 可以添加NPC的图片模板作为补充

### Q: 日程检查不准确

**A**:
1. 确认日程按钮图标 (`schedule_button.png`) 正确
2. 调整 `日程检查间隔(秒)` 配置，给UI加载更多时间
3. 检查"参与"按钮模板 (`accept_button.png`) 是否正确

### Q: 任务一直循环不停止

**A**:
1. 检查"已完成"的OCR识别是否准确
2. 降低 `最大任务轮数` 作为保险
3. 检查任务栏中"师门"文字的识别逻辑

## 扩展功能

### 添加新的任务类型

如果需要支持其他任务类型（如"护送"），可以扩展：

```python
class TaskType(Enum):
    COMBAT = "combat"
    GATHERING = "gathering"
    DELIVERY = "delivery"
    ESCORT = "escort"  # 新增护送类型

# 在 _parse_shimen_task() 中添加解析
escort_match = re.search(r'护送(.+)', task_text)
if escort_match:
    task_type = TaskType.ESCORT
    target_name = escort_match.group(1).strip()

# 在 _execute_task() 中添加处理
elif task_info.task_type == TaskType.ESCORT:
    return self._execute_escort_task(task_info)
```

### 添加自动领取奖励

在任务完成后添加领取奖励逻辑：

```python
def _claim_rewards(self):
    """领取师门任务奖励"""
    # 查找奖励界面
    reward_button = self.find_one('reward_button')
    if reward_button:
        self.click(reward_button[0], reward_button[1])
        time.sleep(1)
```

## 性能优化建议

1. **减少OCR调用**: OCR比较耗时，可以优先使用模板匹配
2. **调整等待时间**: 根据实际网络和游戏性能调整操作间隔
3. **缓存识别结果**: 对于不会变化的UI元素可以缓存识别结果

## 安全建议

1. **设置合理的最大轮数**: 避免异常时无限循环
2. **添加随机延迟**: 模拟真人操作，避免被检测
3. **定期检查状态**: 确保角色没有死亡、卡死等异常

## 更新日志

- v1.0.0: 初始版本，支持基本的师门任务流程
