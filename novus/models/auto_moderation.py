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

from typing import TYPE_CHECKING, Any, Optional

from ..enums import AutoModerationActionType
from ..utils import MISSING, generate_repr, try_id, try_object, try_snowflake
from .guild import BaseGuild, Guild

if TYPE_CHECKING:
    from ..api import HTTPConnection
    from ..payloads import AutoModerationAction as ActionPayload
    from ..payloads import AutoModerationActionMetadata as ActionMetaPayload
    from ..payloads import AutoModerationRule as RulePayload
    from ..payloads import AutoModerationTriggerMetadata as TriggerMetaPayload
    from . import abc
    from .guild_member import GuildMember
    from .user import User

__all__ = (
    'AutoModerationTriggerMetadata',
    'AutoModerationAction',
    'AutoModerationRule',
)


class AutoModerationTriggerMetadata:
    """
    The metadata associated with an auto moderation trigger.

    Parameters
    ----------
    keyword_filters : list[str] | None
        A list of substrings which will be searched for in content.
        A keyword can be a phrase which contains multiple words. Wildcard
        symbols (``*``) can be used to customize how much of each keyword will
        be matched.
    regex_patterns : list[str] | None
        A list of regular expression patterns that will be matched against
        the content.
        Only rust flavored regex is supported.
    presets : list[int] | None
        A list of preset word lists that you want to match against.

        .. seealso:: `novus.AutoModerationKeywordPresetType`
    allow_list : list[str] | None
        A list of substrings which should not trigger the rule.
    mention_total_limit : int | None
        The total number of unique role and user mentions allowed per message.
    """

    def __init__(
            self,
            *,
            keyword_filters: list[str] | None = None,
            regex_patterns: list[str] | None = None,
            presets: list[int] | None = None,
            allow_list: list[str] | None = None,
            mention_total_limit: int | None = None):
        self.keyword_filters = keyword_filters or list()
        self.regex_patterns = regex_patterns or list()
        self.presets = presets or list()
        self.allow_list = allow_list or list()
        self.mention_total_limit = (
            mention_total_limit
            if mention_total_limit is not None
            else None
        )

    __repr__ = generate_repr((
        'keyword_filters',
        'regex_patterns',
        'presets',
        'allow_list',
        'mention_total_limit',
    ))

    @classmethod
    def _from_data(
            cls,
            *,
            data: TriggerMetaPayload) -> AutoModerationTriggerMetadata:
        return cls(
            keyword_filters=data.get('keyword_filter'),
            regex_patterns=data.get('regex_patterns'),
            presets=[
                i
                for i in data.get('presets', [])
            ] or None,
            allow_list=data.get('allow_list'),
            mention_total_limit=data.get('mention_total_limit'),
        )

    def _to_data(self) -> TriggerMetaPayload:
        ret: TriggerMetaPayload = {}
        if self.keyword_filters is not None:
            ret['keyword_filter'] = self.keyword_filters
        if self.regex_patterns is not None:
            ret['regex_patterns'] = self.regex_patterns
        if self.presets is not None:
            ret['presets'] = self.presets
        if self.allow_list is not None:
            ret['allow_list'] = self.allow_list
        if self.mention_total_limit is not None:
            ret['mention_total_limit'] = self.mention_total_limit
        return ret


class AutoModerationAction:
    """
    A moderation action to be taken on a rule being triggered.

    Parameters
    ----------
    type : int
        The type of action to be taken.

        .. seealso:: `novus.AutoModerationActionType`
    channel : int | novus.abc.Snowflake | None
        The channel associated with the action. Can only be set if
        the action type is `AutoModerationActionType.SEND_ALERT_MESSAGE`.
    duration : int | None
        The duration (in seconds) associated with the action. Can only be set
        if the action type is `AutoModerationActionType.TIMEOUT`.

    Attributes
    ----------
    type : int
        The type of action to be taken.

        .. seealso:: `novus.AutoModerationActionType`
    channel_id : int | None
        The channel ID associated with the action. Will only be set if
        the action type is `AutoModerationActionType.SEND_ALERT_MESSAGE`.
    duration : int | None
        The duration (in seconds) associated with the action. Will only be set
        if the action type is `AutoModerationActionType.TIMEOUT`.
    """

    __slots__ = (
        'type',
        'channel_id',
        'duration',
    )

    def __init__(
            self,
            type: int,
            *,
            channel: int | abc.Snowflake | None = None,
            duration: int | None = None):
        self.type = type
        self.channel_id = None
        if channel is not None:
            if self.type != AutoModerationActionType.SEND_ALERT_MESSAGE:
                raise ValueError("Cannot set channel for action type %s" % self.type)
            self.channel_id = channel if isinstance(channel, int) else channel.id
        self.duration = None
        if duration is not None:
            if self.type != AutoModerationActionType.TIMEOUT:
                raise ValueError("Cannot set duration for action type %s" % self.type)
            self.duration = duration

    __repr__ = generate_repr(('type', 'channel_id', 'duration',))

    @classmethod
    def _from_data(cls, *, data: ActionPayload) -> AutoModerationAction:
        return cls(
            type=data['type'],
            channel=try_snowflake(data.get('metadata', {}).get('channel_id')),
            duration=data.get('metadata', {}).get('duration_seconds'),
        )

    def _to_data(self) -> ActionPayload:
        data: ActionPayload = {}  # pyright: ignore
        data['type'] = self.type
        metadata: ActionMetaPayload = {}  # pyright: ignore
        if self.channel_id is not None:
            metadata['channel_id'] = str(self.channel_id)
        if self.duration is not None:
            metadata['duration_seconds'] = self.duration
        if metadata:
            data['metadata'] = metadata
        return data


