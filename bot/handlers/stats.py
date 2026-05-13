from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram import Router

from bot.services.github import get_repo_stats, get_contributors, get_stargazers, get_repo_traffic
from bot.ui.panel import CTX_RELEASES, PanelManager
from utils.formatters import format_size, mini_bar, bar

async def show_repo_stats(msg_or_query, session, telegram_id, repo_name):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    try: await msg_or_query.message.edit_text("<pre>⏳  Loading stats...</pre>", parse_mode="HTML")
    except: pass
    data = await get_repo_stats(session, telegram_id, repo_name)
    if "error" in data:
        await msg_or_query.message.answer("❌ Failed to load stats.")
        return
    languages = data.get("languages",{})
    total_bytes = sum(languages.values()) or 1
    days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    activity = data.get("daily_activity",{})
    day_vals = [activity.get(d,0) for d in days]
    sparkline = mini_bar(day_vals)
    lines = ["---",
             f"  📦  {format_size(data['size'])}       📝  {data['total_commits']} commits",
             f"  ⭐  {data['stars']} stars      🍴  {data['forks']} forks",
             f"  🔥  {data['streak']} day streak",
             "---","  LANGUAGES","···"]
    for lang, count in sorted(languages.items(), key=lambda x:x[1], reverse=True)[:4]:
        pct = (count/total_bytes)*100
        b = bar(count, total_bytes, 7)
        lines.append(f"  {h(lang):<12}  {pct:4.1f}%  {b}")
    lines += ["---","  ACTIVITY  (last 7 days)","···", f"  {sparkline}",
              f"  {' '.join(d[:1] for d in days)}"]
    if data.get("top_files"):
        lines += ["---","  MOST COMMITTED FILES","···"]
        for i, f in enumerate(data["top_files"],1):
            lines.append(f"  {i}.  {h(f['path'].split('/')[-1][:25])}  {f['commits']} commits")
    text = panel(f"📊  Stats  ·  {h(repo_name.split('/')[-1])}", lines)
    await pm.update(telegram_id, chat_id, "stats", f"<pre>{text}</pre>",
                    InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="👁 Traffic",callback_data=f"stats_traffic:{repo_name}"),
                        InlineKeyboardButton(text="⭐ Stargazers",callback_data=f"stats_stargazers:{repo_name}"),
                        InlineKeyboardButton(text="👥 Contributors",callback_data=f"stats_contributors:{repo_name}"),
                    ],[
                        InlineKeyboardButton(text="⬅️ Back to Repo",callback_data=f"repo_open:{repo_name}"),
                        InlineKeyboardButton(text="🏠 Home",callback_data="home"),
                    ]]))

router = Router()
