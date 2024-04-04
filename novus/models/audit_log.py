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

from typing import TYPE_CHECKING, Any, Generator

from ..utils import cached_slot_property, generate_repr, try_snowflake
from .auto_moderation import AutoModerationRule
from .channel import Channel
from .scheduled_event import ScheduledEvent
from .user import User
from .webhook import Webhook

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ..api import HTTPConnection
    from ..payloads import AuditLog as AuditLogPayload
    from ..payloads import AuditLogEntry as AuditLogEntryPayload
    from .abc import Snowflake

__all__ = (
    'AuditLogContainer',
    'AuditLogEntry',
    'AuditLog',
)


class AuditLogContainer:
    """
    A proxy object for audit log changes, and extra information given back from
    Discord. This can hold a wide variety of information (attributes of changed
    entities; additional parameters for a user action; etc), so can be iterated
    over like a `dict` for easy access.
    """

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __len__(self) -> int:
        return len(self.__dict__)

    def __iter__(self) -> Generator[tuple[str, Any], None, None]:
        yield from self.__dict__.items()

    def __repr__(self) -> str:
        values = ' '.join('%s=%r' % item for item in self.__dict__.items())
        if values:
            return f'<{self.__class__.__name__} {values}>'
        return f'<{self.__class__.__name__}>'

    if TYPE_CHECKING:

        def __getattr__(self, item: str) -> Any:
            ...

        def __setattr__(self, key: str, value: Any) -> Any:
            ...


class AuditLogEntry:
    """
    An individual entry in the audit log.

    Attributes
    ----------
    id : int
        The ID of the entry.
    reason : str | None
        The reason added to the entry, if one was given.
    target_id : int | None
        The ID of the affected entity.
    target : novus.abc.Snowflake | None
        The affected entity.
    user_id : int | None
        The ID of the user or app that made the changes.
    user : novus.User | None
        The user or app that made the changes.
    action_type : novus.AuditLogEvent
        The action that was applied.
    options : novus.AuditLogContainer
        Additional information for the entry.
    before : novus.AuditLogContainer | None
        The state of the object before the action happened. Could be ``None``
        in the case of new objects being created.
    after : novus.AuditLogContainer | None
        The state of the object after the action happened. Could be ``None``
        in the case of an object being removed.
    """

    __slots__ = (
        'log',
        'id',
        'reason',
        'target_id',
        'user_id',
        'action_type',
        'options',
        'before',
        'after',

        '_cs_user',
        '_cs_target',
    )

    def __init__(self, *, data: AuditLogEntryPayload, log: AuditLog | None):
        self.log = log
        self.id = try_snowflake(data['id'])
        self.reason = data.get('reason', None)
        self.target_id = try_snowflake(data.get('target_id'))
        self.user_id = try_snowflake(data.get('user_id'))
        self.action_type = int(data['action_type'])

        self.options: AuditLogContainer | None = None
        if 'options' in data:
            self.options = AuditLogContainer()
            for k, v in data['options'].items():
                if k.endswith("_id") or k == "id":
                    v = int(v)  # pyright: ignore
                setattr(self.options, k, v)

        self.before: AuditLogContainer | None = AuditLogContainer()
        self.after: AuditLogContainer | None = AuditLogContainer()

        # Log all changes uwu
        changes = data.get('changes', list())
        for change in changes:

            # Special case for role add/remove
            if change['key'].startswith("$"):
                if change['key'] == "$add":
                    self.before = None
                    change_obj = self.after
                elif change['key'] == "$remove":
                    self.after = None
                    change_obj = self.before
                else:
                    raise ValueError("Invalid change key")
                nv = change['new_value']  # pyright: ignore
                for k, v in nv[0].items():
                    if k == "id":
                        v = int(v)  # pyright: ignore
                    setattr(change_obj, k, v)
                continue

            # Everything else case for everything else
            key = change['key']
            setattr(self.before, key, change.get('old_value'))
            setattr(self.after, key, change.get('new_value'))

        # If we're all null
        if self.before is not None:
            for _, v in self.before:
                if v is not None:
                    break
            else:
                self.before = None
        if self.after is not None:
            for _, v in self.after:
                if v is not None:
                    break
            else:
                self.after = None

    __repr__ = generate_repr(('id', 'action_type', 'reason',))

    @cached_slot_property('_cs_user')
    def user(self) -> User | None:
        if self.log is None:
            return None
        if self.user_id is None:
            return None
        return self.log._get_user(self.user_id)

    @cached_slot_property('_cs_target')
    def target(self) -> Snowflake | None:
        if self.log is None:
            return None
        if self.target_id is None:
            return None

        a = self.action_type  # Just to make the line shorter
        if 1 <= a < 10:
            return None
        elif 10 <= a < 20:
            return None
        elif 20 <= a < 30:
            return self.log._get_user(self.target_id)
        elif 30 <= a < 40:
            return None
        elif 40 <= a < 50:
            return None
        elif 50 <= a < 60:
            return self.log._get_webhook(self.target_id)
        elif 60 <= a < 70:
            return None  # TODO emojis
        elif 70 <= a < 80:
            return None  # TODO messages
        elif 80 <= a < 83:
            return self.log._get_integration(self.target_id)
        elif 83 <= a < 90:
            return None  # TODO stage instance
        elif 90 <= a < 100:
            return None  # TODO stickers
        elif 100 <= a < 110:
            return self.log._get_guild_scheduled_event(self.target_id)
        elif 110 <= a < 120:
            return self.log._get_thread(self.target_id)
        elif 120 <= a < 130:
            return None  # TODO application command permissions
        elif 130 <= a < 140:
            return None  # seemingly reserved
        elif 140 <= a < 150:
            return self.log._get_auto_moderation_rule(self.target_id)
        return None


