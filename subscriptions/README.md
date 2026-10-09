# Cloudflare 私密订阅与 agent 接手指南

**Android、iPhone、MacBook 节点的维护来源是 Cloudflare。**
公开规则、构建器、Worker 和发布工具保存在本仓库；各设备节点存在 Worker 各自的
`ANDROID_CONFIG` / `IPHONE_CONFIG` / `MACBOOK_CONFIG` JSON 运行时变量中。本机 `dist/subscriptions/` 是可删除、可重建的
私密工作副本和备份，不是另一份长期维护的节点来源。

已接入以下三个设备，各有独立订阅令牌：

| `--device` | 完整配置的公共来源 | 节点配置 |
| --- | --- | --- |
| `android`（默认） | `flclash.yaml` | 现有 Android 节点，IPv6 关闭 |
| `iphone` | `clash-backcn.yaml` | iPhone Clash/Hako YAML，DMIT 使用 Vision |
| `macbook` | `clash-backcn-muse.yaml` | MacBook Muse YAML，DMIT 使用 h2mux |

这是 Clash YAML 订阅；iPhone 此入口不是 Shadowrocket 的 `.conf` 配置。
iPhone 与 MacBook 的 IPv6 跟随各自公共主配置。Windows、AVP 尚未迁移。

## 接手时先读这里

仓库根目录的两个 gitignored 文件是现有机器的凭据入口：

- `.env.cloudflare`：`CLOUDFLARE_API_TOKEN`，发布权限为当前账户的
  Workers Scripts Write / Edit。该权限覆盖账户内 Worker 脚本，不仅限一个 Worker。
- `.env.subscriptions`：账户 ID、Worker 名称、服务根地址，以及现有
  `ANDROID_SUBSCRIPTION_TOKEN`、`IPHONE_SUBSCRIPTION_TOKEN`、`MACBOOK_SUBSCRIPTION_TOKEN`。

### Google Drive 共享凭据入口

所有者已授权 agent 使用 Google Drive 插件连接的账号，在 `Agents/cloudflare` 中
读取和更新共享凭据文件，以便其他 agent 接手。使用插件账号，不要根据浏览器当前
登录账号判断目标 Drive。

