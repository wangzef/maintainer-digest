# Maintainer Digest · 开源维护简报

**把 GitHub Issue、PR 和版本发布整理成可核查的维护周报。**

[English](README.md) · [中文报告示例](examples/report.zh-CN.md) · [参与贡献](CONTRIBUTING.md)

维护者经常需要在 Issue、PR、Release 页面之间切换，才能说明“这周发生了什么、还有哪些事项值得关注”。这个工具把这些信息汇总为 Markdown 和 JSON，并保留来源链接、统计时间范围及采集不完整的提示。

Python 3.10 及以上，运行时零第三方依赖，无需大模型或付费 AI 服务，MIT 开源。

## 快速开始

```bash
git clone https://github.com/wangzef/maintainer-digest.git
cd maintainer-digest

# 离线体验：全部是明确标注的虚构示例，无需联网或账号。
python3 -m maintainer_digest --input examples/demo-snapshot.json --lang zh

# 换成你实际维护的仓库。
python3 -m maintainer_digest --repo OWNER/REPO --days 7 --lang zh --output report.md
```

也可以在虚拟环境内通过 `python -m pip install .` 安装，再运行 `maintainer-digest`。当前尚未发布到 PyPI。

## 首版功能

- 汇总新增/关闭 Issue、新增/合并 PR，PR 合并以真实的 `merged_at` 为准。
- 列出当前长期未更新、未指派的 Issue 和非草稿开放 PR。
- 汇总范围内发布的版本，包含预发布，按发布时间筛选。
- 一次处理多个仓库，输出英文或中文 Markdown，并可导出 JSON。
- 保存 API 快照后离线重放，同一份数据可以重复生成不同语言的报告。
- 可选机器人作者过滤，支持分页、请求重试、限流提示以及不完整结果标记。
- 附带测试、CI 和只读权限的每周 GitHub Actions 报告工作流。

## 常用命令

```bash
# 多仓库
python3 -m maintainer_digest --repo pallets/flask --repo psf/requests \
  --days 7 --lang zh --output reports/weekly.md

# 固定 UTC 范围，含 10 月 15 日零点，不含 10 月 22 日零点
python3 -m maintainer_digest --repo OWNER/REPO \
  --since 2026-10-15 --until 2026-10-22 \
  --save-data snapshots/weekly.json --json-output reports/weekly.json \
  --lang zh --output reports/weekly.md

# 无网络重放；时间范围直接使用快照里的值
python3 -m maintainer_digest --input snapshots/weekly.json \
  --lang en --exclude-bots --output reports/weekly.en.md

# 大仓库：提高分页上限，不完整时用退出码 2 提醒 CI
python3 -m maintainer_digest --repo OWNER/REPO --max-pages 50 --strict
```

公开仓库可不带令牌访问，但受 GitHub 匿名请求限额影响。日常使用可设置环境变量 `GH_TOKEN` 或 `GITHUB_TOKEN`，前者优先。令牌需要目标仓库的 Issues、Pull requests 只读权限；私有仓库发布信息还需 Contents 只读权限。不要把令牌写进命令参数、仓库或报告。

完整参数表见 [英文文档](README.md#usage)。`--limit` 仅限制每段展示条数，不改变统计总数；`--max-pages` 默认每个接口最多 10 页、每页 100 条。达到分页上限会明确提示，`--strict` 会返回非零退出码。

## 自动生成周报

[Weekly digest 工作流](.github/workflows/digest.yml)可手动触发，也会在每周一 UTC 00:00（北京时间 08:00）运行，分析当前仓库。报告放在 Actions 运行摘要和附件里，不自动发 Issue、不提交文件。工作流需要本工具源码位于仓库根目录；复制到其他项目时，请一并提供源码或改为安装已审核版本。

## 统计口径

活动按 `[起点, 终点)` 的 UTC 时间戳统计；关闭 Issue 按最近一次关闭时间统计，不还原反复开启/关闭的历史。Issue 接口混入的 PR 会被排除。

“开放、未指派、长期未更新”来自采集时的当前快照，不能用于还原某天的历史待办。开放 PR 可能已被评审，这不是“等待首次评审”列表。作者数仅涵盖新增 Issue 和 PR 的作者，不代表全部贡献者。各项指标可能重叠，不能简单相加。

快照是顺序请求采集的，采集期间仓库状态可能变化；达到分页上限的报告会标记为不完整。机器人过滤按条目作者判断。v0.1 不支持 GitHub Enterprise Server、自定义 API 地址、评论时间线、首次响应时长或历史事件恢复。

工具只读取 GitHub API，不调用大模型或分析平台。Markdown 不渲染 Issue/PR 正文，但 `--save-data` 保存的原始快照可能含正文和私有仓库信息，分享前应自行检查。

这是一个新发布、需要真实使用反馈和持续维护的工具。它不承诺任何开源资助、会员赠送计划的申请资格。

## 参与维护

运行测试：`python3 -m unittest discover -s tests -v`。

欢迎提交实际使用中遇到的问题、可复现的错误和小范围改进。请勿提交虚假用户、贡献、下载量或活动记录。参见 [贡献指南](CONTRIBUTING.md)、[路线图](ROADMAP.md)、[安全说明](SECURITY.md)。

维护者：[wangzef](https://github.com/wangzef)。许可证：[MIT](LICENSE)。
