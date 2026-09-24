# OpenCode 适配说明（第一版）

本文说明如何使用 OpenCode 适配器及其当前证据边界。面向使用者的最短命令请先看
[README](../README.md)；这里记录配置条件和现阶段适配限制。

## 模型与凭据

本版适配器按每条用例启动隔离的 OpenCode 配置，默认显式选择
`iiis/infi/deepseek-v4.1-flash`。本机开发环境验证过 OpenCode `1.18.32`
能使用该模型；你的机器仍需配置自己的可用模型供应商端点和专用测试 Key。

OpenCode CLI 的 `opencode/big-pickle` 可以在未登录产品账号时调用；
`opencode auth list` 中没有凭据不等于模型不可用。不过，**当前测试适配器要求所选模型
已经在配置文件的 `provider` 中声明，且 `options.apiKey` 是有效的 `{env:...}` 或
`{file:...}` 引用**。所以不能仅将 `OPENCODE_TEST_MODEL` 改成
`opencode/big-pickle`，就认为当前驱动会以匿名方式运行它。

建议为测评专门准备一个 `opencode.json`，并在项目根目录 `.env` 中设置：

```dotenv
OPENCODE_TEST_CONFIG=/path/to/dedicated/opencode.json
OPENCODE_TEST_MODEL=iiis/infi/deepseek-v4.1-flash
IIIS_API_KEY=your-dedicated-test-api-key
```

下面是**不可直接使用**的示例配置；将 `baseURL` 替换为实际 IIIS 接口地址，
将 `IIIS_API_KEY` 换成仅用于测评的有效 Key。不要将密钥原文写入配置或提交到仓库：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "iiis": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "IIIS 测试供应商",
      "options": {
        "baseURL": "https://your-test-provider.example/v1",
        "apiKey": "{env:IIIS_API_KEY}"
      },
      "models": {
        "infi/deepseek-v4.1-flash": { "name": "DeepSeek V4.1 Flash" }
      }
    }
  }
}
```

也可以把 `apiKey` 写成 `{file:/absolute/path/to/dedicated-key-file}`，
密钥文件应限制访问权限。配置文件自身不能是符号链接。没有设置
`OPENCODE_TEST_CONFIG` 时，适配器会读取当前用户的
`~/.config/opencode/opencode.json` 作为供应商配置来源；正式测评建议显式使用
**专用**配置文件，以免无意中选用个人供应商或个人密钥。

测试时只会将所选 provider 的定义复制到临时配置；其他 provider、个人插件和
普通 OpenCode 会话不会作为测试配置复制。隔离配置不等同于操作系统沙箱：
目标进程仍可能访问其运行用户可访问的主机资源，测评应使用专用测试密钥和可清理的数据。

## 启动与报告

安装 OpenCode 和依赖、填写 `.env` 后，在仓库根目录运行：

```bash
opencode --version
uv sync --extra dev
uv run agent-test --agent opencode --suite all
```

默认 `--suite black_box`，完整报告需显式指定 `--suite all`。执行顺序为
冒烟门禁、黑盒、灰盒、白盒；冒烟失败时后面三卷不运行，但仍生成冒烟报告。
第一版请保持默认 `--business-workers 1`：OpenCode 的多 worker 隔离尚未实现。

每次运行的 `report.pdf`、`report.json`、各卷结果和日志位于
`artifacts/<RUN_ID>/`；可用 `--output-dir` 修改产物父目录。业务用例存在
“不通过”时退出码可以为非零，不能仅凭退出码判断是否生成了 PDF。

## 当前适配边界

- **黑盒 42 条**：只使用公开输入输出、工作区文件变化和受控工具/外部副作用等
  `PUBLIC`、`FILE`、`CONTROL` 证据，不使用抓包或重建的 Agent Trace
  作为黑盒断言依据。
- **灰盒 81 条**：使用产品运行事件、受控工具、插件 Hook 和可用的网络证据。
  抓到部分事件不代表获得了完整、可信的当前回合 Trace；缺少必要的网络请求关联、
  工具生命周期或确认证据时，不得据此判通过，按用例要求报告证据不足或不适用。
- **白盒 86 条**：W062、W066、W085、W086 已接入固定 OpenCode v1.18.32
  source-runtime Harness，其余 82 条仍为占位用例。四条结果只归属于明确登记的
  source-runtime 目标，不归属于本机 npm 安装二进制。当前实测结果为 W062/W086
  通过，W085 不通过，W066 无法判定；不通过表示真实生产路径已执行并取得有效
  不符合证据，无法判定表示仍缺少原题要求的可验证检查边界。
  逐条源码适配分析见 [白盒用例审查](opencode-whitebox-case-audit.md)。

单独运行任一已实现白盒用例需要准备固定源码树和 Bun 1.3.14：

```bash
OPENCODE_WHITEBOX_SOURCE=/path/to/opencode-v1.18.32-source \
OPENCODE_WHITEBOX_BUN=/path/to/bun-1.3.14 \
uv run pytest -q test_cases/white_box/test_w062.py --agent opencode --case-suite white_box
# 将 test_w062.py 替换为 test_w066.py、test_w085.py 或 test_w086.py 可分别执行。
```

Harness 只替换原题允许的确定性外部依赖和测试存储；被测控制、消息装配、
取消传播和任务注册代码保持源码真实实现，并把 CODE/SPY/STATE/CONTROL 证据
写入本次运行目录。

公共用例中用于放置 Agent 指令的文件优先使用 `AGENTS.md`，实际读取行为
以被测 OpenCode 版本为准。没有产品原生支持的身份、实例或服务端能力，
不应由测试环境模拟后冒称产品原生功能。
