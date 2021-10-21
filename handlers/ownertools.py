import os
import shutil
import sys
import traceback
from functools import wraps
from os import environ, execle

import heroku3
import psutil
from config import (
    BOT_USERNAME,
    GROUP_SUPPORT,
    HEROKU_API_KEY,
    HEROKU_APP_NAME,
    HEROKU_URL,
    OWNER_ID,
    U_BRANCH,
    UPSTREAM_REPO,
)
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError
from handlers.song import get_text, humanbytes
from handlers import __version__
from helpers.database import db
from helpers.dbtools import main_broadcast_handler
from helpers.decorators import sudo_users_only
from helpers.filters import command
from pyrogram import Client, filters
from pyrogram.types import Message


# Stats Of Your Bot
@Client.on_message(command("stats"))
@sudo_users_only
async def botstats(_, message: Message):
    total, used, free = shutil.disk_usage(".")
    total = humanbytes(total)
    used = humanbytes(used)
    free = humanbytes(free)
    cpu_usage = psutil.cpu_percent()
    ram_usage = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage("/").percent
    total_users = await db.total_users_count()
    await message.reply_text(
        text=f"**📊 Stats of @{BOT_USERNAME}** \n\n**🤖 Bot version:** `{__version__}` \n\n**🙎🏼 Total users:** \n » **On bot pm:** `{total_users}` \n\n**💾 Disk usage:** \n » **Disk space:** `{total}` \n » **Used:** `{used}({disk_usage}%)` \n » **Free:** `{free}` \n\n**🎛 Hardware usage:** \n » **CPU Usage:** `{cpu_usage}%` \n » **RAM Usage:** `{ram_usage}%`",
        parse_mode="Markdown",
        quote=True,
    )


@Client.on_message(
    filters.private
    & filters.command("broadcast")
    & filters.user(OWNER_ID)
    & filters.reply
)
async def broadcast_handler_open(_, m: Message):
    await main_broadcast_handler(m, db)


@Client.on_message(filters.private & filters.command("block"))
@sudo_users_only
async def ban(c: Client, m: Message):
    if len(m.command) == 1:
        await m.reply_text(
            "» This command for ban user from using your bot, read /help for more info !",
            quote=True,
        )
        return
    try:
        user_id = int(m.command[1])
        ban_duration = m.command[2]
        ban_reason = " ".join(m.command[3:])
        ban_log_text = f"🚷 **Banned user !** \n\nUser id: `{user_id}` \nDuration: `{ban_duration}` \nReason: `{ban_reason}`"
        try:
            await c.send_message(
                user_id,
                f"😕 Sorry, you're banned!** \n\nReason: `{ban_reason}` \nDuration: `{ban_duration}` day(s). \n\n**💬 Message from owner: ask in @{GROUP_SUPPORT} if you think this was an mistake.",
            )
            ban_log_text += "\n\n✅ This notification was sent to that user"
        except:
            traceback.print_exc()
            ban_log_text += f"\n\n❌ **Failed sent this notification to that user** \n\n`{traceback.format_exc()}`"
        await db.ban_user(user_id, ban_duration, ban_reason)
        print(ban_log_text)
        await m.reply_text(ban_log_text, quote=True)
    except:
        traceback.print_exc()
        await m.reply_text(
            f"❌ An error occoured, traceback is given below:\n\n`{traceback.format_exc()}`",
            quote=True,
        )


# Unblock User
@Client.on_message(filters.private & filters.command("unblock"))
@sudo_users_only
async def unban(c: Client, m: Message):
    if len(m.command) == 1:
        await m.reply_text(
            "» This command for unban user, read /help for more info !", quote=True
        )
        return
    try:
        user_id = int(m.command[1])
        unban_log_text = f"🆓 **Unbanned user !** \n\n**user id:**{user_id}"
        try:
            await c.send_message(user_id, "🎊 Congratulations, you was unbanned!")
            unban_log_text += "\n\n✅ this notification was sent to that user"
        except:
            traceback.print_exc()
            unban_log_text += f"\n\n❌ **Failed sent this notification to that user** \n\n`{traceback.format_exc()}`"
        await db.remove_ban(user_id)
        print(unban_log_text)
        await m.reply_text(unban_log_text, quote=True)
    except:
        traceback.print_exc()
        await m.reply_text(
            f"❌ An error occoured, traceback is given below:\n\n`{traceback.format_exc()}`",
            quote=True,
        )


# Blocked User List
@Client.on_message(filters.private & filters.command("blocklist"))
@sudo_users_only
async def _banned_usrs(_, m: Message):
    all_banned_users = await db.get_all_banned_users()
    banned_usr_count = 0
    text = ""
    async for banned_user in all_banned_users:
        user_id = banned_user["id"]
        ban_duration = banned_user["ban_status"]["ban_duration"]
        banned_on = banned_user["ban_status"]["banned_on"]
        ban_reason = banned_user["ban_status"]["ban_reason"]
        banned_usr_count += 1
        text += f"🆔 **User id**: `{user_id}`\n⏱ **Duration**: `{ban_duration}`\n🗓 **Banned date**: `{banned_on}`\n💬 **Reason**: `{ban_reason}`\n\n"
    reply_text = f"🚷 **Total banned:** `{banned_usr_count}`\n\n{text}"
    if len(reply_text) > 4096:
        with open("banned-user-list.txt", "w") as f:
            f.write(reply_text)
        await m.reply_document("banned-user-list.txt", True)
        os.remove("banned-user-list.txt")
        return
    await m.reply_text(reply_text, True)


# ====== UPDATER ======

REPO_ = UPSTREAM_REPO
BRANCH_ = U_BRANCH