class AuditLog:
    """
    A model containing the audit logs for a guild.

    Attributes
    ----------
    entries : list[novus.AuditLogEntry]
        The entries contained in the audit log.
    """

    __slots__ = (
        'guild',
        'entries',
        'state',
        '_targets',
        '_application_commands',
        '_auto_moderation_rules',
        '_guild_scheduled_events',
        '_integrations',
        '_threads',
        '_users',
        '_webhooks',
    )

    def __init__(self, *, data: AuditLogPayload, state: HTTPConnection, guild: Snowflake):
        self.guild = guild
        self.state = state
        self._targets: dict[str, dict[int, Any]] = {
            'application_commands': {int(i['id']): i for i in data['application_commands']},
            'auto_moderation_rules': {int(i['id']): i for i in data['auto_moderation_rules']},
            'guild_scheduled_events': {int(i['id']): i for i in data['guild_scheduled_events']},
            'integrations': {int(i['id']): i for i in data['integrations']},
            'threads': {int(i['id']): i for i in data['threads']},
            'users': {int(i['id']): i for i in data['users']},
            'webhooks': {int(i['id']): i for i in data['webhooks']},
        }
        self.entries = [
            AuditLogEntry(data=d, log=self)
            for d in data['audit_log_entries']
        ]

        self._application_commands: dict[int, Any | None] = {}
        self._auto_moderation_rules: dict[int, AutoModerationRule | None] = {}
        self._guild_scheduled_events: dict[int, ScheduledEvent | None] = {}
        self._integrations: dict[int, Any | None] = {}
        self._threads: dict[int, Channel | None] = {}
        self._users: dict[int, User | None] = {}
        self._webhooks: dict[int, Webhook | None] = {}

    __repr__ = generate_repr(('guild',))

    def __iter__(self) -> Iterator[AuditLogEntry]:
        return iter(self.entries)

    def _get_application_command(self, id: int) -> Any | None:
        if id in self._application_commands:
            return self._application_commands[id]
        raise NotImplementedError()

    def _get_auto_moderation_rule(self, id: int) -> AutoModerationRule | None:
        if id in self._auto_moderation_rules:
            return self._auto_moderation_rules[id]
        raise NotImplementedError()

    def _get_guild_scheduled_event(self, id: int) -> ScheduledEvent | None:
        if id in self._guild_scheduled_events:
            return self._guild_scheduled_events[id]
        raise NotImplementedError()

    def _get_integration(self, id: int) -> Any | None:
        if id in self._integrations:
            return self._integrations[id]
        raise NotImplementedError()

    def _get_thread(self, id: int) -> Channel | None:
        if id in self._threads:
            return self._threads[id]
        if id in self._targets['threads']:
            self._threads[id] = None
            return None
        self._threads[id] = u = Channel(
            data=self._targets['threads'][id],
            state=self.state,
        )
        return u

    def _get_user(self, id: int) -> User | None:
        if id in self._users:
            return self._users[id]
        if id in self._targets['users']:
            self._users[id] = None
            return None
        self._users[id] = u = User(
            data=self._targets['users'][id],
            state=self.state,
        )
        return u

    def _get_webhook(self, id: int) -> Webhook | None:
        if id in self._webhooks:
            return self._webhooks[id]
        raise NotImplementedError()

    # API methods

    @classmethod
    async def fetch(
            cls,
            state: HTTPConnection,
            guild_id: int,
            *,
            user_id: int | None = None,
            action_type: int | None = None,
            before: int | None = None,
            after: int | None = None,
            limit: int = 50) -> AuditLog:
        """
        Get an instance of a user from the API.

        Parameters
        ----------
        state : HTTPConnection
            The API connection.
        guild_id : int
            The ID associated with the user you want to get.
        user_id: Optional[int]
            The ID of the moderator you want to to filter by.
        action_type: Optional[int]
            The type of action that you want to filter by.

            .. seealso:: `novus.AuditLogEventType`
        before: Optional[int]
            The snowflake before which to get entries.
        after: Optional[int]
            The snowflake after which to get entries.
        limit: Optional[int]
            The number of entries to get. Max 100, defaults to 50.

        Returns
        -------
        novus.AuditLog
            The audit log for the guild.
        """

        return await state.audit_log.get_guild_audit_log(
            guild_id,
            user_id=user_id,
            action_type=action_type,
            before=before,
            after=after,
            limit=limit,
        )
