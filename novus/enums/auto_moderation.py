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
    'AutoModerationKeywordPresetType',
    'AutoModerationTriggerType',
    'AutoModerationEventType',
    'AutoModerationActionType',
)


class AutoModerationKeywordPresetType(Enum):
    PROFANITY = 1
    SEXUAL_CONTENT = 2
    SLURS = 3


class AutoModerationTriggerType(Enum):
    KEYWORD = 1
    SPAM = 3
    KEYWORD_PRESET = 4
    MENTION_SPAM = 5


class AutoModerationEventType(Enum):
    MESSAGE_SEND = 1


class AutoModerationActionType(Enum):
    BLOCK_MESSAGE = 1
    SEND_ALERT_MESSAGE = 2
    TIMEOUT = 3
