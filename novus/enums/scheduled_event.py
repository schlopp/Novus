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

from .utils import Enum

__all__ = (
    'EventPrivacyLevel',
    'EventStatus',
    'EventEntityType',
)


class EventPrivacyLevel(Enum):
    GUILD_ONLY = 2


class EventStatus(Enum):
    SCHEDULED = 1
    ACTIVE = 2
    COMPLETED = 3
    CANCELLED = 4


class EventEntityType(Enum):
    STAGE_INSTANCE = 1
    VOICE = 2
    EXTERNAL = 3
