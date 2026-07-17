# M336：Cypress 锚点引导的异形 Keep-in PCB 摆件实验规格

**目标分支：** `Wellshh/Cypress:experiment`  
**实验代号：** `m336_anchor_keepin_v1`  
**状态：** 可实施规范  
**第一阶段策略：** 固定方向、固定锚点、侧别拆分、异形区域硬约束、锚点软吸引、精确后修复  
**核心原则：** Cypress 负责连续全局优化趋势；几何预处理、投影和精确修复负责真正的区域合法性。

---

## 1. 任务定义

M336 板上已经画出了若干 **可摆件区域**。这些区域来自：

- `component_placeable_regions`
- TOP：1 个异形区域
- BOTTOM：3 个异形区域
- 边界中同时含直线和圆弧

已有聚类结果把 140 个有 refdes 的器件分成：

- 125 个聚类器件
- 15 个未聚类器件
- 输入文字宣称 27 个模块，但表格实际包含 25 行模块，且 25 行成员数之和正好为 125

本实验需要验证：

> 对每个模块，以指定锚点为参考，使模块成员在指定侧别的 keep-in 区域内合法摆放，同时尽量靠近锚点并保持同网络/同模块紧凑；相对于 Cypress 原始全局布局，区域违规必须清零，锚点距离显著下降，并控制总体 HPWL 回退。

这不是“所有器件向整个板中心收缩”，也不是“仅把区域外器件裁剪到板框”。需要同时解决：

1. 模块/网络组和锚点语义；
2. TOP/BOTTOM 分侧；
3. 异形 keep-in 的完整包含；
4. 锚点可能在 keep-in 外部；
5. 不同器件尺寸对应不同合法参考点域；
6. 连续优化与离散合法化的衔接；
7. 可复现、可量化的消融实验。

---

## 2. 成功标准

第一阶段 E4 结果必须同时满足：

1. **Keep-in 精确违规数为 0**；
2. **器件重叠数为 0**，包括 movable–movable 和 movable–fixed；
3. 锚点坐标、层、方向相对于输入保持不变，容差不超过 1 DBU；
4. 相对 E0 基线：
   - 加权平均合法锚点距离下降至少 25%；
   - P90 合法锚点距离下降至少 15%；
   - 总 HPWL 回退不超过 10%；
5. `anchor_keepin_flag=false` 时，旧流程和旧结果在测试容差内不变；
6. 至少输出三个 seed 的完整报告，或者以实际日志证明确定性运行等价；
7. 所有结果均来自真实命令和文件，不允许使用估计值替代实验结果。

---

## 3. 非目标

第一阶段不要求：

- 一次性支持任意自由旋转；
- 把所有几何运算写成 CUDA；
- 重新设计 Cypress 的整个 electric-potential 模型；
- 自动推导新的模块聚类；
- 自动移动锚点；
- 自动路由；
- 达到生产级所有 PCB 机械规则覆盖。

第一阶段先建立可验证的 M336 闭环。通用化和性能优化放在后续阶段。

---

## 4. 输入契约与已知数据

### 4.1 几何文件

期望路径：

```text
artifacts/experiments/m336/pcb_geometry_keepin.json
```

校验：

```text
size_bytes = 14091267
sha256 = a7c2c788a7df386db9f94df76bfe64a21d49f21beacb0e233ebedac75cc4ad8d
schema = pcb_geometry_lossless_v1
coordinate_encoding = integer_dbu
source_units = millimeters
dbu_per_user_unit = 10000
```

必须使用：

```text
component_placeable_regions
```

本实验不要错误读取 `keepin_place` 作为器件可摆区来源。

几何摘要：

| region_id | side | source layer | bbox, mm | tessellated area, mm² |
|---|---|---|---:|---:|
| `bottom_0` | BOTTOM | `BOARD GEOMETRY/KEBAIJIAN_BOT` | `[-10.2700, -74.0380, -1.0100, -68.4817]` | 39.183334 |
| `bottom_1` | BOTTOM | `BOARD GEOMETRY/KEBAIJIAN_BOT` | `[-15.0370, -77.9150, -9.4100, -74.7800]` | 15.853804 |
| `bottom_2` | BOTTOM | `BOARD GEOMETRY/KEBAIJIAN_BOT` | `[8.8100, -78.2750, 11.4600, -73.1644]` | 9.196065 |
| `top_0` | TOP | `BOARD GEOMETRY/KEBAIJIAN_TOP` | `[-9.5500, -71.5435, 1.8900, -64.6900]` | 31.281727 |

