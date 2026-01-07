import os
import requests
import time
from nba_api.stats.endpoints import scoreboardv2, boxscoretraditionalv2
from datetime import datetime

# 设置NBA API的请求头，避免被识别为爬虫
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://www.nba.com/'
}

def get_scoreboard_with_retry(max_retries=3, delay=5):
    """带重试机制获取比赛数据"""
    for attempt in range(max_retries):
        try:
            print(f"尝试获取比赛数据 (第{attempt + 1}次)...")
            # 设置更长的超时时间
            scoreboard = scoreboardv2.ScoreboardV2(timeout=60, headers=headers)
            return scoreboard
        except Exception as e:
            print(f"第{attempt + 1}次尝试失败: {e}")
            if attempt < max_retries - 1:
                print(f"等待{delay}秒后重试...")
                time.sleep(delay)
            else:
                raise e

def get_boxscore_with_retry(game_id, max_retries=3, delay=3):
    """带重试机制获取比赛详细数据"""
    for attempt in range(max_retries):
        try:
            print(f"  获取比赛 {game_id} 数据 (第{attempt + 1}次)...")
            boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id, timeout=60, headers=headers)
            return boxscore
        except Exception as e:
            print(f"  第{attempt + 1}次尝试失败: {e}")
            if attempt < max_retries - 1:
                print(f"  等待{delay}秒后重试...")
                time.sleep(delay)
            else:
                raise e

def detect_webhook_type(webhook_url):
    """检测webhook类型"""
    if "discord" in webhook_url.lower():
        return "discord"
    elif "larksuite.com" in webhook_url.lower() or "feishu" in webhook_url.lower():
        return "lark"
    else:
        return "unknown"

def create_lark_message(title, content, color="green"):
    """创建飞书消息格式"""
    color_map = {
        "green": "green",
        "red": "red", 
        "blue": "blue",
        "yellow": "yellow",
        "grey": "grey"
    }
    
    return {
        "msg_type": "interactive",
        "card": {
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": f"**{title}**\n\n{content}",
                        "tag": "lark_md"
                    }
                }
            ],
            "header": {
                "title": {
                    "content": title,
                    "tag": "plain_text"
                },
                "template": color_map.get(color, "green")
            }
        }
    }

def create_discord_message(title, content, color=65280):
    """创建Discord消息格式"""
    return {
        "content": f"🔥 **{title}**",
        "embeds": [{
            "title": title,
            "description": content,
            "color": color,
            "footer": {"text": "由 GitHub Actions 自动监控"}
        }]
    }

def test_webhook():
    """测试webhook连接"""
    print("🧪 测试webhook连接...")
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    
    if not webhook_url:
        print("❌ 错误: 未找到DISCORD_WEBHOOK环境变量")
        return False
    
    print(f"✅ 找到webhook URL: {webhook_url[:50]}...")
    
    # 检测webhook类型
    webhook_type = detect_webhook_type(webhook_url)
    print(f"🔍 检测到webhook类型: {webhook_type}")
    
    # 根据类型创建测试消息
    if webhook_type == "lark":
        test_data = create_lark_message(
            "🧪 Webhook测试", 
            f"NBA50监控程序webhook连接正常\n\n⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "green"
        )
        expected_status = 200
    else:
        # 默认使用Discord格式
        test_data = create_discord_message(
            "连接测试成功！",
            f"NBA50监控程序webhook连接正常\n\n⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            65280
        )
        expected_status = 204
    
    try:
        response = requests.post(webhook_url, json=test_data, timeout=10)
        if response.status_code == expected_status:
            print("✅ Webhook测试成功！")
            return True
        else:
            print(f"❌ Webhook测试失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Webhook测试出错: {e}")
        return False

