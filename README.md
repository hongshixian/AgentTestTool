# AgentTestTool

AgentTestTool 是一个面向 Agent CLI 产品的自动化测评工具。它可以运行真实的被测
Agent，执行标准化测试用例，并自动生成结构化结果和 PDF 测评报告。

当前支持腾讯 **CodeBuddy Code CLI** 和 **OpenCode CLI**。CodeBuddy 默认使用 `hy3`；
OpenCode 默认使用配置好的 `iiis/infi/deepseek-v4.1-flash`。

## 主要功能

- 运行真实 Agent CLI 和真实网络服务。
- 在业务测试前执行冒烟门禁，确认 CLI 安装、认证和基础交互可用。
- 支持黑盒、灰盒、白盒三套测评卷。
- 使用“通过、不通过、不适用、无法判定”四态记录测试结论。
- 自动生成 PDF 报告、JSON 结果和运行日志。

当前用例规模：

| 测评卷 | 用例数量 | 说明 |
| --- | ---: | --- |
| 黑盒测试 | 42 | 根据用户可观察的输入、输出和外部行为进行判断 |
| 灰盒测试 | 81 | 结合更丰富的 Agent 执行证据进行判断 |
| 白盒测试 | 86 | W062、W066、W085、W086 已接入固定 OpenCode 源码 Harness，其余用例按能力就绪情况记录 |

## 快速开始

### 1. 准备环境

使用前请准备：

- Python 3.11 或更高版本；
- `uv`；
- 已安装的目标 CLI：`codebuddy` 或 `opencode`；
- 可调用的测试模型；CodeBuddy 需要已登录的专用测试账号，OpenCode 默认使用配置了 API Key 的 IIIS 模型；
- 执行灰盒测试或完整三套卷时可用的 Judge API。

请使用专用测试账号和可清理的测试数据，不要使用个人账号或生产账号。

### 2. 安装依赖

在项目根目录执行：

```bash
uv sync --extra dev
```

### 3. 配置测试环境

复制环境变量示例：

```bash
cp .env.example .env
```

根据实际环境填写 Judge API：

```dotenv
JUDGE_API_URL=https://your-judge-api.example.com
JUDGE_API_KEY=your-api-key
JUDGE_MODEL_NAME=your-model-name
```

使用 CodeBuddy 时，如果需要使用独立的测试账号配置目录，可以设置：

```dotenv
CODEBUDDY_CONFIG_DIR=/path/to/codebuddy-test-profile
```

该目录应当已经通过 CodeBuddy 官方登录流程完成认证。

使用 OpenCode 时，请设置独立的模型供应商配置文件；该文件中的 API Key 应引用环境变量或
密钥文件，不要直接写入配置正文：

```dotenv
OPENCODE_TEST_CONFIG=/path/to/dedicated/opencode.json
OPENCODE_TEST_MODEL=iiis/infi/deepseek-v4.1-flash
IIIS_API_KEY=your-dedicated-test-api-key
```

具体配置格式见 [OpenCode 使用说明](docs/opencode-adapter.md)。使用默认 IIIS 模型无需
登录 OpenCode 账号，但需要可用的供应商 API Key。其他可选配置请参考 `.env.example`。
不要将 `.env`、密钥文件或真实账号配置提交到 Git 仓库。

确认被测 CLI 已安装并能够正常启动，例如：

```bash
codebuddy --version
opencode --version
```

### 4. 运行测评

默认执行冒烟测试和黑盒卷：

```bash
uv run agent-test --agent codebuddy
```

按测评卷执行：

```bash
# 黑盒测试
uv run agent-test --agent codebuddy --suite black_box

# 灰盒测试
uv run agent-test --agent codebuddy --suite grey_box

# 白盒测试
uv run agent-test --agent codebuddy --suite white_box

# 冒烟通过后依次执行黑盒、灰盒和白盒，生成完整报告
uv run agent-test --agent codebuddy --suite all
```

运行 OpenCode 的完整三套卷：

```bash
uv run agent-test --agent opencode --suite all
```

完整测评会调用真实 Agent 和真实网络服务，可能需要较长时间。运行期间请保持账号、网络和
Judge API 可用。

## 常用参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--suite` | `black_box` | 选择 `all`、`black_box`、`grey_box` 或 `white_box` |
| `--agent` | `codebuddy` | 选择 `codebuddy` 或 `opencode` |
| `--output-dir` | `artifacts` | 设置运行产物父目录 |
| `--repeat` | `1` | 设置业务测试重复次数 |
| `--business-workers` | `1` | 设置单卷业务测试的 worker 数量，可选 1 至 4 |
| `--smoke-timeout` | `900` | 设置冒烟阶段总超时，单位为秒 |
| `--business-timeout` | `86400` | 设置业务阶段总超时，单位为秒 |
| `--business-manifest` | 无 | 只运行清单列出的单卷用例，不能与 `--suite all` 同用 |

例如，使用四个 worker 执行灰盒卷：

```bash
uv run agent-test \
  --agent codebuddy \
  --suite grey_box \
  --business-workers 4
```

CodeBuddy 并行执行前必须配置已认证的 `CODEBUDDY_CONFIG_DIR`。`--suite all` 会依次执行三套卷，不会跨卷并行。
OpenCode 首版建议使用默认的单 worker 执行。

查看完整命令帮助：

```bash
uv run agent-test --help
```

## 查看报告

每次运行会在以下目录创建独立产物：

```text
artifacts/<RUN_ID>/
```

主要文件包括：

| 文件 | 内容 |
| --- | --- |
| `report.pdf` | 用于阅读和交付的 PDF 测评报告 |
| `report.json` | 完整结构化测评结果 |
| `smoke-results.json` | 冒烟测试结果 |
| `business*.json` | 业务测试及各测评卷的结构化结果 |
| `*.stdout.log` / `*.stderr.log` | 各执行阶段的控制台日志 |

完整 PDF 报告包含冒烟测试、黑盒测试、灰盒测试和白盒测试，各测评卷分别展示总体结果和
用例详情。

冒烟测试必须全部通过，工具才会继续执行业务测试。冒烟未通过时仍会生成冒烟报告；业务
测试中存在“不通过”时，命令会返回非零退出码，但仍会正常生成报告。

## 结果状态

| 状态 | 含义 |
| --- | --- |
| 通过 | 用例执行完成，结果满足判定要求 |
| 不通过 | 被测行为不满足要求，或执行过程中发生错误 |
| 不适用 | 当前产品或测试条件不具备用例所需能力 |
| 无法判定 | 操作已经执行，但现有证据不足以形成结论 |

## 使用注意事项

- 请确保测试账号具有足够的模型调用额度。
- OpenCode 白盒卷目前已实现 W062、W066、W085、W086；其余 82 条仍为占位状态。当前固定源码目标上 W062/W086 通过，W085 不通过，W066 无法判定。运行参数和证据边界见 [OpenCode 使用说明](docs/opencode-adapter.md)。
- 不要在测试工作区放置个人文件、生产凭据或无法恢复的数据。
- `.env`、访问令牌、账号配置、会话数据和运行产物不应提交到代码仓库。
- 并行执行会增加账号和外部服务压力，建议先使用默认串行模式验证环境。
