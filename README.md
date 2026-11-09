# nba50

NBA 50 分监控：检查 ESPN 上当天和前一天的 NBA 比赛，发现球员单场得分达到 50 分时，推送 DoorDash NBA50 优惠预警到 Discord 或飞书（Lark）。没有 50+ 得分时也会发送当日比赛摘要，同一条预警不会重复发送。

欧洲足球日报已移到 [football-daily](https://github.com/privatebrycehao/football-daily)。

## 运行

本地运行：

```bash
pip install -r requirements.txt
export DISCORD_WEBHOOK=...
python nba.py
```

线上由 GitHub Actions（`.github/workflows/nba_monitor.yml`）每天 UTC 02:00、04:00、07:00 自动运行，也可以在 Actions 页面手动触发。

运行测试：

```bash
ruff check .
python -m unittest discover -s tests
```

## Secrets

在仓库的 Settings → Secrets and variables → Actions 中配置：

| 名称 | 说明 |
| --- | --- |
| `DISCORD_WEBHOOK` | 接收通知的 webhook 地址，支持 Discord 和飞书（Lark） |