- 账号：`larry@kbyshiyori.com`。
- 文件夹：[Agents/cloudflare](https://drive.google.com/drive/folders/1x-bA2cLZEgVuNoY5jeekBA9COmYl9oxJ)。
- 已上传：[.env.cloudflare](https://drive.google.com/file/d/10RMt9Yns1kj_b9sbS_5vswvx6CRN67N9/view)，
  只含 Cloudflare API 凭据；当前未上传 `.env.subscriptions`。

agent 可直接修改该文件夹内与本项目相关的共享凭据文件，不必仅为写回文件再次确认。
此授权不包括扩大 Drive 共享权限、公开文件、增加 API Token 权限，或自行删除在用设备。
读取前确认插件账号及文件父目录，下载到仓库根目录的 gitignored 文件并设置 0600；
不要打印文件内容。Cloudflare 节点配置仍以云端 JSON 变量为准。

更新已有 Drive 文件用 `update_file` 上传新内容并保留文件 ID、父目录和权限，
不要用 `upload_file` 生成同名重复文件。修改前重新读取共享文件、保留无关字段，
写回后读取元数据及文件核对结果；同一时间仅安排一个凭据维护者。
API Token 更换时同步 `.env.cloudflare`。设备增删涉及的令牌登记在 `.env.subscriptions`，
不能写进只存 API 凭据的 `.env.cloudflare`。

需要共享设备订阅令牌时，可按所有者要求首次将 `.env.subscriptions` 放入同一文件夹，
之后 agent 新增或删除设备时直接更新这份共享登记，并同步本机副本。
当前它尚未在 Drive 中，接手时必须从所有者取得现有令牌；不得假定 Drive 备份已完整。
共享文件不是自动同步服务，上传本身不会部署 Worker。

可以用 `subscriptions/.env.example` 在新环境准备第二个文件，但必须从所有者或
可信凭据管理器取得**现有**订阅令牌。API Token 可以重新授权；设备令牌不得随意重建，
否则现有手机订阅会失效。Worker 只保存其 SHA-256 哈希，不能从 Worker 还原原始令牌。
两个文件都应为 0600。不要在日志、聊天、公开 PR 或源码中打印 Token、私密 URL 或完整节点。

新 agent 所需工具：Python 3.12、Ruby/Psych（解析并校验 YAML，macOS 自带），
修改 Worker 时还需 Node.js 22 或更新版本。Python 发布器只用标准库。
不要抓取浏览器登录态来调用 API；使用上述 Token。

## 订阅架构

公开规则入口为 `https://kbyshiyori.github.io/rulesv2/` 上表列出的主配置。
服务根地址配置在 `.env.subscriptions`，当前 Worker 名称为 `rulesv2-subscriptions`。

| 路径（令牌是占位符） | 返回内容 | 用途 |
| --- | --- | --- |
| `/<device>/<token>/config.yaml` | 公共主配置 + 私密节点 provider 地址 | 客户端添加远程配置用这个 |
| `/<device>/<token>/provider.yaml` | 仅 `proxies` 节点 YAML | 内核下载节点，不用于添加完整配置 |
| `/<device>/config.yaml` | 同完整配置 | 请求头 `Authorization: Bearer <token>` |
| `/<device>/provider.yaml` | 同节点 | agent 下载时使用请求头认证 |

所有入口都鉴权，错误令牌返回 404，缺少配置变量返回 503。完整配置仅从固定的
GitHub Pages 地址抓取规则，不向 GitHub 发送设备令牌，也不跟随重定向。
规则源不可达、返回错误或格式不兼容时，完整配置返回 502；节点订阅仍独立工作。

Worker 每次完整订阅请求都抓取公共规则，注入 `type: http` provider 和
`interval: 3600`，并保持 Android 主配置和 DNS 的 IPv6 关闭。其余分组、规则、
DNS 策略及健康检查跟随公共构建结果。不要在 Worker 单独维护第二套规则列表。

- rulesv2 发布规则：GitHub Actions 构建并部署 Pages；手机下次更新完整配置获取
  新规则，需考虑 Pages/CDN 传播时间。不需要触发 Worker 重建。
- 修改节点：先从 Cloudflare 下载，修改工作文件，再执行发布命令；文件编辑不会自动部署。
- 修改 Worker：测试后用 `--deploy-code` 发布，直接使用当时云端节点，避免覆盖本地尚未发布的编辑。
- 手机中主配置刷新与 provider 刷新分开管理。每小时 provider 刷新由内核运行时执行，
  主配置自动更新间隔需要在 FlClash 中设置。

Worker 返回 `Cache-Control: private, no-store`，部署器关闭 Worker observability 和
preview URLs。订阅 URL 仍是一项读取凭据；浏览器历史、手机配置和第三方访问日志
可能保存它。不要把 URL 放入公开仓库。当前使用 workers.dev，手机所在网络的实际
可达性仍需要用户验证；可按需要另接自定义域名。

## 在 Cloudflare 后台核对和修改

Worker → Settings → Runtime variables and secrets 中，三个 `*_CONFIG` 的类型是 JSON。
普通 JSON 变量可以在后台及已授权的 Cloudflare API 中读取；不会因为改为 JSON 而
通过未鉴权的订阅请求公开。读取订阅仍需原有设备令牌，原始令牌仍只保存在本地。
Cloudflare API Token 继续保存在本地 `.env.cloudflare`，不放入运行时变量。

配置对象含两个字段：`tokenHash`（现有订阅令牌的 SHA-256）与 `provider`（节点 YAML 字符串）。
修改节点时编辑 `provider`，保留 `tokenHash`。JSON 字符串内的换行表示为 `\n`，
必须保持 JSON 和内含 YAML 都有效。后台保存并部署后，客户端下次刷新 provider 获取改动。
agent 下次修改必须先 `--pull`，以后台最新版本建立基线；旧工作副本不会自动覆盖后台更新。
Worker 兼容旧的字符串 Secret 和新的 JSON 对象，发布工具新建/更新配置都使用 JSON。
历史 Worker 版本可能仍含旧 Secret binding；当前生产版本已迁移为 JSON。

## agent 修改节点的标准流程

在仓库根目录执行：

```sh
python3.12 subscriptions/publish.py --pull
# 编辑 dist/subscriptions/android-provider.yaml，保留用户要求之外的节点。
python3.12 subscriptions/publish.py --check
python3.12 subscriptions/publish.py --publish
```

`--pull` 从已鉴权的云端 provider 下载，保存节点工作文件和基线
`dist/subscriptions/android-revision.json`。若检测到本机未发布编辑，拒绝覆盖。
文件不会打印到终端。

`--publish` 校验 YAML、节点名称唯一性，读取当前云端节点并比对下载基线，备份发布前的
云端节点，然后将 Worker 模块与选定设备的 JSON 变量一起上传。其他已部署设备的配置变量通过 `inherit` binding 保留；
遇到不认识的 binding 会拒绝部署，防止误删。
发布后核对云端与本地节点字节一致、正确令牌下载成功、错误令牌被拒绝，并独立解析
完整配置，检查 HTTP provider、规则和 IPv6 设置。仅验证成功后更新工作基线。

基线校验能拦住大多数旧副本覆盖，但不是服务端原子 compare-and-swap。
**同一时间只安排一个发布者**：在检查到上传之间仍有短暂竞态。
不要宣称多 agent 同时发布完全安全。需要并发写入时，应另设计服务端锁或事务。

现有手机 URL 不变，发布节点后用户可刷新 provider，或等待下一次自动刷新。
不需要更新 iCloud、重新导入 YAML，也不需要推送节点到 GitHub。

所有操作均可添加 `--device iphone` 或 `--device macbook`，例如：

```sh
python3.12 subscriptions/publish.py --device macbook --pull
# 编辑 dist/subscriptions/macbook-provider.yaml
python3.12 subscriptions/publish.py --device macbook --check
python3.12 subscriptions/publish.py --device macbook --publish
```

## 首次接入新设备

仅在用户要求迁移新设备时执行一次：

```sh
python3.12 subscriptions/publish.py --device iphone --bootstrap --provider /private/path/private-provider.yaml
```

源文件可为首次迁移时的 iCloud 副本。工具先确认对应配置变量不存在，校验节点，
生成独立随机设备令牌并保存到 gitignored `.env.subscriptions`，再发布和验证。
如果本地已有该设备令牌，会保留它。上传后验证失败，先恢复令牌并 `--pull` / `--verify`，
不得重建已有订阅。常规维护不再读取首次导入文件。
这次 iPhone、MacBook 迁移逐字保留原有节点，没有变更节点凭据或协议。

## 增加、删除设备与共享文件的维护

当前 CLI 仅接受 `android`、`iphone`、`macbook`，没有 `--delete` 命令。
修改 Drive 的 env 文件只是在维护凭据登记，不会自动增加路由或停用订阅。
所有者要求增删设备后，agent 应完成以下对应流程。

### 增加设备

1. 从 Cloudflare 读取现有配置；从 Drive 取得 API 凭据和已存在的共享设备登记。
   保留所有其他设备的令牌和配置。
2. 对新的设备名称，修改 `worker.mjs` 的设备映射与路由允许列表，以及 `publish.py`
   的 `DEVICES`、环境变量示例、测试和本文设备表。公共规则复用现有 Pages 配置；
   需要新平台时先完成相应公共构建。
3. 使用该设备的 `--bootstrap --provider`，只为新设备生成令牌，上传 JSON 变量并
   验证完整配置、节点、鉴权及其他设备订阅。已有设备禁止重新 bootstrap。
4. 如 Drive 中已有 `.env.subscriptions`，将新增的 `<DEVICE>_SUBSCRIPTION_TOKEN`
   合并写回原文件；不存在时按所有者要求建立共享登记。核对原有令牌未改变，
   提供私密完整订阅地址，提交公开代码与文档改动。

### 删除设备

1. 确认用户要求停用的设备；下载当前云端配置和共享登记，保存私密恢复备份。
2. 将目标设备从 Worker 路由和设备映射、发布器 `DEVICES`、env 示例、测试与文档移除。
   部署时同时移除该设备的 CONFIG binding，保留所有其他设备的当前 binding。
   当前部署器会拒绝未知 binding；必须为移除操作设计明确的处理，不能通过忽略检查
   或用一个缺少其他设备 binding 的上传来删除设备。
3. 验证已删除设备的原 provider/config URL 返回 404，剩余设备正常。
   再从本机及 Drive 中已有的 `.env.subscriptions` 移除该设备令牌条目，保留其他字段。
   `.env.cloudflare` 通常无需变化，因为 API 凭据按账户管理。
4. 正常更新原共享文件即可；保留恢复备份，不顺带删除 Drive 文件夹或其他设备文件。
   旧 Worker 版本/私密备份可能仍含旧凭据，回滚时应核对停用设备不会被重新启用。

## Worker 代码更新

```sh
node --test subscriptions/test_worker.mjs
python3.12 -m unittest discover -s subscriptions -p 'test_*.py'
python3.12 subscriptions/publish.py --deploy-code
```

这个命令使用云端最新节点，不读取工作节点文件、不修改节点编辑基线、不访问 iCloud。
API 更新是部署步骤，修改 GitHub 代码本身不会自动部署 Worker。
工作流 `test-subscriptions.yml` 只测试公开代码，不持有 Cloudflare Token，也不发布节点。
规则 Pages 构建保持原有工作流。

Cloudflare Worker fetch 必须用 `redirect: manual` 并自行拒绝非成功状态，不能用
`redirect: error`（Cloudflare 不支持）。验证请求采用 Mihomo User-Agent，因为当前
Cloudflare 在测试中拒绝 Python 默认请求头。兼容日期固定为已经支持的
`2025-01-01`，不要未经验证改成未来日期。

## 验证、冲突和恢复

```sh
# 不上传，验证工作文件是否已经与云端一致，并检查完整主配置。
python3.12 subscriptions/publish.py --verify

# 只有明确要舍弃未发布编辑时使用；先备份再覆盖工作副本。
python3.12 subscriptions/publish.py --pull --discard-local
```

- 发布报告失败不代表上传未发生。先运行 `--verify`；若成功，工作基线会恢复。
  不要立即重复上传旧副本。
- 云端基线变化：停止发布，保留本机编辑，拉取新版本再合并用户所需修改。
- 回滚节点：先 `--pull` 建立当前基线，把选定私密备份复制到工作文件，校验后
  `--publish`；不要绕过基线检查。
- 缺少 Token：交由所有者从可信凭据备份恢复，不要创建新设备令牌自动替换。
- 首次接入见上节；`--bootstrap` 会拒绝覆盖已经存在的设备。

所有私密输出都在 gitignored 的 `dist/subscriptions/`，权限为 0600：

| 文件 | 内容 |
| --- | --- |
| `android-provider.yaml` | 从云端下载、供编辑的节点工作文件 |
| `android-revision.json` | 目标服务和节点内容的基线哈希 |
| `android-config-url.txt` | 手机应订阅的完整配置 URL |
| `android-url.txt` | 仅节点的 URL，兼容最初的文件名 |
| `flclash.yaml` | 已验证完整配置的私密快照 |
| `backups/*-android-provider.yaml` | 带时间戳的节点备份 |

备份含凭据，避免复制到跟踪文件中，也不要在 diff/日志中展示备份全文。
iPhone、MacBook 对应输出使用 `iphone-`、`macbook-` 前缀；完整快照分别为
`clash-backcn.yaml`、`clash-backcn-muse.yaml`。所有客户端导入 `*-config-url.txt` 内的地址。
原有 iCloud 文件和最初的备份保留作历史副本；维护流程已不依赖它们。

服务端部署后已验证三个设备的节点字节一致、完整配置可解析、鉴权和令牌隔离。
客户端的实际导入和联网仍需在对应设备验证。
