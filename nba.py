import os
import requests
from nba_api.stats.endpoints import scoreboardv2, boxscoretraditionalv2
from datetime import datetime

def check_for_50_points():
    """检查当日所有比赛中是否有球员得分50+"""
    try:
        # 获取当日比赛数据
        scoreboard = scoreboardv2.ScoreboardV2()
        games = scoreboard.get_data_frames()[0]  # GameHeader
        
        if games.empty:
            print("今日没有比赛")
            return
        
        print(f"检查 {len(games)} 场比赛的球员数据...")
        
        # 遍历每场比赛
        for _, game in games.iterrows():
            game_id = game['GAME_ID']
            print(f"检查比赛 {game_id}: {game['MATCHUP']}")
            
            # 获取比赛的详细统计数据
            try:
                boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
                player_stats = boxscore.get_data_frames()[0]  # PlayerStats
                
                # 检查每个球员的得分
                for _, player in player_stats.iterrows():
                    points = player['PTS']
                    player_name = player['PLAYER_NAME']
                    team_abbreviation = player['TEAM_ABBREVIATION']
                    
                    if points >= 50:
                        print(f"🔥 发现50+得分: {player_name} ({team_abbreviation}) - {points}分")
                        send_to_discord(player_name, points, team_abbreviation, game['MATCHUP'])
                        
            except Exception as e:
                print(f"获取比赛 {game_id} 数据时出错: {e}")
                continue
                
    except Exception as e:
        print(f"获取比赛数据时出错: {e}")

def send_to_discord(player, pts, team, matchup):
    """发送50+得分通知到Discord"""
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("警告: 未设置 DISCORD_WEBHOOK 环境变量")
        return
        
    data = {
        "content": "🔥 **NBA50 优惠预警!**",
        "embeds": [{
            "title": "50分记录达成！",
            "description": f"球员 **{player}** ({team}) 在今天的比赛中砍下了 **{pts}** 分！\n\n比赛: {matchup}\n\n**DoorDash NBA50** 优惠码预计将于明日 9:00 AM PT 生效！",
            "color": 16711680, # 红色
            "footer": {"text": f"由 GitHub Actions 自动监控 • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
        }]
    }
    
    try:
        response = requests.post(webhook_url, json=data)
        if response.status_code == 204:
            print(f"✅ 成功发送Discord通知: {player} {pts}分")
        else:
            print(f"❌ Discord通知发送失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 发送Discord通知时出错: {e}")

if __name__ == "__main__":
    check_for_50_points()
