# CONTRIBUTING — 添加新命令的规范

只把确实会重复使用的操作做成命令。开始前先读 `AGENTS.md` 的“补充脚本的原则”。

## 开发环境

```bash
uv sync --extra dev --extra plot --extra dpdata --extra structure
uv run pytest tests/       # 全部测试
uv run mfk <软件> <命令> -h  # 验证帮助
```

仓库外真实样例的回归测试见 `tests/integration/README.md`。它们不会修改原始计算文件，
需要通过 `MFK_REAL_SAMPLE_ROOT` 明确指定样例根目录。

## 添加一个命令的步骤

1. 实现放在对应软件子包：`matflowkit/<software>/<command_name>.py`，
   新软件则新建 `matflowkit/<software>/` 子包（含 `__init__.py` 和 `README.md`）。
   跨命令共享代码放 `matflowkit/common/`。
2. 在 `matflowkit/registry.py` 的对应软件组注册 callback、命令名、菜单说明和常用参数；
   `cli.py` 与 `menu.py` 会从同一份注册表生成入口，不要再单独维护两份命令列表。
3. 菜单通过 CliRunner 复用命令，禁止在菜单里另写实现。
4. 更新对应子包的 `matflowkit/<software>/README.md`（输入约定 / 参数 / 输出 / 边界）。
5. 更新根 `AGENTS.md` 的场景 → 命令路由表。
6. 配最小测试数据（放 /tmp，不进仓库）实际跑一遍验收；在 `tests/` 里补测试。

## 硬性要求

- 必须支持 `-h`（用 typer 声明参数即可获得）；
- 路径输入默认当前目录（或当前目录下的约定文件名）；
- 产出文件（图、csv 等）写到当前目录，命名固定、见名知意；
- 报错走 stderr 且退出码非零；不许编造解析不到的数据（找不到就明说）；
- 硬依赖只有 typer + numpy；其余依赖在命令内延迟导入，未安装时清晰提示；
  加新依赖前先确认无法用现有依赖解决，并声明进 `pyproject.toml` 的 extras；
- 画图类功能对 matplotlib 必须延迟导入。
- 画图使用 `matflowkit/common/plot_style.py`，默认保存 PNG。

## 提交纪律

一个命令一个 commit，message 写清命令名与用途；积累 5~10 个命令打一次 tag。
