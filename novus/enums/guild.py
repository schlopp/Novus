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
    'NSFWLevel',
    'PremiumTier',
    'MFALevel',
    'ContentFilterLevel',
    'VerificationLevel',
    'NotificationLevel',
)


class NSFWLevel(Enum):
    """The NSFW level associated with a guild."""

    DEFAULT = 0
    EXPLICIT = 1
    SAFE = 2
    AGE_RESTRICTED = 3


class PremiumTier(Enum):
    """The premium tier that a guild is currently at."""

    NONE = 0
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class MFALevel(Enum):
    """The MFA level set for a guild."""

    NONE = 0
    ELEVATED = 1


class ContentFilterLevel(Enum):
    """The content filter set for a guild."""

    DISABLED = 0
    MEMBERS_WITHOUT_ROLES = 1
    ALL_MEMBERS = 2


class VerificationLevel(Enum):
    """
    The verification level set for a guild.

    Attributes
    ----------
    none
        Unrestricted.
    low
        Must have a verified email on account.
    medium
        Must be registered on Discord for longer than 5 minutes.
    high
        Must be a member of the guild for longer than 10 minutes.
    very_high
        Must have a verified phone number.
    """

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERY_HIGH = 4


class NotificationLevel(Enum):
    """The default notification level set for a guild."""

    ALL_MESSAGES = 0
    ONLY_MENTIONS = 1
