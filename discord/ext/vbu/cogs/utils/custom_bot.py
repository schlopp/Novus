from __future__ import annotations

import asyncio
import collections
import glob
import logging
from typing import (
    TYPE_CHECKING,
    Union,
    List,
    Optional,
    Type,
    Iterable,
    Tuple,
)
import copy
import string
import platform
import random
import json
import sys
from datetime import datetime, timedelta

import aiohttp
import toml
import discord
from discord.iterators import HistoryIterator
from discord.ext import commands
import upgradechat

from .custom_context import Context, SlashContext
from .database import DatabaseWrapper
from .redis import RedisConnection
from .statsd import StatsdConnection
from .analytics_log_handler import AnalyticsLogHandler, AnalyticsClientSession
from .shard_manager import ShardManagerClient
from .embeddify import Embeddify
from .constants import Constants
from .. import all_packages as all_vfl_package_names

if TYPE_CHECKING:
    from .types.bot_config_file import BotConfig


sys.path.append(".")


def get_prefix(bot, message: discord.Message):
    """
    Get the guild prefix for the bot given the message that should be invoking a command.
    """

    # Set our default
    config_prefix = bot.config.get("default_prefix")
    if not config_prefix and message.author.id not in bot.owner_ids:
        return " ".join(
            random.choices(string.whitespace, k=5)
        )  # random string for a prefix if nothing is set

    # Default prefix for DMs
    if message.guild is None:
        prefix = config_prefix

    # Custom prefix or default prefix
    else:
        guild_prefix = bot.guild_settings[message.guild.id][
            bot.config.get("guild_settings_prefix_column", "prefix")
        ]
        prefix = guild_prefix or config_prefix

    # Fuck iOS devices
    if type(prefix) is not list and prefix in ["'", "‘"]:
        prefix = ["'", "‘"]

    # Listify it
    prefix = [prefix] if isinstance(prefix, str) else prefix if prefix else []
    prefix = [i for i in prefix if i]

    # Make it slightly more case insensitive
    prefix.extend([i.title() for i in prefix if i])
    prefix.extend([i.upper() for i in prefix if i])
    prefix.extend([i.lower() for i in prefix if i])
    prefix = list(set(prefix))  # Remove those duplicates

    # Add spaces for words
    possible_word_prefixes = [
        i for i in prefix if i and not any([o in i for o in string.punctuation])
    ]
    prefix.extend([f"{i.strip()} " for i in possible_word_prefixes])

    # Add the bot's managed role
    if message.guild:
        try:
            managed_role = [
                i
                for i in message.guild.roles
                if i.tags and i.tags.bot_id == bot.user.id
            ]
        except Exception:
            managed_role = None
        if managed_role:
            prefix.extend([f"<@&{managed_role[0].id}> "])

    # And we're FINALLY done
    return commands.when_mentioned_or(*prefix)(bot, message)


class MinimalBot(commands.AutoShardedBot):
    """
    A minimal version of the VoxelBotUtils bot that inherits from
    :class:`discord.ext.commands.AutoShardedBot` but gives new VBU features.
    """

    async def create_message_log(
        self,
        messages: Union[List[discord.Message], HistoryIterator],
    ) -> str:
        """
        Creates and returns an HTML log of all of the messages provided.
        This is an API method, and may raise an asyncio HTTP error.

        Args:
            messages (Union[List[discord.Message], discord.iterators.HistoryIterator]):
                The messages you want to create into a log.

        Returns:
            str: The HTML for a log file.
        """

        # Let's flatten the messages if we need to
        if isinstance(messages, HistoryIterator):
            messages = await messages.flatten()

        # Create the data we're gonna send
        data = {
            "channel_name": messages[0].channel.name,
            "category_name": messages[0].channel.category.name,
            "guild_name": messages[0].guild.name,
            "guild_icon_url": str(messages[0].guild.icon.url),
        }
        data_authors = {}
        data_messages = []

        # Get the data from the server
        for message in messages:
            for user in message.mentions + [message.author]:
                data_authors[user.id] = {
                    "username": user.name,
                    "discriminator": user.discriminator,
                    "avatar_url": str(user.avatar.url),
                    "bot": user.bot,
                    "display_name": user.display_name,
                    "color": user.colour.value,
                }
            message_data = {
                "id": message.id,
                "content": message.content,
                "author_id": message.author.id,
                "timestamp": int(message.created_at.timestamp()),
                "attachments": [str(i.url) for i in message.attachments],
            }
            embeds = []
            for i in message.embeds:
                embed_data = i.to_dict()
                if i.timestamp:
                    embed_data.update({"timestamp": i.timestamp.timestamp()})
                embeds.append(embed_data)
            message_data.update({"embeds": embeds})
            data_messages.append(message_data)

        # Send data to the API
        data.update({"users": data_authors, "messages": data_messages[::-1]})
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://voxelfox.co.uk/discord/chatlog", json=data
            ) as r:
                return await r.text()

    async def get_context(self, message, *, cls=None) -> Context:
        """
        Create a new context object using the utils' Context.

        :meta private:
        """

        return await super().get_context(message, cls=cls or Context)

    async def get_slash_context(self, interaction, *, cls=None) -> SlashContext:
        """
        Create a new context object using the utils' Context.

        :meta private:
        """

        return await super().get_slash_context(interaction, cls=cls or SlashContext)

    def get_context_message(self, channel, content, embed, *args, **kwargs):
        """
        A small base class for us to inherit from so that I don't need to change my
        send method when it's overridden.

        :meta private:
        """

        return content, embed


