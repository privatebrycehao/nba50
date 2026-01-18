import os
import requests
import time
import json
from nba_api.stats.endpoints import scoreboardv2, boxscoretraditionalv2
from datetime import datetime, date, timedelta
import pytz

# 设置NBA API的请求头，避免被识别为爬虫
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://www.nba.com/'
}

def get_scoreboard_with_retry(max_retries=5, delay=10):
    """带重试机制获取比赛数据"""
    for attempt in range(max_retries):
        try:
            print(f"尝试获取比赛数据 (第{attempt + 1}次)...")
            # 逐步增加超时时间
            timeout_seconds = 60 + (attempt * 30)  # 60, 90, 120, 150, 180秒
            print(f"  使用超时时间: {timeout_seconds}秒")
            
            # 尝试不同的方法
            if attempt < 2:
                # 前两次使用自定义headers
                scoreboard = scoreboardv2.ScoreboardV2(timeout=timeout_seconds, headers=headers)
            else:
                # 后面几次使用默认设置，可能更稳定
                scoreboard = scoreboardv2.ScoreboardV2(timeout=timeout_seconds)
            
            print("✅ 成功获取比赛数据")
            return scoreboard
        except Exception as e:
            print(f"第{attempt + 1}次尝试失败: {e}")
            if attempt < max_retries - 1:
                # 逐步增加等待时间
                wait_time = delay + (attempt * 5)  # 10, 15, 20, 25秒
                print(f"等待{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                print("❌ 所有重试都失败了")
                raise e

def get_boxscore_with_retry(game_id, max_retries=3, delay=5):
    """带重试机制获取比赛详细数据"""
    for attempt in range(max_retries):
        try:
            print(f"  获取比赛 {game_id} 数据 (第{attempt + 1}次)...")
            timeout_seconds = 90 + (attempt * 30)  # 90, 120, 150秒
            
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
    """获取美西时间的当前日期"""
    try:
        # 美西时区（自动处理夏令时）
        pacific_tz = pytz.timezone('US/Pacific')
        utc_now = datetime.now(pytz.UTC)
        pacific_now = utc_now.astimezone(pacific_tz)
        
        print(f"🕐 UTC时间: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"🕐 美西时间: {pacific_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        return pacific_now.date()
    except ImportError:
        # 如果pytz不可用，使用简单的时区偏移
        print("⚠️ pytz不可用，使用简单时区计算")
        utc_now = datetime.utcnow()
        # 假设PST (UTC-8)，实际应该根据季节调整
        pacific_now = utc_now - timedelta(hours=8)
        
        print(f"🕐 UTC时间: {utc_now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"🕐 美西时间(估算): {pacific_now.strftime('%Y-%m-%d %H:%M:%S')} PST")
        
        return pacific_now.date()

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

def get_games_from_espn():
    """使用ESPN API获取今日NBA比赛数据"""
    print("🏀 尝试使用ESPN API获取数据...")
    try:
        # 获取美西时间的日期
        pacific_today = get_pacific_time_date()
        
        # 检查美西时间的今天
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
            
            # 检查是否有已完成或进行中的比赛
            completed_games = [g for g in games if g.get('status', {}).get('type', {}).get('name', '') in ['STATUS_FINAL', 'STATUS_IN_PROGRESS']]
            scheduled_games = [g for g in games if g.get('status', {}).get('type', {}).get('name', '') == 'STATUS_SCHEDULED']
            
            print(f"    发现 {len(games)} 场比赛: {len(completed_games)} 场已完成/进行中, {len(scheduled_games)} 场未开始")
            
            if completed_games:
                print(f"✅ ESPN API成功获取到 {len(completed_games)} 场已完成/进行中的比赛 (美西时间: {date_str})")
                return completed_games, "espn"
        
        print("❌ ESPN API未找到已完成的比赛")
        return None, None
        
        response = requests.get(espn_url, timeout=30, headers=headers)
        if response.status_code != 200:
            raise Exception(f"ESPN API响应错误: {response.status_code}")
        
        data = response.json()
        games = data.get('events', [])
        
        print(f"✅ ESPN API成功获取到 {len(games)} 场比赛")
        return games, "espn"
    
    except Exception as e:
        print(f"❌ ESPN API获取失败: {e}")
        return None, None

def get_espn_summary(game_id):
    """获取ESPN比赛summary数据"""
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
    """从ESPN summary中提取球员得分列表"""
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
            
            # 找到包含PTS的统计表
            for stat_table_idx, stat_table in enumerate(statistics):
                stat_names = stat_table.get("statNames", [])
                if not stat_names:
                    print(f"        统计表 {stat_table_idx} 没有statNames")
                    continue

                print(f"        统计表 {stat_table_idx} 的statNames: {stat_names}")
                
                pts_idx = None
                for idx, name in enumerate(stat_names):
                    name_upper = str(name).upper()
                    name_lower = str(name).lower()
                    if name_upper == "PTS" or "points" in name_lower or "pts" in name_lower:
                        pts_idx = idx
                        print(f"          找到PTS字段，索引: {pts_idx}")
                        break

                if pts_idx is None:
                    print(f"        统计表 {stat_table_idx} 没有找到PTS字段")
                    continue

                athletes = stat_table.get("athletes", [])
                print(f"        统计表 {stat_table_idx} 包含 {len(athletes)} 名球员")
                
                if not athletes:
                    print(f"        统计表 {stat_table_idx} 的athletes数组为空")
                    continue
                
                for athlete_idx, athlete in enumerate(athletes):
                    # 尝试多种方式获取球员名字
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
                    print(f"          球员 {athlete_idx}: {athlete_name}, stats长度: {len(stats)}, pts_idx: {pts_idx}")
                    
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
                        except (ValueError, TypeError) as e:
                            print(f"        解析 {athlete_name} 得分失败: {e}, stats[{pts_idx}] = {stats[pts_idx] if pts_idx < len(stats) else 'N/A'}")
                            points = 0
                    else:
                        print(f"        球员 {athlete_name} 的stats数组长度不足: {len(stats)} < {pts_idx + 1}")
    except Exception as e:
        print(f"  解析summary球员数据失败: {e}")
        import traceback
        print(f"  详细错误: {traceback.format_exc()}")

    return players

def extract_top_scorers_from_event(game):
    """从ESPN event数据中提取得分王信息（作为补充）"""
    top_scorers = []
    try:
        competitions = game.get("competitions", [])
        if not competitions:
            print(f"    event中没有competitions数据")
            return top_scorers

        competitors = competitions[0].get("competitors", [])
        print(f"    找到 {len(competitors)} 个competitor")
        
        for competitor in competitors:
            team_abbr = competitor.get("team", {}).get("abbreviation", "UNK")
            leaders = competitor.get("leaders", [])
            print(f"      球队 {team_abbr} 有 {len(leaders)} 个leader数据块")
            
            for leader_block in leaders:
                leader_name = leader_block.get("name", "").lower()
                print(f"        leader类型: {leader_name}")
                if leader_name in ["points", "pts"]:
                    leaders_list = leader_block.get("leaders", [])
                    print(f"          找到 {len(leaders_list)} 名得分王")
                    for leader_idx, leader in enumerate(leaders_list):
                        # 尝试多种方式获取球员名字
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
                        print(f"          leader {leader_idx} 原始数据: {leader}")
                        
                        try:
                            points_int = int(points) if isinstance(points, (int, float, str)) else 0
                            top_scorers.append({
                                "name": player_name,
                                "points": points_int,
                                "team": team_abbr,
                            })
                            print(f"          得分王: {player_name} - {points_int}分")
                        except (ValueError, TypeError) as e:
                            print(f"          解析得分失败: {e}, value = {points}")
    except Exception as e:
        print(f"    从event提取得分王失败: {e}")
        import traceback
        print(f"    详细错误: {traceback.format_exc()}")
    return top_scorers

def get_games_from_nba_com_by_date(target_date):
    """根据指定日期获取NBA.com比赛数据"""
    try:
        # 尝试获取指定日期的比赛数据
        date_str = target_date.strftime('%Y-%m-%d')
        
        # 先尝试今日比赛API
        if target_date == date.today():
            nba_url = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
        else:
            # 对于其他日期，尝试构造历史数据URL
            nba_url = f"https://cdn.nba.com/static/json/liveData/scoreboard/scoreboard_{target_date.strftime('%Y%m%d')}.json"
        
        print(f"  尝试获取 {date_str} 的比赛数据: {nba_url}")
        
        response = requests.get(nba_url, timeout=30, headers=headers)
        if response.status_code != 200:
            return None, None
        
        data = response.json()
        games = data.get('scoreboard', {}).get('games', [])
        
        return games, date_str
        
    except Exception as e:
        print(f"  获取 {target_date} 数据失败: {e}")
        return None, None

def get_games_from_nba_com():
    """使用NBA.com API获取比赛数据"""
    print("🏀 尝试使用NBA.com API获取数据...")
    
    # 获取美西时间日期信息
    pacific_today = get_pacific_time_date()
    pacific_yesterday = pacific_today - timedelta(days=1)
    
    # 按优先级尝试不同日期
    for target_date in [pacific_today, pacific_yesterday]:
        print(f"  尝试美西时间日期: {target_date.strftime('%Y-%m-%d')}")
        
        try:
            # 先尝试今日比赛API
            nba_url = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
            
            response = requests.get(nba_url, timeout=30, headers=headers)
            if response.status_code != 200:
                print(f"    NBA.com API响应错误: {response.status_code}")
                continue
            
            data = response.json()
            games = data.get('scoreboard', {}).get('games', [])
            api_game_date = data.get('scoreboard', {}).get('gameDate', 'unknown')
            
            print(f"    API返回的比赛日期: {api_game_date}")
            print(f"    目标日期: {target_date.strftime('%Y-%m-%d')}")
            
            # 检查日期是否匹配（允许一天的误差）
            if api_game_date != 'unknown':
                try:
                    api_date = datetime.strptime(api_game_date, '%Y-%m-%d').date()
                    date_diff = abs((api_date - target_date).days)
                    
                    if date_diff <= 1:  # 允许一天误差
                        # 过滤出已完成或进行中的比赛
                        completed_games = [g for g in games if g.get('gameStatus') in [2, 3]]
                        scheduled_games = [g for g in games if g.get('gameStatus') == 1]
                        
                        print(f"✅ NBA.com API成功获取到 {len(games)} 场比赛 (日期: {api_game_date})")
                        print(f"    其中 {len(completed_games)} 场已完成/进行中, {len(scheduled_games)} 场未开始")
                        
                        if completed_games or not scheduled_games:  # 有已完成的比赛，或者没有任何比赛
                            return games, "nba_com"
                        else:
                            print(f"    所有比赛都未开始，继续尝试前一天...")
                    else:
                        print(f"    日期不匹配，差异: {date_diff} 天")
                except ValueError:
                    print(f"    无法解析API日期: {api_game_date}")
            
        except Exception as e:
            print(f"    获取数据失败: {e}")
            continue
    
    print("❌ NBA.com API未找到合适的比赛数据")
    return None, None

def check_espn_game_for_50_points(game, api_status=None, games_count=0, games_summary=None, highest_scorers=None):
    """检查ESPN格式的比赛数据中是否有50+得分"""
    found_50_points = False
    # 修复：不要覆盖传入的highest_scorers，如果为None则初始化为空列表
    if highest_scorers is None:
        highest_scorers = []

    try:
        # ESPN API的比赛状态检查
        status = game.get("status", {}).get("type", {}).get("name", "")
        if status not in ["STATUS_FINAL", "STATUS_IN_PROGRESS", "STATUS_HALFTIME"]:
            print(f"  比赛未开始或状态未知: {status}")
            return False

        # 获取比赛信息
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

        # 计算得分王并记录
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

            # 检查50+得分
            for player in players:
                points = player.get("points", 0)
                if points >= 50:
                    print(f"🔥 发现50+得分: {player['name']} ({player['team']}) - {points}分")
                    send_to_discord(
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
            # 从event里提取得分王（作为补充）
            print(f"    summary数据为空，尝试从event数据中提取...")
            fallback_top = extract_top_scorers_from_event(game)
            print(f"    从event中提取到 {len(fallback_top)} 名得分王")
            
            if fallback_top:
                # 记录得分王
                for player in fallback_top:
                    print(f"      得分王: {player.get('name', 'Unknown')} ({player.get('team', 'UNK')}) - {player.get('points', 0)}分")
                    if highest_scorers is not None:
                        highest_scorers.append({
                            "matchup": matchup,
                            "name": player.get("name", "Unknown"),
                            "points": player.get("points", 0),
                            "team": player.get("team", "UNK"),
                        })
                    
                    # 检查50+得分
                    points = player.get("points", 0)
                    if points >= 50:
                        print(f"🔥 发现50+得分 (从event): {player.get('name', 'Unknown')} ({player.get('team', 'UNK')}) - {points}分")
                        send_to_discord(
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
        import traceback
        print(f"  详细错误: {traceback.format_exc()}")
        return False

def generate_game_summary(games_data, api_source):
    """生成比赛摘要信息"""
    if not games_data:
        return "无比赛数据"
    
    summary_lines = []
    
    if api_source == "nba_com":
        for game in games_data:
            try:
                # 获取比赛基本信息
                away_team = game.get('awayTeam', {})
                home_team = game.get('homeTeam', {})
                
                away_name = away_team.get('teamTricode', 'UNK')
                home_name = home_team.get('teamTricode', 'UNK')
                away_score = away_team.get('score', 0)
                home_score = home_team.get('score', 0)
                
                game_status = game.get('gameStatusText', 'Unknown')
                
                # 获取得分王信息
                home_leader = game.get('gameLeaders', {}).get('homeLeaders', {})
                away_leader = game.get('gameLeaders', {}).get('awayLeaders', {})
                
                # 格式化比赛信息
                matchup = f"{away_name} {away_score} - {home_score} {home_name}"
                if game_status == "Final":
                    matchup += " (终场)"
                elif game_status != "Unknown":
                    matchup += f" ({game_status})"
                
                summary_lines.append(f"🏀 **{matchup}**")
                
                # 添加得分王信息
                if home_leader and home_leader.get('points', 0) > 0:
                    summary_lines.append(f"   {home_leader.get('name', 'Unknown')} ({home_name}): {home_leader.get('points', 0)}分")
                
                if away_leader and away_leader.get('points', 0) > 0:
                    summary_lines.append(f"   {away_leader.get('name', 'Unknown')} ({away_name}): {away_leader.get('points', 0)}分")
                
                summary_lines.append("")  # 空行分隔
                
            except Exception as e:
                summary_lines.append(f"🏀 比赛信息解析错误: {e}")
                summary_lines.append("")
    
    elif api_source == "nba_api":
        # 处理nba_api格式的数据
        for _, game in games_data.iterrows():
            try:
                matchup = game.get('MATCHUP', 'Unknown vs Unknown')
                game_id = game.get('GAME_ID', 'Unknown')
                summary_lines.append(f"🏀 **{matchup}** (ID: {game_id})")
                summary_lines.append("")
            except Exception as e:
                summary_lines.append(f"🏀 比赛信息解析错误: {e}")
                summary_lines.append("")
    
    elif api_source == "espn":
        # 处理ESPN格式的数据
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

def check_nba_com_game_for_50_points(game, api_status=None, games_count=0, games_summary=None):
    """检查NBA.com格式的比赛数据中是否有50+得分"""
    found_50_points = False
    
    try:
        game_id = game.get('gameId')
        if not game_id:
            return False
            
        # 检查比赛状态
        game_status = game.get('gameStatus')
        if game_status not in [2, 3]:  # 2=进行中, 3=已结束
            print(f"  比赛 {game_id} 未开始 (状态: {game_status})")
            return False
            
        matchup = f"{game.get('awayTeam', {}).get('teamTricode', 'UNK')} @ {game.get('homeTeam', {}).get('teamTricode', 'UNK')}"
        print(f"  检查比赛: {matchup} (状态: {game.get('gameStatusText', 'Unknown')})")
        
        # 首先检查gameLeaders中是否有50+得分的线索
        home_leader = game.get('gameLeaders', {}).get('homeLeaders', {})
        away_leader = game.get('gameLeaders', {}).get('awayLeaders', {})
        
        for leader in [home_leader, away_leader]:
            if leader and leader.get('points', 0) >= 50:
                player_name = leader.get('name', 'Unknown')
                team_name = leader.get('teamTricode', 'UNK')
                points = leader.get('points', 0)
                print(f"🔥 发现50+得分 (从gameLeaders): {player_name} ({team_name}) - {points}分")
                send_to_discord(player_name, points, team_name, matchup, "50_points", api_status=api_status, games_count=games_count, games_summary=games_summary)
                found_50_points = True
        
        # 如果gameLeaders中没有50+，尝试获取完整的boxscore数据
        if not found_50_points:
            try:
                boxscore_url = f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
                print(f"    获取详细数据: {boxscore_url}")
                response = requests.get(boxscore_url, timeout=30, headers=headers)
                
                if response.status_code == 200:
                    boxscore_data = response.json()
                    
                    # 检查主队和客队的球员数据
                    for team_key in ['homeTeam', 'awayTeam']:
                        team_data = boxscore_data.get('game', {}).get(team_key, {})
                        players = team_data.get('players', [])
                        team_name = team_data.get('teamTricode', 'UNK')
                        
                        for player in players:
                            stats = player.get('statistics', {})
                            points = stats.get('points', 0)
                            player_name = f"{player.get('firstName', '')} {player.get('lastName', '')}"
                            
                            if points >= 50:
                                print(f"🔥 发现50+得分 (从boxscore): {player_name} ({team_name}) - {points}分")
                                send_to_discord(player_name, points, team_name, matchup, "50_points", api_status=api_status, games_count=games_count, games_summary=games_summary)
                                found_50_points = True
                else:
                    print(f"    无法获取详细数据，状态码: {response.status_code}")
            except Exception as boxscore_error:
                print(f"    获取boxscore数据失败: {boxscore_error}")
        
        return found_50_points
        
    except Exception as e:
        print(f"  检查NBA.com比赛数据时出错: {e}")
        return False

def test_nba_api_connection():
    """测试NBA API连接"""
    print("🌐 测试NBA API连接...")
    try:
        # 简单的连接测试
        response = requests.get("https://stats.nba.com", timeout=10, headers=headers)
        if response.status_code == 200:
            print("✅ NBA网站连接正常")
            return True
        else:
            print(f"⚠️ NBA网站响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ NBA网站连接失败: {e}")
        return False

def check_for_50_points():
    """检查当日所有比赛中是否有球员得分50+"""
    # 首先测试webhook连接
    print("🤖 NBA50监控程序启动...")
    
    # 测试NBA API连接
    test_nba_api_connection()
    
    found_50_points = False
    highest_scorers = []  # 初始化最高得分球员列表
    
    try:
        # 尝试多个API来源
        games_data = None
        api_source = None
        api_status = {
            'failed_apis': [],
            'successful_api': None
        }
        games_count = 0
    
        # 只使用ESPN API（最稳定且不会超时）
        print("🏀 使用ESPN API获取数据...")
        games_data, api_source = get_games_from_espn()
        if games_data is not None:
            games_count = len(games_data)
            api_status['successful_api'] = "ESPN API"
            print(f"✅ ESPN API成功获取到 {games_count} 场比赛")
        else:
            api_status['failed_apis'].append("ESPN API")
        
        # 如果所有API都失败了
        if games_data is None:
            raise Exception("所有API都无法获取数据")
    
        # 根据API来源处理数据
        if api_source == "nba_api":
            # 使用原有的nba_api逻辑
            if games_data.empty:
                print("今日没有比赛")
                send_to_discord(message_type="no_games", api_status=api_status, games_count=0)
                return
            
            print(f"检查 {len(games_data)} 场比赛的球员数据...")
            
            # 生成比赛摘要
            games_summary = generate_game_summary(games_data, api_source)
            
            # 遍历每场比赛
            for _, game in games_data.iterrows():
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
                            send_to_discord(player_name, points, team_abbreviation, game['MATCHUP'], "50_points", api_status=api_status, games_count=games_count, games_summary=games_summary)
                            found_50_points = True
                        
                except Exception as e:
                    print(f"获取比赛 {game_id} 数据时出错: {e}")
                    continue
    
        elif api_source == "espn":
            # 使用ESPN API逻辑
            if not games_data:
                print("今日没有比赛")
                send_to_discord(message_type="no_games", api_status=api_status, games_count=0)
                return
                
            print(f"检查 {len(games_data)} 场比赛的球员数据...")
            
            # 生成比赛摘要
            games_summary = generate_game_summary(games_data, api_source)
            
            for game in games_data:
                if check_espn_game_for_50_points(game, api_status, games_count, games_summary, highest_scorers):
                    found_50_points = True
    
        elif api_source == "nba_com":
            # 使用NBA.com API逻辑
            if not games_data:
                print("今日没有比赛")
                send_to_discord(message_type="no_games", api_status=api_status, games_count=0)
                return
                
            print(f"检查 {len(games_data)} 场比赛的球员数据...")
            
            # 显示所有比赛的得分王信息
            print("📊 今日比赛得分王:")
            for game in games_data:
                matchup = f"{game.get('awayTeam', {}).get('teamTricode', 'UNK')} @ {game.get('homeTeam', {}).get('teamTricode', 'UNK')}"
                home_leader = game.get('gameLeaders', {}).get('homeLeaders', {})
                away_leader = game.get('gameLeaders', {}).get('awayLeaders', {})
                
                if home_leader:
                    print(f"  {matchup}: {home_leader.get('name', 'Unknown')} ({home_leader.get('teamTricode', 'UNK')}) - {home_leader.get('points', 0)}分")
                if away_leader:
                    print(f"  {matchup}: {away_leader.get('name', 'Unknown')} ({away_leader.get('teamTricode', 'UNK')}) - {away_leader.get('points', 0)}分")
            
            # 生成比赛摘要
            games_summary = generate_game_summary(games_data, api_source)
            
            # 检查50+得分
            for game in games_data:
                if check_nba_com_game_for_50_points(game, api_status, games_count, games_summary):
                    found_50_points = True
    
        # 如果没有发现50+得分，发送完成通知
        if not found_50_points:
            print("✅ 监控完成，未发现50+得分")
            send_to_discord(
                message_type="no_50_points",
                api_status=api_status,
                games_count=games_count,
                games_summary=games_summary,
                highest_scorers=highest_scorers,
            )
                
    except Exception as e:
        error_msg = str(e)
        print(f"获取比赛数据时出错: {error_msg}")
        
        # 根据错误类型提供不同的建议
        if "timeout" in error_msg.lower():
            print("💡 建议: NBA API响应缓慢，这在比赛高峰期很常见")
            print("💡 程序会在下次调度时间自动重试")
        elif "connection" in error_msg.lower():
            print("💡 建议: 网络连接问题，可能是临时的")
        
        # 发送详细的错误通知
        send_to_discord(message_type="error", error_details=error_msg, api_status=api_status)

def send_to_discord(player=None, pts=None, team=None, matchup=None, message_type="50_points", error_details=None, api_status=None, games_count=0, games_summary=None, highest_scorers=None):
    """发送通知到webhook（支持Discord和飞书）"""
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        print("警告: 未设置 DISCORD_WEBHOOK 环境变量")
        return
    
    # 检测webhook类型
    webhook_type = detect_webhook_type(webhook_url)
    
    # 根据消息类型和webhook类型创建消息
    if message_type == "no_games":
        title = "📅 今日无NBA比赛"
        content = f"今日没有NBA比赛安排\n\n"
        
        # 添加API状态信息
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
        
        # 添加API状态信息
        if api_status:
            content += f"📡 **数据来源**: {api_status.get('successful_api', 'Unknown')}\n"
            content += f"🏀 **比赛数量**: {games_count} 场\n"
            
            failed_apis = api_status.get('failed_apis', [])
            if failed_apis:
                content += f"❌ **失败的API**: {', '.join(failed_apis)}\n"
            content += "\n"
        
        # 添加比赛详情
        if games_summary:
            content += "📋 **今日比赛详情**:\n\n"
            content += games_summary
            content += "\n"

        # 添加每场比赛得分王
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
        
        # 添加API状态信息
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
        # 50+得分通知
        title = "🔥 NBA50 优惠预警!"
        content = f"球员 **{player}** ({team}) 在今天的比赛中砍下了 **{pts}** 分！\n\n比赛: {matchup}\n\n**DoorDash NBA50** 优惠码预计将于明日 9:00 AM PT 生效！\n\n"
        
        # 添加API状态信息
        if api_status:
            content += f"📡 **数据来源**: {api_status.get('successful_api', 'Unknown')}\n"
            failed_apis = api_status.get('failed_apis', [])
            if failed_apis:
                content += f"❌ **失败的API**: {', '.join(failed_apis)}\n"
            content += "\n"
        
        # 添加比赛详情（如果有）
        if games_summary:
            content += "📋 **今日所有比赛**:\n\n"
            content += games_summary
            content += "\n"

        # 添加每场比赛得分王
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
        
        # 根据webhook类型检查成功状态码
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
        import traceback
        print(f"详细错误信息: {traceback.format_exc()}")

if __name__ == "__main__":
    # 运行完整的NBA监控
    check_for_50_points()
