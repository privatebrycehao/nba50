import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from lib.display import get_home_away_competitors
from lib.webhook import (
    create_discord_messages,
    create_lark_messages,
    detect_webhook_type,
    send_webhook,
)


def get_pacific_time_date():
    utc_now = datetime.now(timezone.utc)
    pacific_now = utc_now.astimezone(ZoneInfo('America/Los_Angeles'))
    
    print(f"🕐 UTC时间: {utc_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"🕐 美西时间: {pacific_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    return pacific_now.date()

def get_games_from_espn():
    print("🏀 尝试使用ESPN API获取数据...")
    pacific_today = get_pacific_time_date()
    games_by_id = {}
    successful_requests = 0

    for check_date in [pacific_today, pacific_today - timedelta(days=1)]:
        date_str = check_date.strftime('%Y%m%d')
        espn_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
        print(f"  检查美西时间日期: {date_str} ({check_date.strftime('%Y-%m-%d')})")
        try:
            response = requests.get(espn_url, timeout=30)
            if response.status_code != 200:
                print(f"    ESPN API响应错误: {response.status_code}")
                continue
            data = response.json()
            successful_requests += 1
        except (requests.RequestException, ValueError) as exc:
            print(f"    ESPN API获取失败: {type(exc).__name__}")
            continue

        games = data.get('events', [])
        candidates = [g for g in games if g.get('status', {}).get('type', {}).get('name', '') in
                      ['STATUS_FINAL', 'STATUS_IN_PROGRESS', 'STATUS_HALFTIME']]
        print(f"    发现 {len(games)} 场比赛，其中 {len(candidates)} 场可检查")
        for game in candidates:
            game_id = game.get('id')
            if game_id:
                games_by_id[game_id] = game

    if successful_requests == 0:
        return None, None
    print(f"✅ ESPN API 去重后获取到 {len(games_by_id)} 场可检查比赛")
    return list(games_by_id.values()), "espn"

def get_espn_summary(game_id):
    try:
        summary_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
        response = requests.get(summary_url, timeout=30)
        if response.status_code != 200:
            print(f"  ESPN summary响应错误: {response.status_code}")
            return None
        return response.json()
    except Exception as e:  # noqa: BLE001
        print(f"  获取ESPN summary失败: {e}")
        return None

def extract_players_points_from_summary(summary):
    players = []
    if not summary:
        print("    summary数据为空")
        return players

    try:
        boxscore = summary.get("boxscore", {})
        if not boxscore:
            print("    summary中没有boxscore数据")
            return players
            
        team_blocks = boxscore.get("players", [])
        if not team_blocks:
            print("    boxscore中没有players数据")
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
                                "id": athlete_obj.get("id"),
                                "name": athlete_name,
                                "points": points,
                                "team": team_name,
                            })
                            if points >= 50:
                                print(f"        ⚠️ 发现高分: {athlete_name} - {points}分")
                        except (ValueError, TypeError):
                            points = 0
    except Exception as e:  # noqa: BLE001
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
                                "id": athlete_obj.get("id"),
                                "name": player_name,
                                "points": points_int,
                                "team": team_abbr,
                            })
                        except (ValueError, TypeError):
                            pass
    except Exception as e:  # noqa: BLE001
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
                    home_team, away_team = get_home_away_competitors(game)
                    if home_team and away_team:
                        home_name = home_team.get('team', {}).get('abbreviation', 'UNK')
                        away_name = away_team.get('team', {}).get('abbreviation', 'UNK')
                        home_score = home_team.get('score', 0)
                        away_score = away_team.get('score', 0)
                        
                        matchup = f"{away_name} {away_score} - {home_score} {home_name}"
                        summary_lines.append(f"🏀 **{matchup}**")
                        summary_lines.append("")
            except Exception as e:  # noqa: BLE001
                summary_lines.append(f"🏀 比赛信息解析错误: {e}")
                summary_lines.append("")
    
    return "\n".join(summary_lines) if summary_lines else "无法生成比赛摘要"

def check_espn_game_for_50_points(game, highest_scorers):
    status = game.get("status", {}).get("type", {}).get("name", "")
    if status not in ["STATUS_FINAL", "STATUS_IN_PROGRESS", "STATUS_HALFTIME"]:
        return []

    home_team, away_team = get_home_away_competitors(game)
    if not home_team or not away_team:
        raise ValueError(f"比赛 {game.get('id', 'unknown')} 缺少有效 homeAway 字段")
    matchup = f"{away_team.get('team', {}).get('abbreviation', 'UNK')} @ {home_team.get('team', {}).get('abbreviation', 'UNK')}"
    print(f"  检查比赛: {matchup}")

    game_id = game.get("id")
    players = []
    if game_id:
        print(f"    获取比赛 {game_id} 的详细数据...")
        players = extract_players_points_from_summary(get_espn_summary(game_id))
    if not players:
        players = extract_top_scorers_from_event(game)

    if not players:
        return []

    top_player = max(players, key=lambda player: player.get("points", 0))
    highest_scorers.append({
        "matchup": matchup,
        "name": top_player.get("name", "Unknown"),
        "points": top_player.get("points", 0),
        "team": top_player.get("team", "UNK"),
    })

    alerts = []
    for player in players:
        if player.get("points", 0) >= 50:
            alerts.append({
                **player,
                "game_id": game_id,
                "matchup": matchup,
            })
            print(f"🔥 发现50+得分: {player.get('name')} ({player.get('team')}) - {player.get('points')}分")
    return alerts