class Bot(MinimalBot):
    """
    A bot class that inherits from :class:`voxelbotutils.MinimalBot`,
    detailing more VoxelBotUtils functions, as well as changing some of the
    default Discord.py library behaviour.

    Attributes:
        logger (logging.Logger): A logger instance for the bot.
        config (dict): The :class:`config<BotConfig>` for the bot.
        session (aiohttp.ClientSession): A session instance that you can use
        to make web requests.
        application_id (int): The ID of this bot application.
        database (DatabaseWrapper): The database connector, as connected using the data
            from your :class:`config file<BotConfig.database>`.
        redis (RedisConnection): The redis connector, as connected using the data from your
            :class:`config file<BotConfig.redis>`.
        stats (StatsdConnection): The stats connector, as connected using the data from your
            :class:`config file<BotConfig.statsd>`. May not be authenticated, but will fail silently
            if not.
        startup_method (asyncio.Task): The task that's run when the bot is starting up.
        guild_settings (dict): A dictionary from the `guild_settings` Postgres table.
        user_settings (dict): A dictionary from the `user_settings` Postgres table.
        user_agent (str): The user agent that the bot should use for web requests as set in the
            :attr:`config file<BotConfig.user_agent>`. This isn't used automatically anywhere,
            so it just here as a provided convenience.
        upgrade_chat (upgradechat.UpgradeChat): An UpgradeChat connector instance using the oauth information
            provided in your :class:`config file<BotConfig.upgrade_chat>`.
        clean_prefix (str): The default prefix for the bot.
        owner_ids (List[int]): A list of the owners from the :attr:`config file<BotConfig.owners>`.
        embeddify (bool): Whether or not messages should be embedded by default, as set in the
            :attr:`config file<BotConfig.embed.enabled>`.
    """

    def __init__(
        self,
        config_file: str = "config/config.toml",
        logger: Optional[logging.Logger] = None,
        activity: discord.BaseActivity = discord.Game(name="Reconnecting..."),
        status: discord.Status = discord.Status.dnd,
        case_insensitive: bool = True,
        intents: Optional[discord.Intents] = None,
        allowed_mentions: discord.AllowedMentions = discord.AllowedMentions(
            everyone=False
        ),
        *args,
        **kwargs,
    ):
        """
        Args:
            config_file (str): The path to the :class:`config file<BotConfig>` for the bot.
            logger (logging.Logger): The logger object that the bot should use.
            activity (discord.Activity): The default activity of the bot.
            status (discord.Status): The default status of the bot.
            case_insensitive (bool): Whether or not commands are case insensitive.
            intents (discord.Intents): The default intents for the bot. Unless subclassed, the
                intents to use will be read from your :class:`config file<BotConfig.intents>`.
            allowed_mentions (discord.AllowedMentions): The default allowed mentions for the bot.
            *args: The default args that are sent to the :class:`discord.ext.commands.Bot` object.
            **kwargs: The default args that are sent to the :class:`discord.ext.commands.Bot` object.
        """

        # Store the config file for later
        self.config: BotConfig
        self.config_file = config_file
        self.logger = logger or logging.getLogger("bot")
        self.reload_config()

        # Let's work out our intents
        if not intents:
            if self.config.get("intents", {}):
                intents = discord.Intents(**self.config.get("intents", {}))
            else:
                intents = discord.Intents(
                    guilds=True, guild_messages=True, dm_messages=True
                )

        # Get our max messages
        cached_messages = self.config.get("cached_messages", 1_000)

        # Run original
        super().__init__(
            command_prefix=get_prefix,
            activity=activity,
            status=status,
            case_insensitive=case_insensitive,
            intents=intents,
            allowed_mentions=allowed_mentions,
            max_messages=cached_messages,
            *args,
            **kwargs,
        )

        # Set up our default guild settings
        self.DEFAULT_GUILD_SETTINGS = {
            self.config.get("guild_settings_prefix_column", "prefix"): self.config.get(
                "default_prefix"
            ),
        }
        self.DEFAULT_USER_SETTINGS = {}

        # Set support guild ID in the utils
        global SUPPORT_GUILD_ID
        SUPPORT_GUILD_ID = self.config.get("support_guild_id")

        # Aiohttp session
        self.session: aiohttp.ClientSession = AnalyticsClientSession(
            self,
            loop=self.loop,
            headers={"User-Agent": self.user_agent},
        )

        # Allow database connections like this
        self.database: Type[DatabaseWrapper] = DatabaseWrapper

        # Allow redis connections like this
        self.redis: Type[RedisConnection] = RedisConnection

        # Allow Statsd connections like this
        self.stats: Type[StatsdConnection] = StatsdConnection
        self.stats.config = self.config.get("statsd", {})

        # Set embeddify attrs
        Embeddify.bot = self

        # Gently add an UpgradeChat wrapper here - added as a property method so we can create a new instance if
        # the config is reloaded
        self._upgrade_chat = None

        # Store the startup method so I can see if it completed successfully
        self.startup_method = None
        self.shard_manager = None

        # Store whether or not we're an interactions only bot
        self.is_interactions_only = False  # Set elsewhere

        # Regardless of whether we start statsd or not, I want to add the log handler
        handler = AnalyticsLogHandler(self)
        handler.setLevel(logging.DEBUG)
        logging.getLogger("discord.http").addHandler(handler)
        logging.getLogger("discord.webhook.async_").addHandler(handler)
        logging.getLogger("discord.webhook.sync").addHandler(handler)

        # Here's the storage for cached stuff
        self.guild_settings = collections.defaultdict(
            lambda: copy.deepcopy(self.DEFAULT_GUILD_SETTINGS)
        )
        self.user_settings = collections.defaultdict(
            lambda: copy.deepcopy(self.DEFAULT_USER_SETTINGS)
        )
        self._topgg_votes: dict[int, datetime] = {}

    async def startup(self):
        """
        Clears the custom caches for the bot (:attr:`guild_settings`
        and :attr:`user_settings`), re-reads the database tables for each of
        those items, and calls the :func:`voxelbotutils.Cog.cache_setup`
        method in each of the cogs again.
        """

        try:
            await self._startup()
        except Exception as e:
            self.logger.error(e, exc_info=True)
            exit(1)

    async def _startup(self):
        """
        Runs all of the actual db stuff.
        """

        # Remove caches
        self.logger.debug("Clearing caches")
        self.guild_settings.clear()
        self.user_settings.clear()

        # Get database connection
        db = await self.database.get_connection()

        # Get default guild settings
        default_guild_settings = await db.call(
            "SELECT * FROM guild_settings WHERE guild_id=0"
        )
        if not default_guild_settings:
            await db.call("INSERT INTO guild_settings (guild_id) VALUES (0)")
            default_guild_settings = await db.call(
                "SELECT * FROM guild_settings WHERE guild_id=0"
            )
        for i, o in default_guild_settings[0].items():
            self.DEFAULT_GUILD_SETTINGS.setdefault(i, o)

        # Get guild settings
        data = await self._get_all_table_data(db, "guild_settings")
        for row in data:
            for key, value in row.items():
                self.guild_settings[row["guild_id"]][key] = value

        # Get default user settings
        default_user_settings = await db.call(
            "SELECT * FROM user_settings WHERE user_id=0",
        )
        if not default_user_settings:
            await db.call(
                "INSERT INTO user_settings (user_id) VALUES (0)",
            )
            default_user_settings = await db.call(
                "SELECT * FROM user_settings WHERE user_id=0",
            )
        for i, o in default_user_settings[0].items():
            self.DEFAULT_USER_SETTINGS.setdefault(i, o)

        # Get user settings
        data = await self._get_all_table_data(db, "user_settings")
        for row in data:
            for key, value in row.items():
                self.user_settings[row["user_id"]][key] = value

        # Run the user-added startup methods
        async def fake_cache_setup_method(db):
            pass

        for _, cog in self.cogs.items():
            await getattr(cog, "cache_setup", fake_cache_setup_method)(db)

        # Close database connection
        await db.disconnect()

    async def _run_sql_exit_on_error(
        self, db: DatabaseWrapper, sql: str, *args
    ) -> Iterable:
        """
        Get data from a table, and exit if we get an error.
        """

        try:
            return await db.call(sql, *args)
        except Exception as e:
            self.logger.critical(f"Error selecting from table - {e}")
            exit(1)

    async def _get_all_table_data(self, db, table_name) -> Iterable:
        """
        Select all from a table given its name.
        """

        v = await self._run_sql_exit_on_error(
            db,
            "SELECT * FROM {0}".format(table_name),
        )
        return v

    async def _get_list_table_data(
        self, db: DatabaseWrapper, table_name: str, key: str
    ) -> Iterable:
        """
        Select all from a table given its name and a `key=key` check.
        """

        return await self._run_sql_exit_on_error(
            db,
            "SELECT * FROM {0} WHERE key=$1".format(table_name),
            key,
        )

    async def fetch_support_guild(self) -> Optional[discord.Guild]:
        """
        Get the support guild as set in the bot's
        :attr:`config file<BotConfig.support_guild_id>`.

        Returns
        -------
        Optional[discord.Guild]
            The guild instance. Will be `None` if a guild ID has not been
            provided, or cannot be found.
        """

        try:
            assert self.config["support_guild_id"]
            return self.get_guild(
                self.config["support_guild_id"]
            ) or await self.fetch_guild(self.config["support_guild_id"])
        except Exception:
            return None

    @property
    def user_agent(self):
        """:meta private:"""

        if self.user is None:
            return self.config.get(
                "user_agent",
                (
                    f"DiscordBot (Discord.py discord bot https://github.com/"
                    f"Voxel-Fox-Ltd/Novus) Python/{platform.python_version()} "
                    f"aiohttp/{aiohttp.__version__}"
                ),
            )
        return self.config.get(
            "user_agent",
            (
                f"{self.user.name.replace(' ', '-')} (Discord.py discord "
                f"bot https://github.com/Voxel-Fox-Ltd/Novus) Python/"
                f"{platform.python_version()} aiohttp/{aiohttp.__version__}"
            ),
        )

    @property
    def cluster(self) -> int:
        """
        Gets the bot cluster based on the shard count
        and an evenly split amount of shards.
        """

        return (self.shard_ids or [0])[0] // len(self.shard_ids or [0])

    @property
    def upgrade_chat(self) -> upgradechat.UpgradeChat:
        """:meta private:"""

        if self._upgrade_chat:
            return self._upgrade_chat
        self._upgrade_chat = upgradechat.UpgradeChat(
            self.config["upgrade_chat"]["client_id"],
            self.config["upgrade_chat"]["client_secret"],
            session=self.session,
        )
        return self._upgrade_chat
    
    async def user_has_voted(self, user_id: int) -> bool:
        """
        Returns whether or not the user has vote registered through the top.gg webhook. If the
        top.gg webhook server is not enabled in your
        :attr:`config file<BotConfig.topgg_webhook.enabled>` then this will raise an `Exception`.

        Raises:
            `NotImplementedError`: Top.gg webhook server is not enabled.
        """
        
        if not self.config.get("topgg_webhook", {}).get("enabled", False):
            raise NotImplementedError

        if self.config["redis"]["enabled"]:
            async with self.redis() as redis:
                last_vote_data = await redis.get(f"votes:{user_id}")

                if last_vote_data is None:
                    return False
                
                last_vote_timestamp = int(last_vote_data)
                last_vote = datetime.utcfromtimestamp(last_vote_timestamp)
        
        else:
            try:
                last_vote = self._topgg_votes[user_id]
            except KeyError:
                return False

        vote_expiration_date = last_vote + timedelta(hours=12)

        return vote_expiration_date > datetime.utcnow()


    async def get_user_topgg_vote(self, user_id: int) -> bool:
        """
        Returns whether or not the user has voted on Top.gg. If there's no
        Top.gg token provided in your
        :attr:`config file<BotConfig.bot_listing_api_keys.topgg_token>`
        then this will always return `False`. This method doesn't handle
        timeouts or errors in their API (such as outages); you are expected
        to handle them yourself.

        Args:
            user_id (int): The ID of the user you want to check.

        Returns:
            bool: Whether or not that user has registered a vote on Top.gg.
        """

        # Make sure there's a token provided
        bot_listing_api_keys = self.config.get("bot_listing_api_keys", {})
        topgg_token = bot_listing_api_keys.get("topgg_token")
        bot_id = bot_listing_api_keys.get("override_bot_id") or self.user.id  # type: ignore
        if not topgg_token:
            return False

        # Try and see whether the user has voted
        url = f"https://top.gg/api/bots/{bot_id}/check"
        async with self.session.get(
            url, params={"userId": user_id}, headers={"Authorization": topgg_token}
        ) as r:
            try:
                data = await r.json()
            except Exception:
                return False
            if r.status != 200:
                return False

        # Return
        return bool(data.get("voted", False))

    def get_event_webhook(self, event_name: str) -> Optional[discord.Webhook]:
        """
        Get a :class:`discord.Webhook` object based on the keys in the
        :class:`bot's config<BotSettings.event_webhooks>`.

        Parameters
        ----------
        event_name : str
            The name of the event you want to get a webhook for.

        Returns
        -------
        Optional[discord.Webhook]
            A webhook instance pointing to the URL as given.
        """

        # First we're gonna use the legacy way of event webhooking, which is
        # to say: it's just in the config
        url = self.config.get("event_webhook_url")
        if url:
            try:
                self.logger.debug("Grabbed event webhook from config")
                w = discord.Webhook.from_url(url, session=self.session)
                w._state = self._connection
                return w
            except discord.InvalidArgument:
                self.logger.error(
                    ("The webhook set in your config is not a valid " "Discord webhook")
                )
                return None
        if url is not None:
            return None

        # Now we're gonna do with the new handler
        webhook_picker = self.config.get("event_webhook")
        if webhook_picker is None:
            return None

        # See if the event is enabled
        new_url = webhook_picker.get("events", dict()).get(event_name)
        if new_url in ["", None, False]:
            return None
        if isinstance(new_url, str):
            url = new_url
        else:
            url = webhook_picker.get("event_webhook_url", "")
        try:
            self.logger.debug(
                f"Grabbed event webhook for event {event_name} from config"
            )
            w = discord.Webhook.from_url(url, session=self.session)
            w._state = self._connection
            return w
        except discord.InvalidArgument:
            self.logger.error(
                f"The webhook set in your config for the event {event_name} "
                "is not a valid Discord webhook"
            )
            return None

    async def add_delete_reaction(
        self,
        message: discord.Message,
        valid_users: Tuple[discord.Snowflake] | None = None,
        *,
        delete: Tuple[discord.Message] | None = None,
        timeout: float = 60.0,
        wait: bool = False,
    ) -> None:
        """
        Adds a delete reaction to the given message.

        Parameters
        ----------
        message : discord.Message
            The message you want to add a delete reaction to.
        valid_users : Tuple[discord.Snowflake] | None, optional
            The users who have permission to use the message's delete reaction.
        delete : Tuple[discord.Message] | None, optional
            The messages that should be deleted on clicking the delete reaction.
        timeout : float, optional
            How long the delete reaction should persist for.
        wait : bool, optional
            Whether or not to block (via async) until the delete reaction
            is pressed.

        Raises
        ------
        e
            Description
        """

        # See if we want to make this as a task or not
        if wait is False:
            self.loop.create_task(
                self.add_delete_reaction(
                    message=message,
                    valid_users=valid_users,
                    delete=delete,
                    timeout=timeout,
                    wait=True,
                )
            )
            return None

        # See if we were given a list of authors
        # This is an explicit check for None rather than just a falsy value;
        # this way users can still provide an empty list for only
        # manage_messages users to be able to delete the message.
        if valid_users is None:
            valid_users = (message.author,)

        # Let's not add delete buttons to DMs
        if isinstance(message.channel, discord.DMChannel):
            return

        # Add reaction
        try:
            await message.add_reaction("\N{WASTEBASKET}")
        except discord.HTTPException as e:
            raise e  # Maybe return none here - I'm not sure yet.

        # Fix up arguments
        if not isinstance(valid_users, (list, tuple, set)):
            valid_users = (valid_users,)

        # Wait for response
        def check(r, u) -> bool:
            if r.message.id != message.id:
                return False
            if u.bot is True:
                return False
            if isinstance(u, discord.Member) is False:
                return False
            if getattr(u, "roles", None) is None:
                return False
            if str(r.emoji) != "\N{WASTEBASKET}":
                return False
            if (
                u.id in [user.id for user in valid_users]
                or u.permissions_in(message.channel).manage_messages
            ):
                return True
            return False

        try:
            await self.wait_for("reaction_add", check=check, timeout=timeout)
        except asyncio.TimeoutError:
            try:
                return await message.remove_reaction("\N{WASTEBASKET}", self.user)
            except Exception:
                return

        # We got a response
        if delete is None:
            delete = (message,)

        # Try and bulk delete
        bulk = False
        if message.guild:
            permissions: discord.Permissions
            permissions = message.channel.permissions_for(message.guild.me)
            bulk = permissions.manage_messages and permissions.read_message_history
        try:
            await message.channel.purge(
                check=lambda m: m.id in [i.id for i in delete],
                bulk=bulk,
            )
        except Exception:
            return  # Ah well

    def set_footer_from_config(self, embed: discord.Embed) -> None:
        """
        Sets a footer on the given embed based on the items in the
        :attr:`bot's config<BotConfig.embed.footer>`.

        Args:
            embed (discord.Embed): The embed that you want to set a footer on.
        """

        pool = []
        for data in self.config.get("embed", dict()).get("footer", list()):
            safe_data = data.copy()
            amount = safe_data.pop("amount")
            if amount <= 0:
                continue
            text = safe_data.pop("text")
            text = text.format(ctx=self)
            safe_data["text"] = text
            for _ in range(amount):
                pool.append(safe_data.copy())
        if not pool:
            return
        try:
            avatar_url = self.user.avatar.url
        except AttributeError:
            avatar_url = embed.Empty
        embed.set_footer(**random.choice(pool), icon_url=avatar_url)

    @property
    def clean_prefix(self):
        v = self.config.get("default_prefix", "/")
        if isinstance(v, str):
            return v
        return v[0]

    @property
    def owner_ids(self) -> list:
        return self.config["owners"]

    @owner_ids.setter
    def owner_ids(self, _):
        pass

    @property
    def embeddify(self) -> bool:
        try:
            return self.config["embed"]["enabled"]
        except Exception:
            return False

    def get_extensions(self) -> List[str]:
        """
        Gets a list of filenames of all the loadable cogs.

        Returns:
            List[str]: A list of the extensions found in the cogs/ folder,
                as well as the cogs included with VoxelBotUtils.
        """

        ext = glob.glob("cogs/[!_]*.py")
        extensions = []
        extensions.extend([f"discord.ext.vbu.cogs.{i}" for i in all_vfl_package_names])
        extensions.extend([i.replace("\\", ".").replace("/", ".")[:-3] for i in ext])
        self.logger.debug("Getting all extensions: " + str(extensions))
        return extensions

    def load_all_extensions(self) -> None:
        """
        Loads all the given extensions from :func:`voxelbotutils.Bot.get_extensions`.
        """

        # Unload all the given extensions
        self.logger.info("Unloading extensions... ")
        for i in self.get_extensions():
            try:
                self.unload_extension(i)
            except Exception as e:
                self.logger.debug(f" * {i}... failed - {e!s}")
            else:
                self.logger.info(f" * {i}... success")

        # Now load em up again
        self.logger.info("Loading extensions... ")
        for i in self.get_extensions():
            try:
                self.load_extension(i)
            except Exception as e:
                self.logger.critical(f" * {i}... failed - {e!s}")
                raise e
            else:
                self.logger.info(f" * {i}... success")

    async def set_default_presence(self, shard_id: Optional[int] = None) -> None:
        """
        Sets the default presence for the bot as appears in the
        :class:`config file<BotConfig.presence>`.
        """

        # Update presence
        self.logger.info("Setting default bot presence")
        presence = self.config.get("presence", {})  # Get presence object
        activity_type_str = presence.get(
            "activity_type", "online"
        ).lower()  # Get the activity type (str)
        status = getattr(
            discord.Status,
            presence.get("status", "online").lower(),
            discord.Status.online,
        )  # Get the activity type
        include_shard_id = presence.get(
            "include_shard_id", False
        )  # Whether or not to include shard IDs
        activity_type = getattr(
            discord.ActivityType, activity_type_str, discord.ActivityType.playing
        )  # The activity type to use

        # Update per shard
        for i in self.shard_ids or [0]:

            # Update the config text
            config_text = presence.get("text", "").format(bot=self).strip()
            if self.shard_count and self.shard_count > 1 and include_shard_id:
                config_text = f"{config_text} (shard {i})".strip()
                if config_text == f"(shard {i})":
                    config_text = f"Shard {i}"

            # Make an activity object
            if config_text:
                activity = discord.Activity(
                    name=config_text,
                    type=activity_type,
                )
            else:
                activity = None

            # Update the presence
            await self.change_presence(
                activity=activity,
                status=status,
                shard_id=i,
            )

    def reload_config(self) -> None:
        """
        Re-reads the config file into cache.
        """

        self.logger.info("Reloading config")
        try:
            with open(self.config_file) as a:
                self.config = toml.load(a)  # pyright: ignore
            self._event_webhook = None
        except Exception as e:
            self.logger.critical(f"Couldn't read config file - {e}")
            exit(1)

        # Reset cache items that might need updating
        self._upgrade_chat = None
        Constants.SUPPORT_GUILD_ID = self.config.get("support_guild_id")

    async def log_command(
        self,
        context: commands.Context
        | commands.SlashContext
        | discord.Interaction
        | commands.Command,
        *,
        guild: Optional[discord.Guild] = None,
        **kwargs,
    ):
        """
        Log a command into statsd.
        """

        # Get a valid name
        command_name: str | None = None
        if isinstance(context, commands.Command):
            command_name = context.qualified_name
        elif isinstance(context, commands.Context):
            if isinstance(context, commands.SlashContext):
                command_name = context.interaction.command_name
            elif context.command:
                command_name = context.command.qualified_name
        elif isinstance(context, discord.Interaction):
            command_name = context.command_name
        if command_name is None and "command_name" not in kwargs:
            return

        # Get a valid guild object
        valid_guild_id: int | None = None
        if guild:
            valid_guild_id = guild.id
        elif isinstance(context, commands.Context):
            valid_guild_id = context.guild.id if context.guild else None
        elif isinstance(context, discord.Interaction):
            valid_guild_id = context.guild_id

        # Get valid channel
        valid_channel_id: int | None = None
        if isinstance(context, (commands.Context, discord.Interaction)):
            valid_channel_id = context.channel.id if context.channel else None

        # Get valid user
        valid_user_id: int | None = None
        if isinstance(context, commands.Context):
            valid_user_id = context.author.id
        elif isinstance(context, discord.Interaction):
            valid_user_id = context.user.id

        # Work out what we wanna tell statsd
        command_stats_tags = {
            "command_name": command_name,
            "guild_id": valid_guild_id,
            "channel_id": valid_channel_id,
            "user_id": valid_user_id,
            "shard_id": ((valid_guild_id or 0) >> 22) % (self.shard_count or 1),
            "cluster": self.cluster,
        }

        # See if we can add the locale
        interaction: discord.Interaction | None = None
        if isinstance(context, discord.Interaction):
            interaction = context
        elif isinstance(context, commands.SlashContext):
            interaction = context.interaction
        if interaction:
            command_stats_tags.update(
                {
                    "user_locale": interaction.user_locale,
                    "user_language": interaction.user_locale.split("-")[0],
                    "guild_locale": interaction.guild_locale,
                }
            )
            if interaction.guild_locale:
                command_stats_tags.update(
                    {
                        "guild_language": interaction.guild_locale.split("-")[0],
                    }
                )

        # See if we can add the command type
        command_type: str = "unknown"
        if interaction:
            if interaction.data and interaction.data.get("type"):
                command_type = {
                    discord.ApplicationCommandType.chat_input: "slash",
                    discord.ApplicationCommandType.user: "user_context",
                    discord.ApplicationCommandType.message: "message_context",
                }[discord.ApplicationCommandType(interaction.data["type"])]
            else:
                command_type = "component"
        elif isinstance(context, commands.Context):
            command_type = "text"
        command_stats_tags["command_type"] = command_type

        # Add whatever custom args we have
        command_stats_tags.update(kwargs)

        # Actually send the update
        async with self.stats() as stats:
            stats.increment(
                "discord.bot.commands",
                tags=command_stats_tags,
            )

    async def login(
        self,
        token: Optional[str] = None,
        *args,
        **kwargs,
    ):
        """:meta private:"""

        try:
            await super().login(token or self.config["token"], *args, **kwargs)
        except discord.HTTPException as e:
            if str(e).startswith("429 Too Many Requests"):
                headers = {
                    i: o
                    for i, o in dict(e.response.headers).items()
                    if "rate" in i.lower()
                }
                self.logger.critical(
                    f"Cloudflare rate limit reached - {json.dumps(headers)}"
                )
            raise

    async def start(
        self,
        token: Optional[str] = None,
        *args,
        run_startup_method: bool = True,
        **kwargs,
    ):
        """:meta private:"""

        # Say we're starting
        self.logger.info(f"Starting bot with {self.shard_count} shards.")

        # See if we should run the startup method
        if run_startup_method:
            if self.config.get("database", {}).get("enabled", False):
                self.logger.info("Running startup method")
                self.startup_method = self.loop.create_task(self.startup())
            else:
                self.logger.info(
                    "Not running bot startup method due to database being disabled."
                )
        else:
            self.logger.info("Not running bot startup method.")

        # And run the original
        self.logger.info("Running original D.py start method.")
        await super().start(token or self.config["token"], *args, **kwargs)

    async def close(self, *args, **kwargs):
        """:meta private:"""

        self.logger.debug("Closing aiohttp ClientSession")
        await asyncio.wait_for(self.session.close(), timeout=None)
        self.logger.debug("Running original D.py logout method")
        await super().close(*args, **kwargs)

    async def on_ready(self):
        self.logger.info(f"Bot connected - {self.user} // {self.user.id}")
        self.logger.info("Setting activity to default")
        await self.set_default_presence()
        self.logger.info("Bot loaded.")

    async def launch_shard(self, gateway, shard_id: int, *, initial: bool = False):
        """
        Ask the shard manager if we're allowed to launch.

        :meta private:
        """

        # See if the shard manager is enabled
        shard_manager_config = self.config.get("shard_manager", {})
        shard_manager_enabled = shard_manager_config.get("enabled", False)

        # It isn't so Dpy can just do its thang
        if not shard_manager_enabled:
            return await super().launch_shard(gateway, shard_id, initial=initial)

        # Get the host and port to connect to
        host = shard_manager_config.get("host", "127.0.0.1")
        port = shard_manager_config.get("port", 8888)

        # Connect using our shard manager
        try:
            shard_manager = await ShardManagerClient.open_connection(host, port)
        except ConnectionRefusedError:
            self.logger.info("Failed to connect to shard manager - waiting 10 seconds.")
            return await self.launch_shard(gateway, shard_id, initial=initial)
        await shard_manager.ask_to_connect(shard_id)
        await super().launch_shard(gateway, shard_id, initial=initial)
        await shard_manager.done_connecting(shard_id)

    async def launch_shards(self):
        """
        Launch all of the shards using the shard manager.

        :meta private:
        """

        # If we don't have redis, let's just ignore the shard manager
        shard_manager_enabled = self.config.get("shard_manager", {}).get(
            "enabled", False
        )
        if not shard_manager_enabled:
            return await super().launch_shards()

        # Get the gateway
        if self.shard_count is None:
            self.shard_count, gateway = await self.http.get_bot_gateway()
        else:
            gateway = await self.http.get_gateway()

        # Set the shard count
        self._connection.shard_count = self.shard_count

        # Set the shard IDs
        shard_ids = self.shard_ids or range(self.shard_count)
        self._connection.shard_ids = shard_ids

        # Connect each shard
        shard_launch_tasks = []
        for shard_id in shard_ids:
            initial = shard_id == shard_ids[0]
            shard_launch_tasks.append(
                self.loop.create_task(
                    self.launch_shard(gateway, shard_id, initial=initial)
                )
            )

        # Wait for them all to connect
        await asyncio.wait(shard_launch_tasks)

        # Set the shards launched flag to true
        self._connection.shards_launched.set()

    async def connect(self, *, reconnect=True):
        """
        A version of connect that uses the shard manager.

        :meta private:
        """

        self._reconnect = reconnect
        await self.launch_shards()

        shard_manager_config = self.config.get("shard_manager", {})
        shard_manager_enabled = shard_manager_config.get("enabled", True)
        host = shard_manager_config.get("host", "127.0.0.1")
        port = shard_manager_config.get("port", 8888)
        queue = self._AutoShardedClient__queue  # I'm sorry Danny

        # Make a shard manager instance if we need to
        async def get_shard_manager() -> Optional[ShardManagerClient]:
            if not shard_manager_enabled:
                return
            return await ShardManagerClient.open_connection(host, port)

        while not self.is_closed():
            item = await queue.get()
            if item.type == discord.shard.EventType.close:
                await self.close()
                if isinstance(item.error, discord.errors.ConnectionClosed):
                    if item.error.code != 1000:
                        raise item.error
                    if item.error.code == 4014:
                        raise discord.errors.PrivilegedIntentsRequired(
                            item.shard.id
                        ) from None
                return
            elif item.type == discord.shard.EventType.identify:
                shard_manager = await get_shard_manager()
                if shard_manager and shard_manager_enabled:
                    await shard_manager.ask_to_connect(
                        item.shard.id, priority=True
                    )  # Let's assign reidentifies a higher priority
                await item.shard.reidentify(item.error)
                if shard_manager and shard_manager_enabled:
                    await shard_manager.done_connecting(item.shard.id)
            elif item.type == discord.shard.EventType.resume:
                await item.shard.reidentify(item.error)
            elif item.type == discord.shard.EventType.reconnect:
                await item.shard.reconnect()
            elif item.type == discord.shard.EventType.terminate:
                await self.close()
                raise item.error
            elif item.type == discord.shard.EventType.clean_close:
                return
