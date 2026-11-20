# video-aspect-fit

## 题面

把 4:3 老素材适配到 16:9 后，人脸被拉宽、黑边还只在一侧：DAR 计算忽略 SAR，4:3 素材被当成 16:9；letterbox 只算缩放不算偏移，画面贴在左上角；crop 从左上角裁切，主体出画；取偶只改宽不改坐标，右边多出一列黑边；安全区 overscan 超过 0.1 不钳制，画面被切没；stretch 模式也加了黑边；SAR 换算用浮点四舍五入，宽度累计偏 1 像素；校验不查越界，矩形超出画布；批量任务共用画布矩形，任务之间互相串；dst_w=0 不校验，除零崩溃。fit/framing.py 是核心，tests/test_framing.py 15个红。要修的是：按 DAR/SAR 正确缩放并居中适配，裁切、取偶与安全区保持整数像素和边界，批量任务原子校验、失败整体回滚，让 15 条测试全部转绿。

## 运行方式

在仓库根目录执行：

```text
python -m pytest tests -q
```

初始状态必须恰好显示 `15 failed`，且没有 collection error、import error 或 syntax error。`fit/framing.py` 中的 8 个函数目前都是 `raise NotImplementedError`，需要逐个实现。

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 游戏、图形与多媒体 |
| 子方向 | 音视频处理 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

## 约束

- 仅使用 Python 标准库（`math`）与 `pytest`，离线运行，不使用随机数。
- 所有几何量均为整数像素；浮点比较容差为 `1e-6`。
- 非法参数和非法批量任务统一抛出 `FitError`。
- `tests/` 不可修改。