这些面积只用于输入诊断。最终容量和合法性必须使用器件尺寸腐蚀后的可行域，而不是原始区域面积。

### 4.2 器件记录

几何 JSON 包含：

- 146 条 symbol 记录；
- 140 条有非空 refdes；
- 6 条空 refdes 记录；
- 140 条有名器件与“125 聚类 + 15 未聚类”完全对应；
- 所有 140 条有名器件都有 `PACKAGE GEOMETRY/PLACE_BOUND_TOP` 或 `PLACE_BOUND_BOTTOM`。

必须忽略空 refdes symbol，不允许将其加入节点、聚类或指标统计。

### 4.3 聚类文件

结构化契约：

```text
docs/experiments/m336_anchor_keepin/data/m336_clusters.json
```

重要校验：

- 文字摘要：27 modules；
- 表格实际：25 modules；
- 表格成员数合计：125；
- 未聚类：15；
- 非锚点成员：100；
- 单例模块：8；
- 跨 TOP/BOTTOM 的模块：6。

实验以表格中 25 个模块为源数据，同时在所有报告中保留“27 vs 25”警告。不要猜测缺失的两个模块。

### 4.4 固定和可移动策略

为了减少混杂变量，第一阶段统一采用：

- 25 个锚点器件：固定；
- 15 个未聚类器件：固定；
- 100 个非锚点聚类成员：可移动；
- 6 个空 refdes symbol：忽略。

E0–E4 必须使用完全相同的 fixed/movable 集合。

### 4.5 跨层模块

以下模块含 TOP 和 BOTTOM 成员：

- `page_2_J201`
- `page_3_J301`
- `page_6_J601`
- `page_7_J701`
- `page_7_J702`
- `page_86_J8601`

将每个模块拆成：

```text
<module_id>__top
<module_id>__bottom
```

两个 subgroup。两个 subgroup 共用同一个物理锚点 XY，但只能选择本侧的 keep-in 区域。锚点器件本身只在其原始侧固定，不复制锚点节点。

---

## 5. 第一阶段实验假设

### H1：单纯 Cypress HPWL 不足以表达锚点约束

HPWL 只约束网络包围盒极值。一个器件在网络包围盒内部移动时，HPWL 可能不变，因此不能保证成员靠近指定锚点。

### H2：仅使用 native fence density 不足以保证异形 keep-in

连续 density 是软约束，且受 bin 分辨率影响。狭窄和带圆弧区域必须有硬投影和最终几何检查。

### H3：合法锚点目标比原始锚点距离更公平

若锚点位于 keep-in 外，器件不可能到达锚点。主要指标应使用：

\[
q_i = \Pi_{F_i}(a_g)
\]

其中：

- \(a_g\)：模块固定锚点；
- \(F_i\)：器件 \(i\) 在分配区域中的合法中心域；
- \(q_i\)：锚点投影到合法域后的目标。

主要距离：

\[
d_i^{feasible} = \|c_i-q_i\|
\]

同时保留原始物理锚点距离：

\[
d_i^{raw} = \|c_i-a_g\|
\]

### H4：锚点初始化 + 锚点损失 + 硬投影优于任何单项

预期 E3/E4 在收敛稳定性和最终紧凑度上明显优于 E1，仅增加投影不会自然得到理想的组内布局。

---

## 6. 总体算法

完整第一阶段流程：

```text
验证输入
  ↓
解析 DBU 坐标和圆弧 keep-in
  ↓
从 PLACE_BOUND 获取每个器件固定方向矩形
  ↓
按 TOP/BOTTOM 拆 subgroup
  ↓
验证/修复 subgroup → region 分配
  ↓
为每个器件构造合法中心域 F_i
  ↓
锚点投影得到 q_i
  ↓
在 q_i 附近做合法初始化
  ↓
Cypress 全局优化
  ├─ 原有 wirelength
  ├─ 原有 density / net crossing
  └─ 新增 anchor loss
  ↓ 每步 optimizer 之后
异形区域硬投影
  ↓
离散候选精确修复
  ↓
精确 polygon + footprint 合法检查
  ↓
指标、CSV、JSON、图像和消融报告
```

---
