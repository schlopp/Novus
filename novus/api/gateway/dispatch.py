"""
Copyright (c) Kae Bartlett

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, NoReturn, cast

from ...models import Channel, Guild, GuildMember, Invite, Message, User
from ...models.channel import channel_builder
from ...utils import try_snowflake

if TYPE_CHECKING:
    from ... import payloads
    from .._http import HTTPConnection

__all__ = (
    'GatewayDispatch',
)


log = logging.getLogger("novus.gateway.dispatch")
dump = json.dumps


class GatewayDispatch:

    def __init__(self, parent: HTTPConnection) -> None:
        self.parent = parent
        self.cache = self.parent.cache
        self.EVENT_HANDLER: dict[
            str,
            Callable[
                [Any],  # dict, but we know about it
                Awaitable[tuple[str, Any] | None]
            ]
        ]
        self.EVENT_HANDLER = {
            # "Application command permissions update": None,
            # "Auto moderation rule create": None,
            # "Auto moderation rule update": None,
            # "Auto moderation rule delete": None,
            # "Auto moderation action execution": None,
            "CHANNEL_CREATE": self._handle_channel_create,
            "CHANNEL_UPDATE": self._handle_channel_update,
            "CHANNEL_DELETE": self._handle_channel_delete,
            "CHANNEL_PINS_UPDATE": self._handle_channel_pins_update,
            # "Thread create": None,
            # "Thread update": None,
            # "Thread delete": None,
            # "Thread list sync": None,
            # "Thread member update": None,
            # "Thread members update": None,
            "GUILD_CREATE": self._handle_guild_create,
            "GUILD_UPDATE": self._handle_guild_update,
            # "Guild delete": None,
            # "Guild audit log entry create": None,
            "GUILD_BAN_ADD": self._handle_guild_ban,
            "GUILD_BAN_REMOVE": self._handle_guild_unban,
            # "Guild emojis update": None,
            # "Guild stickers update": None,
            # "Guild integrations update": None,
            # "Guild member add": None,
            # "Guild member remove": None,
            # "Guild member update": None,
            # "Guild members chunk": None,
            # "Guild role create": None,
            # "Guild role update": None,
            # "Guild role delete": None,
            # "Guild scheduled event create": None,
            # "Guild scheduled event update": None,
            # "Guild scheduled event delete": None,
            # "Guild scheduled event user add": None,
            # "Guild scheduled event user remove": None,
            # "Integration create": None,
            # "Integration update": None,
            # "Integration delete": None,
            # "Interaction create": None,
            "INVITE_CREATE": self._handle_invite_create,
            "INVITE_DELETE": self._handle_invite_delete,
            "MESSAGE_CREATE": self._handle_message_create,
            "MESSAGE_UPDATE": self._handle_message_edit,
            "MESSAGE_DELETE": self._handle_message_delete,
            # "Message delete bulk": None,
            # "Message reaction add": None,
            # "Message reaction remove": None,
            # "Message reaction remove all": None,
            # "Message reaction remove emoji": None,
            "PRESENCE_UPDATE": self._handle_presence_update,
            # "Stage instance create": None,
            # "Stage instance update": None,
            # "Stage instance delete": None,
            "TYPING_START": self._handle_typing,
            # "User update": None,
            # "Voice state update": None,
            # "Voice server update": None,
            # "Webhooks update": None,
        }

    async def _placeholder(self, _: dict[Any, Any]) -> NoReturn:
        raise NotImplementedError()

    async def handle_dispatch(self, event_name: str, data: dict) -> None:
        """
        Handle a Dispatch message from Discord.
        """

        if event_name == "READY":
            self.cache.user = User(state=self.parent, data=data['user'])
            self.cache.application_id = try_snowflake(data['application']['id'])
            self.resume_url = data['resume_gateway_url']
            self.session_id = data['session_id']
            return None

        coro = self.EVENT_HANDLER.get(event_name)
        if coro is None:
            log.warning(
                "Failed to parse event %s %s"
                % (event_name, dump(data))
            )
        else:
            await coro(data)

        if event_name in [
                "PRESENCE_UPDATE",
                "GUILD_CREATE",
                "MESSAGE_CREATE",
                "VOICE_STATE_UPDATE",
                "READY",
                "TYPING_START",
                "CHANNEL_UPDATE",
                "MESSAGE_UPDATE",
                "MESSAGE_DELETE"]:
            return None
        import os
        import pathlib
        base = pathlib.Path(__file__).parent.parent.parent.parent
        evt = base / "_GATEWAY" / event_name
        os.makedirs(evt, exist_ok=True)
        with open(evt / f"{self.parent.gateway.sequence}_{self.session_id}.json", "w") as a:
            json.dump(data, a, indent=4, sort_keys=True)

    async def _handle_guild_create(self, data: payloads.GatewayGuild) -> tuple[str, Guild] | None:
        guild = Guild(state=self.parent, data=data)
        await guild._sync(data=data)
        self.cache.guilds[guild.id] = guild
        self.cache.users.update({
            k: v._to_user()
            for k, v in guild._members.items()
        })
        self.cache.channels.update(guild._channels)
        self.cache.channels.update(guild._threads)
        self.cache.emojis.update(guild._emojis)
        self.cache.stickers.update(guild._stickers)
        self.cache.events.update(guild._guild_scheduled_events)
        return "guild_create", guild

    async def _handle_guild_update(self, data: payloads.GatewayGuild) -> tuple[str, Guild] | None:
        guild = Guild(state=self.parent, data=data)
        await guild._sync(data=data)
        current = self.cache.guilds.get(guild.id, None)
        if current is not None:
            guild._members = current._members
        self.cache.guilds[guild.id] = guild
        self.cache.channels.update(guild._channels)
        self.cache.channels.update(guild._threads)
        self.cache.emojis.update(guild._emojis)
        self.cache.stickers.update(guild._stickers)
        self.cache.events.update(guild._guild_scheduled_events)
        return "guild_update", guild

    async def _handle_typing(self, data: dict[Any, Any]) -> tuple[str, User | GuildMember] | None:
        # This event isn't good for a lot, but it DOES give us a new
        # member payload if the typing was started in a guild
        if "member" in data:
            _member: payloads.GuildMember = data["member"]
            guild = self.cache.guilds.get(data["guild_id"])
            if guild is None:
                log.info(
                    "Failed to get cached guild %s, ignoring typing event"
                    % data["guild_id"]
                )
                return None
            member = GuildMember(
                state=self.parent,
                data=_member,
                guild=guild,
            )
            guild._members[member.id] = member
            self.cache.users[member.id] = member._to_user()
            return "typing", member
        user = self.cache.users.get(data["user_id"])
        if user is None:
            log.info(
                "Failed to get cached user %s, ignoring typing event"
                % data["user_id"]
            )
            return None
        return "typing", user

    async def _handle_message_generic(self, data: payloads.Message) -> Message:
        """Handle message create and message edit."""
        message = Message(state=self.parent, data=data)
        author = message.author
        self.cache.users[message.author.id] = author._to_user()
        if message.guild_id:
            author = cast(GuildMember, author)
            guild = self.cache.guilds.get(message.guild_id)
            if guild is not None:
                message.guild = guild
                guild._members[author.id] = author
        return message

    async def _handle_message_create(self, data: payloads.Message) -> tuple[str, Message]:
        message = await self._handle_message_generic(data)
        return "message", message

    async def _handle_message_edit(self, data: payloads.Message) -> tuple[str, Message]:
        message = await self._handle_message_generic(data)
        return "message_edit", message

    async def _handle_message_delete(self, data: payloads.Message) -> tuple[str, tuple[int, int]]:
        return "message_delete", (int(data["channel_id"]), int(data["id"]),)

    async def _handle_channel_pins_update(self, data: dict[str, str]) -> None:
        return None

    async def _handle_presence_update(self, data: dict[Any, Any]) -> None:
        log.debug("Ignoring presence update %s" % dump(data))  # TODO

    async def _handle_channel_generic(self, data: payloads.Channel) -> Channel | None:
        channel = channel_builder(state=self.parent, data=data)
        if "guild_id" in data:
            guild = self.cache.guilds.get(int(data["guild_id"]))
            if guild is None:
                log.info(
                    "Failed to get guild %s from cache, ignoring channel create"
                    % data["guild_id"]
                )
                return None
            channel.guild = guild
            guild._channels[channel.id] = channel
            self.cache.channels[channel.id] = channel
        return channel

    async def _handle_channel_create(self, data: payloads.Channel) -> tuple[str, Channel] | None:
        channel = await self._handle_channel_generic(data)
        if channel is None:
            return None
        return "channel_create", channel

    async def _handle_channel_update(self, data: payloads.Channel) -> tuple[str, Channel] | None:
        channel = await self._handle_channel_generic(data)
        if channel is None:
            return None
        return "channel_update", channel

    async def _handle_channel_delete(self, data: payloads.Channel) -> tuple[str, Channel] | None:
        # Though we do get a channel in the payload, we'll try and get the one
        # from cache as a first point of contact instead of constructing a new
        # object
        channel_id = int(data["id"])
        channel = self.cache.channels.pop(channel_id, None)
        if channel:
            if isinstance(channel.guild, Guild):
                channel.guild._channels.pop(channel_id, None)
            return "channel_delete", channel

        # It's not cached - let's just build a new one
        channel = channel_builder(state=self.parent, data=data)
        if "guild_id" in data:
            guild = self.cache.guilds.get(int(data["guild_id"]))
            if guild is None:
                log.info(
                    "Failed to get guild %s from cache, ignoring channel delete"
                    % data["guild_id"]
                )
                return None
            channel.guild = guild
        return "channel_delete", channel

    async def _handle_guild_ban(self, data: dict[str, Any]) -> tuple[str, tuple[int, User]]:
        # Here we're going to build the user from scratch; guild member remove
        # will handle the user in cache
        user = User(state=self.parent, data=data["user"])
        return "guild_ban", (int(data["guild_id"]), user,)

    async def _handle_guild_unban(self, data: dict[str, Any]) -> tuple[str, tuple[int, User]]:
        user = User(state=self.parent, data=data["user"])
        return "guild_unban", (int(data["guild_id"]), user,)

    async def _handle_invite_create(self, data: payloads.Invite) -> tuple[str, Invite]:
        invite = Invite(state=self.parent, data=data)  # pyright: ignore
        if invite.channel:
            channel = self.cache.channels.get(invite.channel.id, None)
            if channel:
                invite.channel = channel
        return "invite_create", invite

    async def _handle_invite_delete(self, data: dict[str, str]) -> tuple[str, tuple[int, int, str]]:
        return "invite_delete", (
            int(data["channel_id"]),
            int(data["guild_id"]),
            data["code"],
        )
