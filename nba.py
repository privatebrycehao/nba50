import os
import requests
from nba_api.stats.endpoints import scoreboardv2, boxscoretraditionalv2
from datetime import datetime

def check_for_50_points():
    """检查当日所有比赛中是否有球员得分50+"""
    # 发送启动通知
    print("🤖 NBA50监控程序启动...")
    send_to_discord(message_type="startup")
    
    found_50_points = False
    
    try:
        # 获取当日比赛数据
        scoreboard = scoreboardv2.ScoreboardV2()
        games = scoreboard.get_data_frames()[0]  # GameHeader
        
        if games.empty:
            print("今日没有比赛")
            send_to_discord(message_type="no_games")
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
                        send_to_discord(player_name, points, team_abbreviation, game['MATCHUP'], "50_points")
                        found_50_points = True
                        
            except Exception as e:
                print(f"获取比赛 {game_id} 数据时出错: {e}")
                continue
        
        # 如果没有发现50+得分，发送完成通知
        if not found_50_points:
            print("✅ 监控完成，未发现50+得分")
            send_to_discord(message_type="no_50_points")
                
    except Exception as e:
        print(f"获取比赛数据时出错: {e}")
        # 发送错误通知
        send_to_discord(message_type="error")

def send_to_discord(player=None, pts=None, team=None, matchup=None, message_type="50_points"):
    """发送通知到Discord"""
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("警告: 未设置 DISCORD_WEBHOOK 环境变量")
        return
    
    if message_type == "startup":
        # 启动通知
        data = {
            "content": "🤖 **NBA50监控启动**",
            "embeds": [{
                "title": "NBA50分监控程序已启动",
                "description": f"开始检查今日NBA比赛中的50+得分情况...\n\n⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "color": 3447003, # 蓝色
                "footer": {"text": "由 GitHub Actions 自动运行"}
            }]
        }
    elif message_type == "no_games":
        # 无比赛通知
        data = {
            "content": "📅 **今日无NBA比赛**",
            "embeds": [{
                "title": "监控完成",
                "description": f"今日没有NBA比赛安排\n\n⏰ 检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "color": 10197915, # 灰色
                "footer": {"text": "由 GitHub Actions 自动监控"}
            }]
        }
    elif message_type == "no_50_points":
        # 无50+得分通知
        data = {
            "content": "📊 **今日监控完成**",
            "embeds": [{
                "title": "未发现50+得分",
                "description": f"已检查完今日所有比赛，暂无球员得分达到50+\n\n⏰ 检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "color": 15844367, # 金色
                "footer": {"text": "由 GitHub Actions 自动监控"}
            }]
        }
    elif message_type == "error":
        # 错误通知
        data = {
            "content": "⚠️ **监控程序遇到错误**",
            "embeds": [{
                "title": "程序执行异常",
                "description": f"NBA50监控程序在运行时遇到错误，请检查日志\n\n⏰ 错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "color": 15158332, # 红色
                "footer": {"text": "由 GitHub Actions 自动监控"}
            }]
        }
    else:
        # 50+得分通知
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
            if message_type == "startup":
                print("✅ 成功发送启动通知")
            elif message_type == "50_points":
                print(f"✅ 成功发送Discord通知: {player} {pts}分")
            else:
                print("✅ 成功发送监控完成通知")
        else:
            print(f"❌ Discord通知发送失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 发送Discord通知时出错: {e}")

if __name__ == "__main__":
    check_for_50_points()
