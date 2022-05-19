import asyncio
import contextlib
import csv
import glob
import logging
import os
import traceback

import aiofiles
import numpy as np
from pyrogram import Client
from pyrogram.errors import FloodWait, PeerFlood, UserAlreadyParticipant
from pyrogram.errors.exceptions import UserPrivacyRestricted
from pyrogram.types import Message, User


def digit_wrap(o):
    try:
        return int(o)
    except ValueError:
        return str(o)


async def distribute_and_add_users(
    clients: list, user_list: list, target, msg: Message = None
):
    lists__ = distribute_user_list_for_clients(user_list, len(clients))
    if len(clients) == 1:
        return await add_chunks_of_users(clients[0], user_list, target, msg)
    tasks = [
        add_chunks_of_users(client, lists__[i], target, msg)
        for i, client in enumerate(clients)
    ]
    return await asyncio.gather(*tasks)


def distribute_user_list_for_clients(user_list: list, num_clients: int) -> list:
    return list(np.array_split(user_list, num_clients))


import random


async def scrap_users(client: Client, chat_id, alg, alww, alwm):
    if isinstance(client, list):
        client = random.choice(client)
    with contextlib.suppress(Exception):
        chat_id = (await client.join_chat(chat_id)).id
    with open(f"users_{chat_id}.csv", "w") as f:
        writer = csv.writer(f, delimiter=",", lineterminator="\n")
        writer.writerow(
            [
                "first_name",
                "last_name",
                "username (if any)",
                "id",
                "is_bot",
                "last seen (status)",
            ]
        )
        async for user in client.iter_chat_members(chat_id):
            if alg and user.user.status == "long_time_ago":
                logging.info(f"Ignoring : {user.user.id} - LongTimeAGO")
                continue
            if alww and user.user.status == "within_week":
                logging.info(f"Ignoring : {user.user.id} - WeekSAGO")
                continue
            if alwm and user.user.status == "within_month":
                logging.info(f"Ignorning : {user.user.id} - Months Ago")
                continue
            logging.info(f"Scapping User : {user.user.id}")
            _user: User = user.user
            writer.writerow(
                [
                    _user.first_name,
                    (_user.last_name or "Nil"),
                    (_user.username or "Nil"),
                    int(_user.id),
                    _user.access_hash,
                    (_user.is_bot or "False"),
                    (_user.status or "Nil"),
                ]
            )
    return f"users_{chat_id}.csv"


def load_from_csv_and_fetch_user_id_list(file_path: str, use_m=False) -> list:
    user_list = []
    with open(file_path, "r", encoding="UTF-8") as f:
        reader = csv.reader(f, delimiter=",", lineterminator="\n")
        for i in reader:
            if use_m:
                if i[2] and i[2] != "username":
                    user_list.append(i[2])
            else:
                user = i[3]
                _hash = i[4]
                if user.isdigit() and _hash != "access_hash":
                    user_list.append([int(user), _hash])
    return user_list


from pyrogram.raw import types
from pyrogram.raw.functions.channels import InviteToChannel


async def add_user(client: Client, _access_hash: str, _user_id: int, _peer):
    # sourcery skip: remove-unnecessary-cast
    if (not _access_hash) and (_user_id):
        return await client.add_chat_members(_peer, [_user_id])
    _user = types.InputPeerUser(user_id=int(_user_id), access_hash=int(_access_hash))
    await client.send(InviteToChannel(channel=_peer, users=[_user]))


def walk_dir(path):
    path = f"{path}*.session"
    return list(glob.iglob(path))


async def log(_text: str, client, msg=None):
    first_ = f"[{client.myself.first_name}_{client.myself.id}]: "
    to_log = first_ + _text
    logging.info(to_log)
    if msg and isinstance(msg, Message):
        with contextlib.suppress(Exception):
            await msg.edit(to_log)


async def write_file(content, file_name):
    if os.path.exists(file_name):
        os.remove(file_name)
    async with aiofiles.open(file_name, "w") as f:
        await f.write(content)
    return file_name


async def add_chunks_of_users(
    client: Client, user_list: list, target, msg: Message = None
):
    with contextlib.suppress(Exception):
        target = (await client.join_chat(target)).id
    try:
        peer_chat = await client.resolve_peer(target)
    except Exception:
        return await log("Target chat not found - invalid peer", client, msg)
    msg = await log("Adding users...", client, msg)
    error_s = f"Errors Raised in {client.myself.first_name}_{client.myself.id}: \n\n"
    added = 0
    failed = 0
    privacy_restricted = 0
    for u_chunk in user_list:
        if isinstance(u_chunk, str):
            __user_id = str(u_chunk)
            __access_h = None
        else:
            __user_id = int(u_chunk[0])
            __access_h = int(u_chunk[1])
        try:
            await add_user(client, __access_h, __user_id, peer_chat)
        except UserPrivacyRestricted:
            privacy_restricted += 1
            await log(
                f"User {__user_id} has enabled privacy mode, so failed to add him!",
                client,
                msg,
            )
            continue
        except FloodWait as e:
            await asyncio.sleep(e.x + 5)
            continue
        except PeerFlood:
            await asyncio.sleep(5)
            continue
        except UserAlreadyParticipant:
            await log(
                f"User <code>{__user_id}</code> is already an participant of the chat"
            )
            continue
        except Exception as e:
            error_s += f"{__user_id}: {traceback.format_exc()} \n\n"
            failed += 1
            await log(
                f"Failed to add user - {__user_id} to {target} \nError : {e}",
                client,
                msg,
            )
            continue
        added += 1
        await asyncio.sleep(7)
        await log(f"Added user - {__user_id} to {target}", client, msg)
    if error_s:
        await write_file(error_s, f"errors_{client.myself.id}.txt")
        if msg:
            await msg.reply_document(
                f"errors_{client.myself.id}.txt",
                f"<b>All Errors Raised during the session and client {client.myself.first_name}_{client.myself.id}</b>",
            )
    await client.stop()
    return await log(
        f"<b>Added :</b> {added} \n<b>Failed :</b> {failed} \n<b>Privacy restricted :</b> {privacy_restricted} \n<b>Task Completed</b>",
        client,
        msg,
    )
