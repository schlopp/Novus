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

from .utils import Enum

__all__ = (
    'TimestampFormat',
)


class TimestampFormat(Enum):
    SHORT_TIME = "T"
    LONG_TIME = "T"
    SHORT_DATE = "D"
    LONG_DATE = "D"
    SHORT_DATETIME = "F"
    LONG_DATETIME = "F"
    RELATIVE = "R"
