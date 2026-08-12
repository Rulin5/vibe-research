# 公网部署运行手册

## 边界

本拓扑只允许 `gateway` 暴露 80/443。API、PostgreSQL、Redis 和 ClamAV 仅加入 Compose 私有网络。验证码、短信验证和人机验证不在本发布包内。

## 首次部署

1. 将 `deploy/production.env.example` 复制为 `deploy/production.env`，替换全部 `CHANGE_ME`。数据库密码若含 URL 特殊字符，必须在 `VR_DATABASE_URL` 中做百分号编码。
2. 把目标域名写入 `VR_ALLOW_ORIGINS`；生产模式只接受 `https://` 来源。把允许的 AI API 域名写入 `VR_AI_ALLOWED_HOSTS`。
3. 将证书放到 `deploy/certs/fullchain.pem` 与 `deploy/certs/privkey.pem`，不要提交证书、私钥或生产环境文件。
4. 先备份数据库，再执行迁移：

   `docker compose --env-file deploy/production.env -f compose.production.yaml --profile migration run --rm migrate`

5. 启动：

   `docker compose --env-file deploy/production.env -f compose.production.yaml up -d --build`

6. 验证 `https://目标域名/api/health` 与 `/api/ready` 均返回 200；用一次 EICAR 测试文件验证上传被拦截，并立即删除测试文件。

## 备份与恢复

- 每日使用 `pg_dump --format=custom` 备份 PostgreSQL，并备份 `report_data` 卷；数据库元数据与报告文件必须取同一恢复点。
- 至少每季度在隔离环境执行一次恢复演练。未验证恢复前，不得把“已有备份”视为可恢复。
- Redis 只承载限流计数，不作为业务事实源；故障时公网模式会拒绝受保护请求，恢复 Redis 后自动恢复。

## 更新与回退

1. 更新前记录当前镜像摘要并完成数据库、报告卷备份。
2. 先运行 `docker compose ... build` 和迁移，再滚动重建 `api`、最后重建 `gateway`。
3. 代码回退必须确认旧版本兼容当前数据库迁移。本工作包没有破坏性迁移；若未来迁移不可逆，只能前向修复，不能虚构数据库回滚。

## 日志与事件

API 每个请求返回 `X-Request-ID`，并输出不含请求体、Cookie、API Key 的 JSON 访问日志。生产日志平台应按 `request_id` 检索，至少对 5xx、Redis 不可用、数据库不可用、ClamAV 不健康和磁盘空间不足告警。

初始告警阈值应按真实流量复核：5 分钟内 5xx 比例超过 5% 告警；就绪探针连续失败 2 次告警；数据库连接使用率超过 80%、卷使用率超过 80%、证书剩余不足 30 天告警，超过 90% 或证书不足 7 天升级为紧急告警。任何数据源 10 分钟失败率超过 20% 时停止把相关数据标记为最新，并告警数据运营人员。

事件处理顺序：冻结发布，保存请求 ID 与时间窗，确认受影响用户/数据范围，隔离故障依赖，恢复服务后核对数据库与报告文件一致性。若涉及密钥或隐私数据，立即吊销相关密钥和会话、保留脱敏审计证据，并按适用制度通知负责人和用户；不得把原始密钥复制到工单或聊天记录。

## 密钥轮换

- PostgreSQL、Redis 与系统 StepFun Key：先创建新凭据，在维护窗口更新 `deploy/production.env` 并重建 API，验证就绪与 AI 冒烟后吊销旧凭据。
- TLS：在旧证书到期前安装新证书并执行 `nginx -t`，热重载后从公网验证证书链。
- AI 凭据加密 Key 按以下顺序无损轮换：先把旧值保留到 `VR_CREDENTIAL_ENCRYPTION_KEY_PREVIOUS`，再把新随机值写入 `VR_CREDENTIAL_ENCRYPTION_KEY`；重建 API 后执行 `python rotate_ai_credentials.py`。只有命令输出 `failed=0` 且再次执行时 `rotated=0`，才可清空 previous 并再次重建 API。任一步失败都保留双 Key、恢复备份并调查，不得删除旧 Key。

## 自动化发布证据

- 隔离后端测试：`deploy/scripts/run-backend-tests.ps1`，只接受 `_test` 数据库。
- 数据库备份：`deploy/scripts/backup.ps1`；恢复演练：`deploy/scripts/restore-drill.ps1`，只接受 `_restore_test` 目标。
- HTTPS/HSTS/EICAR 演练：`deploy/scripts/verify-stack.ps1`。脚本在没有认证上传的 EICAR 400 证据时主动失败。
- 复制 `deploy/release-evidence.example.json` 为未提交的证据清单，逐项附文件并由授权责任人批准，再运行：`python deploy/scripts/check_release_gate.py --evidence <清单路径>`。退出码非零时禁止开放 DNS。
