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

from typing import TYPE_CHECKING

from ..utils import generate_repr

if TYPE_CHECKING:
    from ..api import HTTPConnection

__all__ = (
    'Object',
)


class Object:
    """
    An abstract class that you can pass around to other classes requiring
    IDs and a state.
    """

    def __init__(
            self,
            id: int,
            *,
            state: HTTPConnection,
            guild_id: int | None = None):
        self.id = id
        self._state = state
        self.guild = None
        if guild_id:
            self.guild = Object(guild_id, state=state)
        else:
            del self.guild

    __repr__ = generate_repr(('id', 'guild',))