def send_notification(player=None, pts=None, team=None, matchup=None, message_type="50_points", error_details=None, api_status=None, games_count=0, games_summary=None, highest_scorers=None):
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        raise RuntimeError("未设置 DISCORD_WEBHOOK 环境变量")
    
    webhook_type = detect_webhook_type(webhook_url)
    
    if message_type == "no_games":
        title = "📅 今日暂无可检查的NBA比赛"
        content = "今日暂无已完成或进行中的NBA比赛\n\n"
        content += "这通常表示今天没有比赛、比赛尚未开始，或当前还没有可用于50分监控的结果。\n\n"
        
        if api_status:
            content += f"📡 **数据来源**: {api_status.get('successful_api', 'Unknown')}\n"
            
            failed_apis = api_status.get('failed_apis', [])
            if failed_apis:
                content += f"❌ **失败的API**: {', '.join(failed_apis)}\n"
            content += "\n"
        
        content += f"⏰ 检查时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_messages(title, content, "grey")
        else:
            data = create_discord_messages("监控完成", content, 10197915)
    elif message_type == "no_50_points":
        title = "📊 今日监控完成"
        content = "已检查完今日所有比赛，暂无球员得分达到50+\n\n"
        
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
        
        content += f"⏰ 检查时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_messages(title, content, "yellow")
        else:
            data = create_discord_messages("未发现50+得分", content, 15844367)
    elif message_type == "error":
        title = "⚠️ 监控程序遇到错误"
        error_desc = "NBA50监控程序在运行时遇到错误\n\n"
        
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
        
        error_desc += f"⏰ 错误时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_messages(title, error_desc, "red")
        else:
            data = create_discord_messages("程序执行异常", error_desc, 15158332)
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
        
        content += f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
        
        if webhook_type == "lark":
            data = create_lark_messages(title, content, "red")
        else:
            data = create_discord_messages("50分记录达成！", content, 16711680)
    
    print(f"📤 正在发送{message_type}类型的{webhook_type}通知...")
    send_webhook(webhook_url, webhook_type, data)
    if message_type == "50_points":
        print(f"✅ 成功发送通知: {player} {pts}分")
    else:
        print("✅ 成功发送监控完成通知")

def _state_path():
    return Path(os.getenv("NBA50_STATE_FILE", ".nba50_state.json"))


def load_sent_state():
    path = _state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        sent = data.get("sent", {})
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        return {
            key: value for key, value in sent.items()
            if datetime.fromisoformat(value).astimezone(timezone.utc) >= cutoff
        }
    except (OSError, ValueError, TypeError):
        print("⚠️ 幂等状态文件无效，将从空状态开始")
        return {}


def save_sent_state(sent):
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps({"sent": sent}, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def alert_identity(alert):
    player_identity = alert.get("id") or f"{alert.get('team', '')}:{alert.get('name', '').strip().casefold()}"
    return f"{alert.get('game_id')}:{player_identity}"


def send_test_message():
    webhook_url = os.getenv('DISCORD_WEBHOOK')
    if not webhook_url:
        raise RuntimeError("未设置 DISCORD_WEBHOOK 环境变量")
    webhook_type = detect_webhook_type(webhook_url)
    title = "NBA50 Webhook 测试"
    content = "固定测试消息：webhook_test 模式未访问 ESPN。"
    payloads = (create_lark_messages(title, content, "blue") if webhook_type == "lark"
                else create_discord_messages(title, content, 3447003))
    send_webhook(webhook_url, webhook_type, payloads)


def check_for_50_points():
    print("🤖 NBA50监控程序启动...")
    highest_scorers = []
    api_status = {'failed_apis': [], 'successful_api': None}

    try:
        games_data, api_source = get_games_from_espn()
        if games_data is None:
            api_status['failed_apis'].append("ESPN API")
            raise RuntimeError("所有API都无法获取数据")

        games_count = len(games_data)
        api_status['successful_api'] = "ESPN API"
        if not games_data:
            send_notification(message_type="no_games", api_status=api_status, games_count=0)
            return

        games_summary = generate_game_summary(games_data, api_source)
        alerts = []
        for game in games_data:
            alerts.extend(check_espn_game_for_50_points(game, highest_scorers))

        sent = load_sent_state()
        pending = []
        seen = set()
        for alert in alerts:
            key = alert_identity(alert)
            if key not in sent and key not in seen:
                pending.append((key, alert))
                seen.add(key)

        if not alerts:
            print("✅ 监控完成，未发现50+得分")
            send_notification(
                message_type="no_50_points",
                api_status=api_status,
                games_count=games_count,
                games_summary=games_summary,
                highest_scorers=highest_scorers,
            )
            return

        if not pending:
            print("✅ 所有50+记录均已通知，本次无需重复发送")
            return

        for key, alert in pending:
            send_notification(
                alert.get("name"), alert.get("points"), alert.get("team"), alert.get("matchup"),
                "50_points", api_status=api_status, games_count=games_count,
                games_summary=games_summary, highest_scorers=highest_scorers,
            )
            sent[key] = datetime.now(timezone.utc).isoformat()
            save_sent_state(sent)
    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        print(f"获取比赛数据时出错: {error_msg}")
        try:
            send_notification(message_type="error", error_details=error_msg, api_status=api_status)
        except Exception as notify_exc:  # noqa: BLE001
            print(f"错误通知发送失败: {type(notify_exc).__name__}: {notify_exc}")
        raise


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "webhook_test":
        send_test_message()
    else:
        check_for_50_points()
