# M336 Cypress / Codex 实验包

这个目录可直接拷到 `Wellshh/Cypress` 仓库根目录，并在 `experiment` 分支交给 Codex 执行。

## 使用步骤

```bash
git checkout experiment
cp -a /path/to/m336_cypress_codex_pack/. /path/to/Cypress/
cd /path/to/Cypress
python experiments/m336/scripts/validate_manifest.py
```

从仓库根目录启动 Codex。显式选择技能：

```text
$m336-anchor-keepin-experiment
```

然后粘贴：

```text
experiments/m336/CODEX_PROMPT.md
```

或直接把该文件全文作为任务 prompt。

## 包内文件

- `AGENTS.md`：仓库级 Codex 指令
- `.agents/skills/m336-anchor-keepin-experiment/SKILL.md`：可复用技能
- `experiments/m336/SPEC.md`：完整算法与实验规格
- `experiments/m336/CODEX_GOAL.md`：耐久目标
- `experiments/m336/CODEX_PROMPT.md`：主执行 prompt
- `experiments/m336/input/m336_clusters.json`：机器可读聚类
- `experiments/m336/input/m336_geometry_summary.json`：几何摘要
- `experiments/m336/input/m336_region_assignment.seed.json`：建议区域映射，非最终真值
- `experiments/m336/input/pcb_geometry_keepin.json`：原始几何
- `experiments/m336/configs/experiment_matrix.json`：E0–E4
- `experiments/m336/configs/m336_anchor_keepin.example.json`：功能配置示例
- `experiments/m336/scripts/validate_manifest.py`：输入自检

## 重要提醒

聚类摘要声明 27 个模块，但表格只列出 25 个模块；25 行的成员总数正好是 125。包内不会虚构两个模块。Codex 必须优先搜索更完整的机器可读上游映射；找不到时，以 25 行清单进行实验并在报告中保留该数据问题。
