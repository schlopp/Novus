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

from typing import TYPE_CHECKING

from typing_extensions import Self

if TYPE_CHECKING:
    from .. import payloads

__all__ = (
    'Activity',
    'Presence',
)


class Activity:
    """
    A generic activity base class for all types of activity.

    Parameters
    ----------
    name : str
        The name of the activity
    type : int
        The type of activity.

        .. seealso:: `novus.ActivityType`
    state : str | None
        The state of the activity. Used for custom status text.
    url : str | None
        The URL of a stream. Only applicable if the activity type is a stream.

    Attributes
    ----------
    name : str
        The name of the activity
    type : int
        The type of activity.

        .. seealso:: `novus.ActivityType`
    state : str | None
        The state of the activity. Used for custom status text.
    url : str | None
        The URL of a stream. Only applicable if the activity type is a stream.
    """

    __slots__ = (
        'name',
        'type',
        'url',
        'state',
        'emoji',
    )

    def __init__(
            self,
            name: str,
            type: int,
            state: str | None = None,
            url: str | None = None) -> None:
        self.name: str = name
        self.type: int = type
        self.url: str | None = url
        self.state = state
        self.emoji = None

    @classmethod
    def _from_data(cls, data: payloads.Activity) -> Self:
        v = cls(
            name=data["name"],
            type=data["type"],
            state=data.get("state"),
            url=data.get("url"),
        )
        return v

    def _to_data(self) -> payloads.gateway.GatewayActivity:
        return {
            "name": self.name,
            "type": self.type,
            "state": self.state,
            "url": self.url,
        }


class Presence:
    """
    A user's display presence.

    Parameters
    ----------
    activities : list[novus.Activity] | None
        A list of the user's activities.
    status : str
        The status of the user.

        .. seealso:: `novus.Status`

    Attributes
    ----------
    activities : list[novus.Activity]
        A list of the user's activities.
    status : str
        The status of the user.

        .. seealso:: `novus.Status`
    """

    __slots__ = (
        'activities',
        'status',
    )

    def __init__(
            self,
            activities: list[Activity] | None,
            status: str) -> None:
        self.activities = activities or []
        self.status = status

    def _to_data(self) -> payloads.gateway.GatewayPresence:
        return {
            "since": None,
            "activities": [i._to_data() for i in self.activities],
            "status": self.status,
            "afk": False,
        }