@Client.on_message(command("update") & filters.user(OWNER_ID))
async def updatebot(_, message: Message):
    msg = await message.reply_text("**Updating bot, please wait for a while...**")
    try:
        repo = Repo()
    except GitCommandError:
        return await msg.edit("**Invalid git command !**")
    except InvalidGitRepositoryError:
        repo = Repo.init()
        if "upstream" in repo.remotes:
            origin = repo.remote("upstream")
        else:
            origin = repo.create_remote("upstream", REPO_)
        origin.fetch()
        repo.create_head(U_BRANCH, origin.refs.main)
        repo.heads.main.set_tracking_branch(origin.refs.main)
        repo.heads.main.checkout(True)
    if repo.active_branch.name != U_BRANCH:
        return await msg.edit(
            f"**Sorry, you are using costum branch named:** `{repo.active_branch.name}`!\n\nchange to `{U_BRANCH}` branch to continue update!"
        )
    try:
        repo.create_remote("upstream", REPO_)
    except BaseException:
        pass
    ups_rem = repo.remote("upstream")
    ups_rem.fetch(U_BRANCH)
    if not HEROKU_URL:
        try:
            ups_rem.pull(U_BRANCH)
        except GitCommandError:
            repo.git.reset("--hard", "FETCH_HEAD")
        await run_cmd("pip3 install --no-cache-dir -r requirements.txt")
        await msg.edit("**Update finished, restarting now...**")
        args = [sys.executable, "main.py"]
        execle(sys.executable, *args, environ)
        sys.exit()
        return
    else:
        await msg.edit("`Heroku detected!`")
        await msg.edit(
            "`Updating and restarting is started, please wait for 5-10 minutes!`"
        )
        ups_rem.fetch(U_BRANCH)
        repo.git.reset("--hard", "FETCH_HEAD")
        if "heroku" in repo.remotes:
            remote = repo.remote("heroku")
            remote.set_url(HEROKU_URL)
        else:
            remote = repo.create_remote("heroku", HEROKU_URL)
        try:
            remote.push(refspec="HEAD:refs/heads/main", force=True)
        except BaseException as error:
            await msg.edit(f"🚫 **Updater error** \n\nTraceBack : `{error}`")
            return repo.__del__()


# HEROKU LOGS


async def edit_or_send_as_file(
    text: str,
    message: Message,
    client: Client,
    caption: str = "`Result!`",
    file_name: str = "result",
    parse_mode="md",
):
    """Send As File If Len Of Text Exceeds Tg Limit Else Edit Message"""
    if not text:
        await message.edit("`There is something other than text, aborting...`")
        return
    if len(text) <= 1024:
        return await message.edit(text, parse_mode=parse_mode)

    await message.edit("`Output is too large, sending as file!`")
    file_names = f"{file_name}.text"
    open(file_names, "w").write(text)
    await client.send_document(message.chat.id, file_names, caption=caption)
    await message.delete()
    if os.path.exists(file_names):
        os.remove(file_names)
    return


heroku_client = heroku3.from_key(HEROKU_API_KEY) if HEROKU_API_KEY else None


def _check_heroku(func):
    @wraps(func)
    async def heroku_cli(client, message):
        heroku_app = None
        if not heroku_client:
            await message.reply_text("`Please add heroku api key to use this feature!`")
        elif not HEROKU_APP_NAME:
            await edit_or_reply(
                message, "`Please add heroku app name to use this feature!`"
            )
        if HEROKU_APP_NAME and heroku_client:
            try:
                heroku_app = heroku_client.app(HEROKU_APP_NAME)
            except:
                await message.reply_text(
                    message,
                    "`Heroku api key and app name doesn't match, please recheck`",
                )
            if heroku_app:
                await func(client, message, heroku_app)

    return heroku_cli


@Client.on_message(command("logs"))
@sudo_users_only
@_check_heroku
async def logswen(client: Client, message: Message, happ):
    msg = await message.reply_text("`Please wait for a moment!`")
    logs = happ.get_log()
    capt = f"Heroku logs of `{HEROKU_APP_NAME}`"
    await edit_or_send_as_file(logs, msg, client, capt, "logs")


# Restart Bot
@Client.on_message(command("restart") & filters.user(OWNER_ID))
@_check_heroku
async def restart(client: Client, message: Message, hap):
    await message.reply_text("`Restarting now, please wait...`")
    hap.restart()


# Set Heroku Var
@Client.on_message(command("setvar") & filters.user(OWNER_ID))
@_check_heroku
async def setvar(client: Client, message: Message, app_):
    msg = await message.reply_text(message, "`please wait...`")
    heroku_var = app_.config()
    _var = get_text(message)
    if not _var:
        await msg.edit("**Usage:** `/setvar (var) (value)`")
        return
    if " " not in _var:
        await msg.edit("**Usage:** `/setvar (var) (value)`")
        return
    var_ = _var.split(" ", 1)
    if len(var_) > 2:
        await msg.edit("**Usage:** `/setvar (var) (value)`")
        return
    _varname, _varvalue = var_
    await msg.edit(f"**Variable:** `{_varname}` \n**new value:** `{_varvalue}`")
    heroku_var[_varname] = _varvalue


# Delete Heroku Var
@Client.on_message(command("delvar") & filters.user(OWNER_ID))
@_check_heroku
async def delvar(client: Client, message: Message, app_):
    msg = await message.reply_text(message, "`Please wait...!`")
    heroku_var = app_.config()
    _var = get_text(message)
    if not _var:
        await msg.edit("`Give a var name to delete!`")
        return
    if _var not in heroku_var:
        await msg.edit("`This var doesn't exists!`")
        return
    await msg.edit(f"Sucessfully deleted var `{_var}`")
    del heroku_var[_var]
