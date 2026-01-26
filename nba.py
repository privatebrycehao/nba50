import os
import requests
import time
import json
from nba_api.stats.endpoints import scoreboardv2, boxscoretraditionalv2
from datetime import datetime, date, timedelta
import pytz

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://www.nba.com/'
}

def get_scoreboard_with_retry(max_retries=5, delay=10):
    for attempt in range(max_retries):
        try:
            print(f"尝试获取比赛数据 (第{attempt + 1}次)...")
            timeout_seconds = 60 + (attempt * 30)
            print(f"  使用超时时间: {timeout_seconds}秒")
            
            if attempt < 2:
                scoreboard = scoreboardv2.ScoreboardV2(timeout=timeout_seconds, headers=headers)
            else:
                scoreboard = scoreboardv2.ScoreboardV2(timeout=timeout_seconds)
            
            print("✅ 成功获取比赛数据")
            return scoreboard
        except Exception as e:
            print(f"第{attempt + 1}次尝试失败: {e}")
            if attempt < max_retries - 1:
                wait_time = delay + (attempt * 5)
                print(f"等待{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                print("❌ 所有重试都失败了")
                raise e

def get_boxscore_with_retry(game_id, max_retries=3, delay=5):
    for attempt in range(max_retries):
        try:
            print(f"  获取比赛 {game_id} 数据 (第{attempt + 1}次)...")
            timeout_seconds = 90 + (attempt * 30)
            
            if attempt < 2:
                boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id, timeout=timeout_seconds, headers=headers)
            else:
                boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id, timeout=timeout_seconds)
            
            return boxscore
        except Exception as e:
            print(f"  第{attempt + 1}次尝试失败: {e}")
            if attempt < max_retries - 1:
                wait_time = delay + (attempt * 3)
                print(f"  等待{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                raise e

def get_pacific_time_date():
    try:
        pacific_tz = pytz.timezone('US/Pacific')
        utc_now = datetime.now(pytz.UTC)
        pacific_now = utc_now.astimezone(pacific_tz)
        
        print(f"🕐 UTC时间: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"🕐 美西时间: {pacific_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        return pacific_now.date()
    except ImportError:
        utc_now = datetime.utcnow()
        pacific_now = utc_now - timedelta(hours=8)
        
        print(f"🕐 UTC时间: {utc_now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"🕐 美西时间(估算): {pacific_now.strftime('%Y-%m-%d %H:%M:%S')} PST")
        
        return pacific_now.date()

def detect_webhook_type(webhook_url):
    if "discord" in webhook_url.lower():
        return "discord"
    elif "larksuite.com" in webhook_url.lower() or "feishu" in webhook_url.lower():
        return "lark"
    else:
        return "unknown"

def create_lark_message(title, content, color="green"):
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
    return {
        "content": f"🔥 **{title}**",
        "embeds": [{
            "title": title,
            "description": content,
            "color": color,
            "footer": {"text": "由 GitHub Actions 自动监控"}
        }]
    }

def get_games_from_espn():
    print("🏀 尝试使用ESPN API获取数据...")
    try:
        pacific_today = get_pacific_time_date()
        
        for check_date in [pacific_today]:
            date_str = check_date.strftime('%Y%m%d')
            espn_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
            print(f"  检查美西时间日期: {date_str} ({check_date.strftime('%Y-%m-%d')})")
            
            response = requests.get(espn_url, timeout=30, headers=headers)
            if response.status_code != 200:
                print(f"    ESPN API响应错误: {response.status_code}")
                continue
            
            data = response.json()
            games = data.get('events', [])
            
            completed_games = [g for g in games if g.get('status', {}).get('type', {}).get('name', '') in ['STATUS_FINAL', 'STATUS_IN_PROGRESS']]
            scheduled_games = [g for g in games if g.get('status', {}).get('type', {}).get('name', '') == 'STATUS_SCHEDULED']
            
            print(f"    发现 {len(games)} 场比赛: {len(completed_games)} 场已完成/进行中, {len(scheduled_games)} 场未开始")
            
            if completed_games:
                print(f"✅ ESPN API成功获取到 {len(completed_games)} 场已完成/进行中的比赛 (美西时间: {date_str})")
                return completed_games, "espn"
        
        print("❌ ESPN API未找到已完成的比赛")
        return None, None
        
    except Exception as e:
        print(f"❌ ESPN API获取失败: {e}")
        return None, None

def get_espn_summary(game_id):
    try:
        summary_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
        response = requests.get(summary_url, timeout=30, headers=headers)
        if response.status_code != 200:
            print(f"  ESPN summary响应错误: {response.status_code}")
            return None
        return response.json()
    except Exception as e:
        print(f"  获取ESPN summary失败: {e}")
        return None

def extract_players_points_from_summary(summary):
    players = []
    if not summary:
        print(f"    summary数据为空")
        return players

    try:
        boxscore = summary.get("boxscore", {})
        if not boxscore:
            print(f"    summary中没有boxscore数据")
            return players
            
        team_blocks = boxscore.get("players", [])
        if not team_blocks:
            print(f"    boxscore中没有players数据")
            return players
            
        print(f"    找到 {len(team_blocks)} 个球队的数据块")
        
        for team_idx, team_block in enumerate(team_blocks):
            team_name = team_block.get("team", {}).get("abbreviation", "UNK")
            statistics = team_block.get("statistics", [])
            if not statistics:
                print(f"      球队 {team_name} 没有statistics数据")
                continue

            print(f"      球队 {team_name} 有 {len(statistics)} 个统计表")
            
            for stat_table_idx, stat_table in enumerate(statistics):
                stat_names = stat_table.get("statNames", [])
                if not stat_names:
                    continue

                pts_idx = None
                for idx, name in enumerate(stat_names):
                    name_upper = str(name).upper()
                    name_lower = str(name).lower()
                    if name_upper == "PTS" or "points" in name_lower or "pts" in name_lower:
                        pts_idx = idx
                        break

                if pts_idx is None:
                    continue

                athletes = stat_table.get("athletes", [])
                print(f"        统计表 {stat_table_idx} 包含 {len(athletes)} 名球员")
                
                for athlete_idx, athlete in enumerate(athletes):
                    athlete_obj = athlete.get("athlete", {})
                    athlete_name = (
                        athlete_obj.get("displayName") or
                        athlete_obj.get("fullName") or
                        athlete_obj.get("shortName") or
                        athlete.get("displayName") or
                        athlete.get("fullName") or
                        athlete.get("shortName") or
                        "Unknown"
                    )
                    
                    stats = athlete.get("stats", [])
                    
                    if pts_idx < len(stats):
                        try:
                            points = int(stats[pts_idx])
                            players.append({
                                "name": athlete_name,
                                "points": points,
                                "team": team_name,
                            })
                            if points >= 50:
                                print(f"        ⚠️ 发现高分: {athlete_name} - {points}分")
                        except (ValueError, TypeError):
                            points = 0
    except Exception as e:
        print(f"  解析summary球员数据失败: {e}")

    return players

def extract_top_scorers_from_event(game):
    top_scorers = []
    try:
        competitions = game.get("competitions", [])
        if not competitions:
            return top_scorers

        competitors = competitions[0].get("competitors", [])
        print(f"    找到 {len(competitors)} 个competitor")
        
        for competitor in competitors:
            team_abbr = competitor.get("team", {}).get("abbreviation", "UNK")
            leaders = competitor.get("leaders", [])
            
            for leader_block in leaders:
                leader_name = leader_block.get("name", "").lower()
                if leader_name in ["points", "pts"]:
                    leaders_list = leader_block.get("leaders", [])
                    print(f"          找到 {len(leaders_list)} 名得分王")
                    for leader in leaders_list:
                        athlete_obj = leader.get("athlete", {})
                        player_name = (
                            athlete_obj.get("displayName") or
                            athlete_obj.get("fullName") or
                            athlete_obj.get("shortName") or
                            leader.get("displayName") or
                            leader.get("fullName") or
                            leader.get("shortName") or
                            leader.get("name") or
                            "Unknown"
                        )
                        
                        points = leader.get("value", 0)
                        
                        try:
                            points_int = int(points) if isinstance(points, (int, float, str)) else 0
                            top_scorers.append({
                                "name": player_name,
                                "points": points_int,
                                "team": team_abbr,
                            })
                        except (ValueError, TypeError):
                            pass
    except Exception as e:
        print(f"    从event提取得分王失败: {e}")
    return top_scorers

def generate_game_summary(games_data, api_source):
    if not games_data:
        return "无比赛数据"
    
    summary_lines = []
    
    if api_source == "espn":
        for game in games_data:
            try:
                competitions = game.get('competitions', [{}])
                if competitions:
                    competitors = competitions[0].get('competitors', [])
                    if len(competitors) >= 2:
                        home_team = competitors[0]
                        away_team = competitors[1]
                        
                        home_name = home_team.get('team', {}).get('abbreviation', 'UNK')
                        away_name = away_team.get('team', {}).get('abbreviation', 'UNK')
                        home_score = home_team.get('score', 0)
                        away_score = away_team.get('score', 0)
                        
                        matchup = f"{away_name} {away_score} - {home_score} {home_name}"
                        summary_lines.append(f"🏀 **{matchup}**")
                        summary_lines.append("")
            except Exception as e:
                summary_lines.append(f"🏀 比赛信息解析错误: {e}")
                summary_lines.append("")
    
    return "\n".join(summary_lines) if summary_lines else "无法生成比赛摘要"

def check_espn_game_for_50_points(game, api_status=None, games_count=0, games_summary=None, highest_scorers=None):
    found_50_points = False
    if highest_scorers is None:
        highest_scorers = []

    try:
        status = game.get("status", {}).get("type", {}).get("name", "")
        if status not in ["STATUS_FINAL", "STATUS_IN_PROGRESS", "STATUS_HALFTIME"]:
            print(f"  比赛未开始或状态未知: {status}")
            return False

        competitions = game.get("competitions", [{}])
        competitors = competitions[0].get("competitors", []) if competitions else []
        if len(competitors) < 2:
            return False

        home_team = competitors[0]
        away_team = competitors[1]
        matchup = f"{away_team.get('team', {}).get('abbreviation', 'UNK')} @ {home_team.get('team', {}).get('abbreviation', 'UNK')}"
        print(f"  检查比赛: {matchup}")

        game_id = game.get("id")
        players = []
        if game_id:
            print(f"    获取比赛 {game_id} 的详细数据...")
            summary = get_espn_summary(game_id)
            players = extract_players_points_from_summary(summary)
            print(f"    从summary中提取到 {len(players)} 名球员数据")

        if players:
            top_player = max(players, key=lambda p: p.get("points", 0))
            print(f"    得分王: {top_player.get('name', 'Unknown')} ({top_player.get('team', 'UNK')}) - {top_player.get('points', 0)}分")
            if highest_scorers is not None:
                highest_scorers.append({
                    "matchup": matchup,
                    "name": top_player.get("name", "Unknown"),
                    "points": top_player.get("points", 0),
                    "team": top_player.get("team", "UNK"),
                })

            for player in players:
                points = player.get("points", 0)
                if points >= 50:
                    print(f"🔥 发现50+得分: {player['name']} ({player['team']}) - {points}分")
                    send_notification(
                        player["name"],
                        player["points"],
                        player["team"],
                        matchup,
                        "50_points",
                        api_status=api_status,
                        games_count=games_count,
                        games_summary=games_summary,
                        highest_scorers=highest_scorers,
                    )
                    found_50_points = True
        else:
            fallback_top = extract_top_scorers_from_event(game)
            
            if fallback_top:
                for player in fallback_top:
                    print(f"      得分王: {player.get('name', 'Unknown')} ({player.get('team', 'UNK')}) - {player.get('points', 0)}分")
                    if highest_scorers is not None:
                        highest_scorers.append({
                            "matchup": matchup,
                            "name": player.get("name", "Unknown"),
                            "points": player.get("points", 0),
                            "team": player.get("team", "UNK"),
                        })
                    
                    points = player.get("points", 0)
                    if points >= 50:
                        print(f"🔥 发现50+得分 (从event): {player.get('name', 'Unknown')} ({player.get('team', 'UNK')}) - {points}分")
                        send_notification(
                            player.get("name", "Unknown"),
                            points,
                            player.get("team", "UNK"),
                            matchup,
                            "50_points",
                            api_status=api_status,
                            games_count=games_count,
                            games_summary=games_summary,
                            highest_scorers=highest_scorers,
                        )
                        found_50_points = True

        return found_50_points

    except Exception as e:
        print(f"  检查ESPN比赛数据时出错: {e}")
        return False

def send_notification(player=None, pts=None, team=None, matchup=None, message_type="50_points", error_details=None, api_status=None, games_count=0, games_summary=None, highest_scorers=None):
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("警告: 未设置 DISCORD_WEBHOOK 环境变量")
        return
    
    webhook_type = detect_webhook_type(webhook_url)
    
    if message_type == "no_games":
        title = "📅 今日无NBA比赛"
        content = f"今日没有NBA比赛安排\n\n"
        
        if api_status:
            content += f"📡 **数据来源**: {api_status.get('successful_api', 'Unknown')}\n"
            
            failed_apis = api_status.get('failed_apis', [])
            if failed_apis:
                content += f"❌ **失败的API**: {', '.join(failed_apis)}\n"
            content += "\n"
        
        content += f"⏰ 检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_message(title, content, "grey")
        else:
            data = create_discord_message("监控完成", content, 10197915)
    elif message_type == "no_50_points":
        title = "📊 今日监控完成"
        content = f"已检查完今日所有比赛，暂无球员得分达到50+\n\n"
        
        if api_status:
            content += f"📡 **数据来源**: {api_status.get('successful_api', 'Unknown')}\n"
            content += f"🏀 **比赛数量**: {games_count} 场\n"
            
            failed_apis = api_status.get('failed_apis', [])
            if failed_apis:
                content += f"❌ **失败的API**: {', '.join(failed_apis)}\n"
            content += "\n"
        
        if games_summary:
            content += "📋 **今日比赛详情**:\n\n"
            content += games_summary
            content += "\n"

        if highest_scorers:
            content += "🏅 **每场比赛最高得分**:\n"
            for scorer in highest_scorers:
                content += f"- {scorer.get('matchup', 'Unknown')}: {scorer.get('name', 'Unknown')} ({scorer.get('team', 'UNK')}) - {scorer.get('points', 0)}分\n"
            content += "\n"
        
        content += f"⏰ 检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_message(title, content, "yellow")
        else:
            data = create_discord_message("未发现50+得分", content, 15844367)
    elif message_type == "error":
        title = "⚠️ 监控程序遇到错误"
        error_desc = f"NBA50监控程序在运行时遇到错误\n\n"
        
        if api_status:
            failed_apis = api_status.get('failed_apis', [])
            if failed_apis:
                error_desc += f"❌ **失败的API**: {', '.join(failed_apis)}\n"
            
            successful_api = api_status.get('successful_api')
            if successful_api:
                error_desc += f"✅ **成功的API**: {successful_api}\n"
            error_desc += "\n"
        
        if error_details:
            if "timeout" in error_details.lower():
                error_desc += "**错误类型**: 网络超时\n**可能原因**: NBA API响应缓慢或网络连接问题\n**建议**: 程序会自动重试，如持续出现请检查网络状态\n\n"
            elif "httpsconnectionpool" in error_details.lower():
                error_desc += "**错误类型**: 连接失败\n**可能原因**: NBA API服务器暂时不可用\n**建议**: 稍后会自动重试\n\n"
            elif "所有API都无法获取数据" in error_details:
                error_desc += "**错误类型**: 所有API失败\n**可能原因**: 网络问题或所有NBA数据源暂时不可用\n**建议**: 程序会在下次调度时间自动重试\n\n"
            else:
                error_desc += f"**错误详情**: {error_details[:200]}{'...' if len(error_details) > 200 else ''}\n\n"
        
        error_desc += f"⏰ 错误时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_message(title, error_desc, "red")
        else:
            data = create_discord_message("程序执行异常", error_desc, 15158332)
    else:
        title = "🔥 NBA50 优惠预警!"
        content = f"球员 **{player}** ({team}) 在今天的比赛中砍下了 **{pts}** 分！\n\n比赛: {matchup}\n\n**DoorDash NBA50** 优惠码预计将于明日 9:00 AM PT 生效！\n\n"
        
        if api_status:
            content += f"📡 **数据来源**: {api_status.get('successful_api', 'Unknown')}\n"
            failed_apis = api_status.get('failed_apis', [])
            if failed_apis:
                content += f"❌ **失败的API**: {', '.join(failed_apis)}\n"
            content += "\n"
        
        if games_summary:
            content += "📋 **今日所有比赛**:\n\n"
            content += games_summary
            content += "\n"

        if highest_scorers:
            content += "🏅 **每场比赛最高得分**:\n"
            for scorer in highest_scorers:
                content += f"- {scorer.get('matchup', 'Unknown')}: {scorer.get('name', 'Unknown')} ({scorer.get('team', 'UNK')}) - {scorer.get('points', 0)}分\n"
            content += "\n"
        
        content += f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_message(title, content, "red")
        else:
            data = create_discord_message("50分记录达成！", content, 16711680)
    
    try:
        print(f"📤 正在发送{message_type}类型的{webhook_type}通知...")
        response = requests.post(webhook_url, json=data, timeout=10)
        
        expected_status = 200 if webhook_type == "lark" else 204
        
        if response.status_code == expected_status:
            if message_type == "50_points":
                print(f"✅ 成功发送通知: {player} {pts}分")
            else:
                print("✅ 成功发送监控完成通知")
        else:
            print(f"❌ 通知发送失败: {response.status_code}")
            print(f"响应内容: {response.text}")
    except Exception as e:
        print(f"❌ 发送通知时出错: {e}")

def check_for_50_points():
    print("🤖 NBA50监控程序启动...")
    
    found_50_points = False
    highest_scorers = []
    
    try:
        games_data = None
        api_source = None
        api_status = {
            'failed_apis': [],
            'successful_api': None
        }
        games_count = 0
    
        print("🏀 使用ESPN API获取数据...")
        games_data, api_source = get_games_from_espn()
        if games_data is not None:
            games_count = len(games_data)
            api_status['successful_api'] = "ESPN API"
            print(f"✅ ESPN API成功获取到 {games_count} 场比赛")
        else:
            api_status['failed_apis'].append("ESPN API")
        
        if games_data is None:
            raise Exception("所有API都无法获取数据")
    
        if api_source == "espn":
            if not games_data:
                print("今日没有比赛")
                send_notification(message_type="no_games", api_status=api_status, games_count=0)
                return
                
            print(f"检查 {len(games_data)} 场比赛的球员数据...")
            
            games_summary = generate_game_summary(games_data, api_source)
            
            for game in games_data:
                if check_espn_game_for_50_points(game, api_status, games_count, games_summary, highest_scorers):
                    found_50_points = True
    
        if not found_50_points:
            print("✅ 监控完成，未发现50+得分")
            send_notification(
                message_type="no_50_points",
                api_status=api_status,
                games_count=games_count,
                games_summary=games_summary,
                highest_scorers=highest_scorers,
            )
                
    except Exception as e:
        error_msg = str(e)
        print(f"获取比赛数据时出错: {error_msg}")
        
        if "timeout" in error_msg.lower():
            print("💡 建议: NBA API响应缓慢，这在比赛高峰期很常见")
        elif "connection" in error_msg.lower():
            print("💡 建议: 网络连接问题，可能是临时的")
        
        send_notification(message_type="error", error_details=error_msg, api_status=api_status)

if __name__ == "__main__":
    check_for_50_points()
