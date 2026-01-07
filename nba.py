import os
import requests
from nba_api.stats.endpoints import scoreboardv2

def check_for_50_points():
    # 获取当日比赛数据
    sb = scoreboardv2.ScoreboardV2()
    # 这里简化的逻辑：实际上你需要遍历当日所有比赛的 PlayerStats
    # 为了演示，我们假设触发条件成立
    # 实际开发建议参考 nba_api 的 playergamelog 文档
    
    player_name = "Jaylen Brown" # 假设 2026/01/04 的表现
    points = 50
    
    if points >= 50:
        send_to_discord(player_name, points)

def send_to_discord(player, pts):
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    data = {
        "content": "🔥 **NBA50 优惠预警!**",
        "embeds": [{
            "title": "50分记录达成！",
            "description": f"球员 **{player}** 在今天的比赛中砍下了 **{pts}** 分。\n\n**DoorDash NBA50** 优惠码预计将于明日 9:00 AM PT 生效！",
            "color": 16711680, # 红色
            "footer": {"text": "由 GitHub Actions 自动监控"}
        }]
    }
    requests.post(webhook_url, json=data)

if __name__ == "__main__":
    check_for_50_points()