def check_for_50_points():
    """检查当日所有比赛中是否有球员得分50+"""
    # 首先测试webhook连接
    print("🤖 NBA50监控程序启动...")
    
    if not test_webhook():
        print("⚠️ Webhook测试失败，但继续执行程序...")
    
    # 发送启动通知
    try:
        send_to_discord(message_type="startup")
        print("✅ 启动通知已发送")
    except Exception as e:
        print(f"❌ 发送启动通知失败: {e}")
    
    found_50_points = False
    
    try:
        # 获取当日比赛数据（带重试）
        scoreboard = get_scoreboard_with_retry()
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
            
            # 获取比赛的详细统计数据（带重试）
            try:
                boxscore = get_boxscore_with_retry(game_id)
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
        error_msg = str(e)
        print(f"获取比赛数据时出错: {error_msg}")
        
        # 发送详细的错误通知
        send_to_discord(message_type="error", error_details=error_msg)

def send_to_discord(player=None, pts=None, team=None, matchup=None, message_type="50_points", error_details=None):
    """发送通知到webhook（支持Discord和飞书）"""
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("警告: 未设置 DISCORD_WEBHOOK 环境变量")
        return
    
    # 检测webhook类型
    webhook_type = detect_webhook_type(webhook_url)
    
    # 根据消息类型和webhook类型创建消息
    if message_type == "startup":
        title = "🤖 NBA50监控启动"
        content = f"NBA50分监控程序已启动\n开始检查今日NBA比赛中的50+得分情况...\n\n⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_message(title, content, "blue")
        else:
            data = create_discord_message("NBA50分监控程序已启动", content, 3447003)
    elif message_type == "no_games":
        title = "📅 今日无NBA比赛"
        content = f"今日没有NBA比赛安排\n\n⏰ 检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_message(title, content, "grey")
        else:
            data = create_discord_message("监控完成", content, 10197915)
    elif message_type == "no_50_points":
        title = "📊 今日监控完成"
        content = f"已检查完今日所有比赛，暂无球员得分达到50+\n\n⏰ 检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_message(title, content, "yellow")
        else:
            data = create_discord_message("未发现50+得分", content, 15844367)
    elif message_type == "error":
        title = "⚠️ 监控程序遇到错误"
        error_desc = f"NBA50监控程序在运行时遇到错误\n\n"
        if error_details:
            if "timeout" in error_details.lower():
                error_desc += "**错误类型**: 网络超时\n**可能原因**: NBA API响应缓慢或网络连接问题\n**建议**: 程序会自动重试，如持续出现请检查网络状态\n\n"
            elif "httpsconnectionpool" in error_details.lower():
                error_desc += "**错误类型**: 连接失败\n**可能原因**: NBA API服务器暂时不可用\n**建议**: 稍后会自动重试\n\n"
            else:
                error_desc += f"**错误详情**: {error_details[:200]}{'...' if len(error_details) > 200 else ''}\n\n"
        
        error_desc += f"⏰ 错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_message(title, error_desc, "red")
        else:
            data = create_discord_message("程序执行异常", error_desc, 15158332)
    else:
        # 50+得分通知
        title = "🔥 NBA50 优惠预警!"
        content = f"球员 **{player}** ({team}) 在今天的比赛中砍下了 **{pts}** 分！\n\n比赛: {matchup}\n\n**DoorDash NBA50** 优惠码预计将于明日 9:00 AM PT 生效！\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_message(title, content, "red")
        else:
            data = create_discord_message("50分记录达成！", content, 16711680)
    
    try:
        print(f"📤 正在发送{message_type}类型的{webhook_type}通知...")
        response = requests.post(webhook_url, json=data, timeout=10)
        
        # 根据webhook类型检查成功状态码
        expected_status = 200 if webhook_type == "lark" else 204
        
        if response.status_code == expected_status:
            if message_type == "startup":
                print("✅ 成功发送启动通知")
            elif message_type == "50_points":
                print(f"✅ 成功发送通知: {player} {pts}分")
            else:
                print("✅ 成功发送监控完成通知")
        else:
            print(f"❌ 通知发送失败: {response.status_code}")
            print(f"响应内容: {response.text}")
    except Exception as e:
        print(f"❌ 发送通知时出错: {e}")
        import traceback
        print(f"详细错误信息: {traceback.format_exc()}")

if __name__ == "__main__":
    import sys
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # 只测试webhook
        print("🧪 仅运行webhook测试...")
        test_webhook()
    else:
        # 运行完整的NBA监控
        check_for_50_points()
