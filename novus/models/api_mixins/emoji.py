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
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias

from ...utils import MISSING, try_object

if TYPE_CHECKING:
    import io

    from ...api import HTTPConnection
    from ..abc import Snowflake, StateSnowflakeWithGuild
    from ..emoji import Emoji

    FileT: TypeAlias = str | bytes | io.IOBase

__all__ = (
    'EmojiAPIMixin',
)


class EmojiAPIMixin:

    id: int
    state: HTTPConnection

    @classmethod
    async def create(
            cls,
            state: HTTPConnection,
            guild_id: int,
            *,
            name: str,
            image: FileT,
            roles: list[int | Snowflake] | None = None,
            reason: str | None = None) -> Emoji:
        """
        Create an emoji within a guild.

        Parameters
        ----------
        state : novus.HTTPConnection
            The API connection to create the entity with.
        guild_id : int
            The ID of the guild that the emoji is to be created in.
        name : str
            The name of the emoji you want to add.
        image : str | bytes | io.IOBase
            The image that you want to add.
        roles : list[int | novus.abc.Snowflake] | None
            A list of roles that are allowed to use the emoji.
        reason : str | None
            A reason you're adding the emoji.

        Returns
        -------
        novus.Emoji
            The newly created emoji.
        """

        return await state.emoji.create_guild_emoji(
            guild_id,
            reason=reason,
            **{
                "name": name,
                "image": image,
                "roles": [try_object(i) for i in roles or ()],
            },
        )

    @classmethod
    async def fetch(
            cls,
            state: HTTPConnection,
            guild_id: int,
            emoji_id: int) -> Emoji:
        """
        Fetch a specific emoji by its ID from the API.

        .. seealso:: :func:`novus.Guild.fetch_emoji`

        Parameters
        ----------
        guild_id : int
            The ID of the guild that you want to fetch from.
        emoji_id : int
            The ID of the emoji that you want to fetch.

        Returns
        -------
        novus.Emoji
            The emoji from the API.
        """

        return await state.emoji.get_emoji(guild_id, emoji_id)

    @classmethod
    async def fetch_all_for_guild(
            cls,
            state: HTTPConnection,
            guild_id: int) -> list[Emoji]:
        """
        Fetch all of the emojis from a guild.

        .. seealso:: :func:`novus.Guild.fetch_emojis`

        Parameters
        ----------
        guild_id : int
            The ID of the guild that you want to fetch from.

        Returns
        -------
        list[novus.Emoji]
            The list of emojis that the guild has.
        """

        return await state.emoji.list_guild_emojis(guild_id)

    async def delete(
            self: StateSnowflakeWithGuild,
            *,
            reason: str | None = None) -> None:
        """
        Delete this emoji.

        Parameters
        ----------
        reason : str | None
            The reason shown in the audit log.
        """

        await self.state.emoji.delete_guild_emoji(
            self.guild.id,
            self.id,
            reason=reason,
        )
        return None

    async def edit(
            self: StateSnowflakeWithGuild,
            *,
            reason: str | None = None,
            name: str = MISSING,
            roles: list[int | Snowflake] = MISSING) -> Emoji:
        """
        Edit the current emoji.

        Parameters
        ----------
        name : str
            The new name for the emoji.
        roles : list[int | novus.abc.Snowflake]
            A list of the roles that can use the emoji.
        reason : str | None
            The reason shown in the audit log.

        Returns
        -------
        novus.Emoji
            The newly updated emoji.
        """

        update: dict[str, Any] = {}

        if name is not MISSING:
            update["name"] = name
        if roles is not MISSING:
            update["roles"] = [try_object(i) for i in roles]

        return await self.state.emoji.modify_guild_emoji(
            self.guild.id,
            self.id,
            reason=reason,
            **update,
        )