# TCCT 绘图规范

所有 Matplotlib 图先调用：

```python
from tcct.common.plot_style import apply_plot_style, figure_size, save_figure

apply_plot_style()
fig, ax = plt.subplots(figsize=figure_size("single", 0.72))
# plot ...
save_figure(fig, "figure.png")
```

## 固定规则

- 字体：Times New Roman；没有时依次使用 Times、Liberation Serif、DejaVu Serif。
- 字号：正文和坐标轴 8 pt，刻度和图例 7 pt，面板编号 9 pt 粗体。
- 图宽：单栏 89 mm，双栏 183 mm。用 `figure_size()` 设置。
- 坐标轴：线宽 0.8 pt；去掉上、右边框；刻度向外；默认不画网格。
- 线与点：线宽 1.3 pt，marker 4 pt。类别较多时同时改变线型或 marker。
- 图例：无边框。能直接标注时不用图例；多面板尽量共用一个图例。
- 面板编号：小写粗体 `a`, `b`, `c`，位于左上角；使用 `add_panel_labels()`。
- 背景：白色。普通数据图不使用渐变、阴影、3D 效果或装饰性边框。
- 坐标名：句首字母大写，单位放圆括号中，如 `Time (ps)`、`Energy (eV)`。

## 颜色

默认使用 Okabe–Ito 色盲友好色板。颜色从 `COLORS` 或 `COLOR_CYCLE` 取，不在命令中另建色板。

| 名称 | 色值 | 用途 |
| --- | --- | --- |
| blue | `#0072B2` | 主数据 |
| orange | `#E69F00` | 第二组数据 |
| green | `#009E73` | 第三组数据、正向状态 |
| red | `#D55E00` | 对比组、警示 |
| sky | `#56B4E9` | 辅助数据 |
| purple | `#CC79A7` | 辅助数据 |
| gray | `#767676` | 参考线和次要文字 |

- 连续数据：`viridis` 或 `cividis`。
- 有正负中心的数据：`RdBu_r`，并明确设置中心值。
- 禁止 `jet`、`rainbow` 和仅靠红/绿区分类别。

## 输出

- 默认只保存 PNG，分辨率为 300 dpi；线条密集或投稿要求时使用 600 dpi。
- 不自动生成 PDF、SVG 或 JPEG。
- 保存后关闭 figure；统一调用 `save_figure()`。

## 数据表达

- 柱状图的数值轴原则上从 0 开始；不从 0 开始时要能说明理由。
- 有重复实验时显示散点，并说明误差条是 SD、SEM 还是 CI。
- 不使用双 Y 轴，除非两个量之间的对应关系确实是图的结论。
- 多面板中每个面板应提供不同证据，避免同一数据换一种图重复展示。
