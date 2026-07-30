# MatFlowKit

个人科研工具箱（分子动力学 / 第一性原理计算方向），覆盖 **ABACUS / DeePMD / GPUMD**
三条工作线的前处理 → 过程分析 → 后处理。设计借鉴 GPUMDkit：单一入口 `mfk` +
子命令分发，支持**命令行直跑**和**交互式菜单**两种模式。

## 安装

```bash
cd MatFlowKit
pip install -e .
```

依赖：`typer`、`numpy`（`matplotlib` 可选，仅画图时需要，未安装时会自动降级为保存 csv）。

## 命令行模式

```bash
mfk --help                       # 总览
mfk abacus check-relax ./run     # 检查 ABACUS relax 是否收敛、离子步数、总能、最大力
mfk deepmd stat ./data           # 统计 DeePMD 数据集（system/frame/元素/能量/力范围）
mfk deepmd stat ./data --json    # 机器可读 JSON 输出
mfk gpumd thermo thermo.out      # 统计 thermo.out 各列
mfk gpumd thermo --plot          # 同时画第 1 列（温度）演化，保存 thermo_col1.png
```

所有命令的路径参数都默认为当前目录（或当前目录下的默认文件），支持 `-h` 查看帮助。

## 交互模式

直接运行 `mfk`（不带任何参数）进入交互菜单：

```
$ mfk
  ... banner ...
请选择软件:
  1) ABACUS
  2) DeePMD
  3) GPUMD
  0) Exit
> 3
[GPUMD] 可用命令:
  1) thermo         分析 thermo.out 各列统计，可选画图
  0) 返回
> 1
[GPUMD -> thermo] 请依次输入参数（回车使用默认值，q 取消）:
  thermo 文件 [thermo.out]:
  是否画第 1 列曲线 (y/n) [n]: y
等价命令: mfk gpumd thermo thermo.out --plot
```

菜单不实现任何独立逻辑：收集参数后打印等价命令，然后调用同一个 typer app 执行。
任何时候输入 `q` 或 `0` 返回上级 / 退出。

## 目录结构

```
MatFlowKit/
├── mdkit/              # Python 包（命令实现）
│   ├── cli.py          #   typer 入口与子命令注册
│   ├── menu.py         #   交互式菜单
│   ├── abacus/         #   ABACUS 相关命令
│   ├── deepmd/         #   DeePMD 相关命令
│   ├── gpumd/          #   GPUMD 相关命令
│   └── common/         #   跨命令共享代码
├── workflow/           # 串联多条 mfk 命令的流程脚本
├── knowledge/          # 给 AI / 人看的经验文档
└── examples/           # 命令使用案例
```

## 如何添加新命令

以给 GPUMD 加一个 `plot-thermo` 命令为例：

1. 在对应软件子包（如 `mdkit/gpumd/`）新建 `plot_thermo.py`，实现一个普通函数，
   用 `typer.Argument` / `typer.Option` 声明参数；路径参数默认值给当前目录 / 默认文件名。
2. 在 `mdkit/cli.py` 中 import 并注册：`gpumd_app.command("plot-thermo")(plot_thermo)`。
3. 在 `mdkit/menu.py` 的 `MENU` 对应软件条目里追加一行（命令名、一句话说明、参数列表）。
4. 运行 `mfk gpumd plot-thermo -h` 确认帮助正常。

规范：命令必须支持 `-h`；输入默认当前目录；产生的输出文件（图片、csv 等）写到当前目录；
报错信息写 stderr 并以非零退出码退出。详见 `AGENTS.md`。