class AutoModerationRule:
    """
    A model representing an auto moderation rule.

    Attributes
    ----------
    id : int
        The ID of the rule.
    guild_id : int
        The ID of the guild that the rule is tied to.
    name : str
        The name given to the rule.
    creator_id : int
        The ID of the user that created the rule.
    event_type : int
        The event type.

        .. seealso:: `novus.AutoModerationEventType`
    trigger_type : int
        The trigger type for the rule.

        .. seealso:: `novus.AutoModerationTriggerType`
    trigger_metadata : novus.AutoModerationTriggerMetadata
        The metadata associated with the rule.
    actions : list[novus.AutoModerationAction]
        A list of actions taken when the rule is triggered.
    enabled : bool
        Whether the rule is enabled.
    exempt_role_ids : list[int]
        A list of IDs corresponding to roles that are exempt from this rule.
    exempt_channel_ids : list[int]
        A list of IDs corresponding to channels that are exempt from this rule.
    guild : novus.abc.Snowflake
        A guild object (or a snowflake object).
    """

    __slots__ = (
        'state',
        'id',
        'name',
        'creator',
        'event_type',
        'trigger_type',
        'trigger_metadata',
        'actions',
        'enabled',
        'exempt_role_ids',
        'exempt_channel_ids',
        'guild',
    )

    id: int
    name: str
    creator: GuildMember | User
    event_type: int
    trigger_type: int
    trigger_metadata: AutoModerationTriggerMetadata
    actions: list[AutoModerationAction]
    enabled: bool
    exempt_role_ids: list[int]
    exempt_channel_ids: list[int]
    guild: BaseGuild

    def __init__(
            self,
            *,
            state: HTTPConnection,
            data: RulePayload):
        self.state = state
        self.id = try_snowflake(data['id'])
        self.name = data['name']
        self.guild = self.state.cache.get_guild(data["guild_id"])
        creator_id = try_snowflake(data['creator_id'])
        creator = None
        if isinstance(self.guild, Guild):
            creator = self.guild.get_member(creator_id)
        if creator is None:
            creator = self.state.cache.get_user(creator_id)
        self.creator = creator
        self.event_type = data['event_type']
        self.trigger_type = data['trigger_type']
        self.trigger_metadata = AutoModerationTriggerMetadata._from_data(data=data['trigger_metadata'])
        self.actions: list[AutoModerationAction] = [
            AutoModerationAction._from_data(data=d)
            for d in data['actions']
        ]
        self.enabled = data['enabled']
        self.exempt_role_ids = [
            try_snowflake(d)
            for d in data['exempt_roles']
        ]
        self.exempt_channel_ids = [
            try_snowflake(d)
            for d in data['exempt_channels']
        ]

    __repr__ = generate_repr((
        'id',
        'guild',
        'name',
        'event_type',
        'trigger_type',
        'trigger_metadata',
        'actions',
        'enabled',
    ))

    # API methods

    @classmethod
    async def fetch(
            cls,
            state: HTTPConnection,
            guild: int | abc.Snowflake,
            rule: int | abc.Snowflake) -> AutoModerationRule:
        """
        Get an instance of an auto moderation rule from the API.

        Parameters
        ----------
        state : HTTPConnection
            The API connection.
        guild : int | novus.abc.Snowflake
            An association to a guild that you want to get the rule from.
        rule : int | novus.abc.Snowflake
            An association to get the rule from.

        Returns
        -------
        novus.AutoModerationRule
            The auto moderation rule.
        """

        return await state.auto_moderation.get_auto_moderation_rule(
            try_id(guild),
            try_id(rule),
        )

    @classmethod
    async def fetch_all_for_guild(
            cls,
            state: HTTPConnection,
            guild: int | abc.Snowflake) -> list[AutoModerationRule]:
        """
        Get all of the auto moderation rules from the API for a given guild.

        Parameters
        ----------
        state : novus.HTTPConnection
            The API connection to manage the entity with.
        guild : int | novus.abc.Snowflake
            The guild that you want to get the rules from.

        Returns
        -------
        list[novus.AutoModerationRule]
            The list of auto moderation rules in the guild.
        """

        return await state.auto_moderation.list_auto_moderation_rules_for_guild(
            try_id(guild),
        )

    async def edit(
            self: abc.StateSnowflakeWithGuild,
            *,
            reason: str | None = None,
            name: str = MISSING,
            event_type: int = MISSING,
            trigger_type: int = MISSING,
            trigger_metadata: AutoModerationTriggerMetadata = MISSING,
            actions: list[AutoModerationAction] = MISSING,
            enabled: bool = MISSING,
            exempt_roles: list[int | abc.Snowflake] = MISSING,
            exempt_channels: list[int | abc.Snowflake] = MISSING) -> AutoModerationRule:
        """
        Edit an instance of the auto moderation rule.

        Parameters
        ----------
        name : str
            The new name for the role.
        event_type : int
            The event type.

            .. seealso:: `novus.AutoModerationEventType`
        trigger_type : int
            The trigger type.

            .. seealso:: `novus.AutoModerationTriggerType`
        trigger_metadata : novus.AutoModerationTriggerMetadata
            The trigger metadata.
        actions : list[novus.AutoModerationAction]
            The actions to be taken on trigger.
        enabled : bool
            Whether the rule is enabled or not.
        exempt_roles : list[int | novus.abc.Snowflake]
            A list of roles that are exempt from the rule.
        exempt_channels : list[int | novus.abc.Snowflake]
            A list of channels that are exempt from the rule.
        reason : str | None
            The reason shown in the audit log.

        Returns
        -------
        novus.AutoModerationRule
            The updated rule.
        """

        updates: dict[str, Any] = {}

        if name is not MISSING:
            updates["name"] = name
        if event_type is not MISSING:
            updates["event_type"] = event_type
        if trigger_type is not MISSING:
            updates["trigger_type"] = trigger_type
        if trigger_metadata is not MISSING:
            updates["trigger_metadata"] = trigger_metadata
        if actions is not MISSING:
            updates["actions"] = actions
        if enabled is not MISSING:
            updates["enabled"] = enabled
        if exempt_roles is not MISSING:
            updates["exempt_roles"] = [try_object(i) for i in exempt_roles]
        if exempt_channels is not MISSING:
            updates["exempt_channels"] = [try_object(i) for i in exempt_channels]

        return await self.state.auto_moderation.modify_auto_moderation_rule(
            self.guild.id,
            self.id,
            reason=reason,
            **updates,
        )

    async def delete(
            self: abc.StateSnowflakeWithGuild,
            *,
            reason: Optional[str] = None) -> None:
        """
        Delete this auto moderation rule.

        Parameters
        ----------
        reason : str | None
            The reason shown in the audit log.
        """

        await self.state.auto_moderation.delete_auto_moderation_rule(
            self.guild.id,
            self.id,
            reason=reason,
        )
        return

    @classmethod
    async def create(
            cls,
            state: HTTPConnection,
            guild: int | abc.Snowflake,
            *,
            reason: str | None = None,
            name: str,
            event_type: int,
            trigger_type: int,
            actions: list[AutoModerationAction],
            trigger_metadata: AutoModerationTriggerMetadata | None = None,
            enabled: bool = False,
            exempt_roles: list[int | abc.Snowflake] | None = None,
            exempt_channels: list[int | abc.Snowflake] | None = None) -> AutoModerationRule:
        """
        Create a new auto moderation rule.

        Parameters
        ----------
        state : novus.HTTPConnection
            The API connection to create the entity with.
        guild: int | novus.abc.Snowflake
            The ID of the guild to create the object in.
        name : str
            The new name for the role.
        event_type : int
            The event type.

            .. seealso:: `novus.AutoModerationEventType`
        trigger_type : int
            The trigger type.

            .. seealso:: `novus.AutoModerationTriggerType`
        actions : list[novus.AutoModerationAction]
            The actions to be taken on trigger.
        trigger_metadata : novus.AutoModerationTriggerMetadata | None
            The trigger metadata.
        enabled : bool
            Whether the rule is enabled or not.
        exempt_roles : list[int | novus.abc.Snowflake] | None
            A list of roles that are exempt from the rule.
        exempt_channels : list[int | novus.abc.Snowflake] | None
            A list of channels that are exempt from the rule.
        reason : str | None
            The reason shown in the audit log.

        Returns
        -------
        novus.AutoModerationRule
            The created rule.
        """

        updates: dict[str, Any] = {}
        updates["name"] = name
        updates["event_type"] = event_type
        updates["trigger_type"] = trigger_type
        updates["trigger_metadata"] = trigger_metadata
        if actions:
            updates["actions"] = actions
        updates["enabled"] = enabled
        if exempt_roles:
            updates["exempt_roles"] = [try_object(i) for i in exempt_roles]
        if exempt_channels:
            updates["exempt_channels"] = [try_object(i) for i in exempt_channels]

        return await state.auto_moderation.create_auto_moderation_rule(
            try_id(guild),
            reason=reason,
            **updates,
        )
