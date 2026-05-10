
from bot.services.github import get_gists, create_gist
from bot.states.flow import GistFlow
from bot.ui.keyboards import gists_kb
from utils.formatters import time_ago

async def show_gists(msg_or_query, session, telegram_id):
    gists = await get_gists(session, telegram_id)
    lines = ["---", f"  {len(gists)} gists","---"]
    for g in gists:
        pub = "🌍" if g["public"] else "🔒"
        lines += [f"  {pub}  {h(g['description'][:40])}", f"       {h(', '.join(g['files'][:2]))}","···"]
    if not gists: lines.append("  No gists yet.")
    text = panel("📋  Your Gists", lines)
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    try: await msg.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=gists_kb(gists))
    except: await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=gists_kb(gists))

async def start_create_gist(query, state):
    await state.set_state(GistFlow.creating_filename)
    text = panel("➕  New Gist", ["---","  Type the filename:","  e.g.  notes.md  or  script.py"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="gist_list")]]))

@router.message(GistFlow.creating_filename)
async def gist_filename_received(message, state):
    await state.update_data(filename=message.text.strip())
    await state.set_state(GistFlow.creating_description)
    await message.answer("<pre>" + panel("📝  Gist Description",["---","  Type description (or /skip):"]) + "</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭️ Skip",callback_data="gist_skip_desc"), InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

@router.message(GistFlow.creating_description)
async def gist_desc_received(message, state):
    await state.update_data(description=message.text.strip())
    await state.set_state(GistFlow.creating_content)
    await message.answer("<pre>" + panel("📄  Gist Content",["---","  Type or paste the content:"]) + "</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

@router.message(GistFlow.creating_content)
async def gist_content_received(message, state, session, telegram_id):
    data = await state.get_data()
    await state.clear()
    result = await create_gist(session, telegram_id, data.get("filename","file.txt"), message.text or "", data.get("description",""))
    ok = "error" not in result
    text = panel("✅  Gist Created!" if ok else "❌  Failed", ["---", f"  🔗  {h(result.get('url',''))}" if ok else f"  Error {result.get('error','')}"])
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                              InlineKeyboardButton(text="🔗 View",url=result["url"]) if ok else InlineKeyboardButton(text="🔄 Retry",callback_data="gist_create"),
                              InlineKeyboardButton(text="📋 All Gists",callback_data="gist_list"),
                          ]]))

async def confirm_delete_gist(query, session, telegram_id, gist_id):
    text = panel("🗑️  Delete Gist?", ["---","  This cannot be undone."])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="✅ Yes, delete",callback_data=f"gist_delete_confirm:{gist_id}"),
                                       InlineKeyboardButton(text="❌ Cancel",callback_data="gist_list"),
                                   ]]))
