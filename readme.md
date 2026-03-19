# Grok 账号批量自动注册工具

基于 [grok-register](https://github.com/ReinerBRO/grok-register?tab=readme-ov-file) 针对个人环境适应性改进的 Grok (x.ai) 账号自动注册脚本。

## 特性

- **自动注册**: 全自动完成邮箱填写、验证码接收、资料设置及 Turnstile 绕过。
- **拟人化邮箱**: 自动生成拟人化的邮箱前缀（如 `firstname` + `lastname` + `year`），不包含特殊符号，确保与 API 完美兼容。
- **多域名支持**: 支持配置多个邮箱域名，注册时随机选择，降低单一域名被封禁的风险。
- **验证码处理**: 自动提取并自动填写 6 位数字或 `XXX-XXX` 格式验证码。
- **Token 同步**: 注册成功后自动将 SSO Token 推送到 [grok2api](https://github.com/chenyme/grok2api) 管理后台（使用新的 `/append` 接口）。
- **指纹伪装**: 模拟 Safari/Chrome 浏览器指纹，降低被风控风险。
- **环境适配**: 支持 macOS/Windows 桌面运行，以及 Linux 无头服务器运行 (自动启用 Xvfb)。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

*Linux 环境可能还需要安装 `xvfb`。*

### 2. 配置环境变量

将 `.env.example` 复制为 `.env` 并填写相关配置：

```bash
cp .env.example .env
```

**关键配置项说明：**

| 变量名 | 必填 | 说明 |
|------|------|------|
| `RUN_COUNT` | 否 | 默认执行轮数（`0` 为无限循环），默认 `10` |
| `BROWSER_PROXY` | **是** | 浏览器科学上网代理（如 `http://127.0.0.1:7890`），注册 x.ai 必须 |
| `PROXY` | 否 | 邮件 API 请求代理，若 API 无法直连则需填写 |
| `GROK2API_ENDPOINT` | 否 | 你的 grok2api 管理后台地址（如 `https://api.example.com`） |
| `GROK2API_TOKEN` | 否 | grok2api 的 `app_key` |
| `TEMP_MAIL_BASE` | **是** | 临时邮箱 API 基础地址 |
| `TEMP_MAIL_ADMIN_PASSWORD` | **是** | 临时邮箱管理后台配置的 `x-admin-auth` 密码 |
| `TEMP_MAIL_DOMAINS` | **是** | 允许使用的邮箱域名列表，多个请用英文逗号分隔 |
| `SKIP_NET_CHECK` | 否 | 是否跳过网络连通性检查（`1`: 是, `0`: 否），默认 `1` |

### 3. 运行脚本

```bash
# 默认运行
python grok_register.py

# 指定注册 5 轮
python grok_register.py --count 5
```

## 输出说明

- **SSO Token**: 自动保存到 `sso/` 目录下，每行一个。
- **运行日志**: 记录在 `logs/` 目录下，包含每轮注册的邮箱、密码及结果。

## 项目结构

- `grok_register.py`: 主程序，负责浏览器自动化流程。
- `email_manager.py`: 邮箱管理模块，负责创建邮箱和查询验证码。
- `turnstilePatch/`: 浏览器扩展，用于修复 CDP 指纹以绕过验证码。
- `.env`: 统一配置文件（不入库）。

## 安全提示

请确保不要将包含真实密码和 Token 的 `.env` 文件提交到代码仓库。本项目已默认在 `.gitignore` 中忽略 `.env`。

## 致谢

- [grok-register](https://github.com/ReinerBRO/grok-register) — 原始项目
- [cloudflare_temp_email](https://github.com/dreamhunter2333/cloudflare_temp_email) — 临时邮箱 API 原始项目
- [grok2api](https://github.com/chenyme/grok2api) — Grok API 代理项目
- [DrissionPage](https://github.com/g1879/DrissionPage) — 核心自动化框架

