# 文献知识库实施指南

## 一、先回答你的核心问题

第一阶段就是先把这 100 篇跑通，然后把同一套脚本复制到你们组的电脑上批处理。
但要先做试点验证，不要直接上 1 万篇。

完整流程应该是：

`原始 PDF -> 扫描建档 -> 去重 -> 规范命名 -> 文本抽取/OCR -> 分类打标签 -> 切块 -> 向量检索/RAG -> 本地模型问答`

## 二、为什么先做试点

这 100 篇试点不是为了少做，而是为了把规则定下来。

它会帮你回答这些问题：

1. 扫描件占比多少。
2. 文献类型混杂到什么程度。
3. 命名规则怎么定最稳。
4. 哪些标签适合你们研究所。
5. 哪些字段值得提取。
6. 哪些环节要人工审核。

## 三、脚本和 Web 怎么分工

第一阶段优先脚本，不优先 Web。

原因：

1. 你们当前重点是批处理。
2. 规则还会变，先做 Web 容易反复返工。
3. 研究所内网环境通常更适合离线脚本。
4. 数据清洗价值高于界面。

后面规则稳定后再加 Web，专门做：

1. 重复件审核
2. 标题修正
3. 分类修正
4. OCR 结果审核
5. 搜索与问答

## 四、GROBID 到底适不适合你们

GROBID 是专业的学术 PDF 结构化提取工具，确实常用。

它主要擅长：

1. 题名
2. 作者
3. 单位
4. 摘要
5. 参考文献
6. 章节结构

但你要把它放对位置：

1. 它不是 OCR。
2. 它更适合学术论文，不是所有 PDF。
3. 对标准、专利、宣传册、内部资料，规则抽取常常更稳。

结论：

对你们来说，GROBID 是增强模块，不是总方案。

## 五、当前这套脚本做了什么

目录：

`D:\测试文献\literature_kb_pipeline`

### `scan_manifest.py`

负责：

1. 扫描 PDF
2. 计算 SHA256
3. 读取页数
4. 抽取前几页文本
5. 判断是否疑似扫描件
6. 猜测题名、年份、文献类型

输出：

- `work/manifest/manifest.csv`
- `work/manifest/manifest.jsonl`
- `work/manifest/summary.json`

### `dedupe_rename.py`

负责：

1. 精确去重
2. 为每组重复件选主副本
3. 生成规范命名
4. 输出复制计划

输出：

- `work/dedupe/dedupe_plan.csv`
- `work/dedupe/rename_map.csv`

默认不会改原文件。

### `extract_classify.py`

负责：

1. 抽取全文文本
2. 输出纯文本
3. 关键词分类
4. 生成结构化记录
5. 按块切分文本
6. 生成 OCR 队列

输出：

- `work/text/*.txt`
- `work/extract/structured_records.csv`
- `work/extract/ocr_queue.csv`
- `work/chunks/chunks.jsonl`

## 六、你现在怎么跑

### 1. 第一次安全试跑

```powershell
cd D:\测试文献\literature_kb_pipeline
powershell -ExecutionPolicy Bypass -File .\run_pipeline.ps1
```

这次不会复制规范命名文件，只会出计划和结果。

### 2. 重点看哪些文件

1. `work/manifest/manifest.csv`
2. `work/dedupe/dedupe_plan.csv`
3. `work/dedupe/rename_map.csv`
4. `work/extract/structured_records.csv`
5. `work/extract/ocr_queue.csv`

### 3. 确认后再正式复制主副本

```powershell
powershell -ExecutionPolicy Bypass -File .\run_pipeline.ps1 -ApplyRename
```

复制后的主副本会进入：

`normalized\<文献类型>\`

原始 PDF 不会被修改。

## 七、你们组电脑怎么部署

最简单的做法：

1. 把 `literature_kb_pipeline` 整个文件夹复制过去
2. 打开 `config/settings.json`
3. 修改 `source_dir`
4. 运行 `run_pipeline.ps1`

建议统一环境：

1. Windows 10/11
2. Python 3.11+
3. `pdftotext`
4. 后续可选 `Tesseract` 或 `PaddleOCR`
5. 如要用 GROBID，再装 Java

## 八、OCR 后面怎么补

当前脚本已经会先生成：

`work/extract/ocr_queue.csv`

也就是疑似扫描件名单。

后面你们只需要再补一个 OCR 脚本：

1. 读取 `ocr_queue.csv`
2. 对 PDF 转图
3. 执行 OCR
4. 输出 OCR 文本
5. 把 OCR 文本并回结构化记录

建议原则：

1. 只有扫描件进 OCR 队列
2. OCR 后再切块
3. OCR 与原始抽取结果都保留

## 九、材料研究所最值得抽什么

比“文献管理”更重要的是“材料知识抽取”。

建议优先抽这些字段：

1. 合金牌号和成分
2. 工艺路线
3. 热处理制度
4. 变形参数
5. 表面处理参数
6. 组织特征
7. 力学性能
8. 耐蚀/疲劳/耐热/抗弹结果
9. 结论与机理

你们以后最有价值的问题通常是：

1. 某元素添加后组织和性能如何变化。
2. 某工艺窗口下强塑性如何变化。
3. 某防护材料在抗侵彻条件下规律如何。

## 十、下一步最合理

建议先做这 4 件事：

1. 运行这套试点脚本
2. 看 `ocr_queue.csv` 判断扫描件比例
3. 看 `rename_map.csv` 修命名规则
4. 把你们自己的分类标签和命名习惯告诉我

这样第二轮我就可以继续帮你把：

1. OCR 批处理
2. 近重复识别
3. GROBID 接口接入
4. SQLite 入库
5. 本地问答/RAG

继续往下补。
