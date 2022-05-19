import asyncio

from pyrogram import Client, filters, idle
from pyrogram.types import *

from config import *
from loggers import *
from methods import *

bot_client = Client("botp", api_id=api_id, api_hash=api_hash, bot_token=BOT_TOKEN)
ask_session = not os.path.exists("./session/")

_clients_ = []


async def start_all_client():
    if ask_session:
        return
    sessions_ = walk_dir("./session/")
    if not sessions_:
        return
    total_ = 0
    errored = 0
    for i in sessions_:
        total_ += 1
        try:
            _clients_.append(await start_and_return_client(i))
        except Exception as e:
            logging.info(f"Failed to start client: {total_} \nError : {e}")
            errored += 1
            continue
    logging.info(f"Started {total_ - errored} clients")
    if errored > 0:
        logging.info(f"Failed to start {errored} clients")


async def start_and_return_client(session_):
    if session_.endswith(".session"):
        session_ = session_.split(".session")[0]
    client_ = Client(
        session_,
        api_id=api_id,
        api_hash=api_hash,
        device_model="iPhone 11 Pro",
        system_version="13.3",
        app_version="8.6",
    )
    await client_.start()
    client_.myself = await client_.get_me()
    return client_


@bot_client.on_message(filters.command("scrap", prefixes=["/", "!"]))
async def _scrap(client: Client, message: Message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("<b>Who are you?</b>")
    chat_id = await message.from_user.ask("Enter the chat id or username :")
    await chat_id.delete()
    await chat_id.request.delete()
    if not chat_id.text:
        return await message.reply("No chat id or username entered!")
    if ask_session:
        session_ = await message.from_user.ask("Enter the string session :")
        if not session_.text:
            return await message.reply("No session entered!")
        try:
            client__ = await start_and_return_client(session_.text)
        except Exception as e:
            return await message.reply(
                f"Failed to start session !\n<b>Error:</b> <code>{e}</code>"
            )
    else:
        client__ = _clients_
    if not client__:
        return await message.reply("No sessions found!")
    _lag = await message.from_user.ask(
        "Should i add members with status - 'long_time_ago'"
    )
    should_allow_long_time_ago = _lag.text and _lag.text.lower().startswith("n")
    await _lag.delete()
    await _lag.request.delete()
    _lwm = await message.from_user.ask(
        "Should i add members with status - 'last_seen_months_ago'?"
    )
    should_allow_lwm = _lwm.text and _lwm.text.lower().startswith("n")
    await _lwm.delete()
    await _lwm.request.delete()
    _lww = await message.from_user.ask(
        "Should i add members with status - 'last_seen_weeks_ago'?"
    )
    should_allow_lww = _lww.text and _lww.text.lower().startswith("n")
    await _lww.delete()
    await _lww.request.delete()
    chat_id = digit_wrap(chat_id.text)
    try:
        user_list = await scrap_users(
            client__,
            chat_id,
            should_allow_long_time_ago,
            should_allow_lww,
            should_allow_lwm,
        )
    except Exception as e:
        logging.error(traceback.format_exc())
        return await message.reply(
            "<b>Unable to fetch users from the chat!</b> \n\n<b>Error :</b><code>{}</code>".format(
                e
            )
        )
    await message.reply_document(
        user_list,
        f"Users of {chat_id} use /import replying to this file to add to group!",
    )


@bot_client.on_message(filters.command("import", prefixes=["/", "!"]))
async def import_and_add(client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply("<b>Reply to a document!</b>")
    csv_file = await message.reply_to_message.download()
    if ask_session:
        session_ = await message.from_user.ask("Enter the string session :")
        if not session_.text:
            return await message.reply("No session entered!")
        try:
            client__ = [await start_and_return_client(session_.text)]
        except Exception as e:
            return await message.reply(
                f"Failed to start session !\n<b>Error:</b> <code>{e}</code>"
            )
    else:
        client__ = _clients_
    if not client__:
        return await message.reply("No sessions found!")
    use_m = await message.from_user.ask("Do you want to use username to scrap? (y/n)")
    try:
        user_ids = load_from_csv_and_fetch_user_id_list(
            csv_file, use_m=use_m.text and use_m.text.lower().startswith("y")
        )
    except Exception as e:
        return await message.reply(
            f"Failed to load users from csv!\n<b>Error:</b> <code>{e}</code>"
        )
    now_c = await message.from_user.ask("Enter chat id to add users :")
    if not now_c.text:
        return await message.reply("No Chat Entity given!")
    chat_ = digit_wrap(now_c.text)
    k_ = await message.from_user.ask(
        "Do you wish to log results by bot too? (Can be spammy and cause floodwaits!)"
    )
    if not user_ids:
        return await message.reply("<b>No users found in the file!</b>")
    mo = await message.reply(f"Total users to add: {len(user_ids)}")
    mo = mo if (k_.text and k_.text.lower().startswith("y")) else None
    await distribute_and_add_users(client__, user_ids, chat_, mo)
    await asyncio.sleep(20)
    await mo.delete()
    await message.reply("Done! All Users Added to chat!")


async def run_bot():
    logging.info("Running Bot...")
    await bot_client.start()
    bot_client.myself = await bot_client.get_me()
    logging.info("Info: Bot Started!")
    logging.info("Idling...")
    await start_all_client()
    await idle()
    logging.warning("Exiting Bot....")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_bot())
