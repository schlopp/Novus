import logging
import asyncio
from datetime import datetime
from typing import TypedDict, NotRequired, Literal

from aiohttp import web
from discord.ext import vbu

from . import utils as vbu


class _WebhookPayload(TypedDict):
    bot: str
    user: str
    type: Literal["upvote", "test"]
    isWeekend: bool
    query: NotRequired[str]


class TopggWebhookCog(
    vbu.Cog[vbu.Bot],
    command_attrs={"hidden": True, "add_slash_command": False}
):
    """
    Handles the creation and handling of the top.gg webhook server.
    """

    def __init__(self, bot: vbu.Bot) -> None:
        super().__init__(bot)
        self.__host = self.bot.config["topgg_webhook"]["host"]
        self.__port = self.bot.config["topgg_webhook"]["port"]
        self.__auth = self.bot.config["topgg_webhook"]["authorization"]
        self.__redis_enabled = self.bot.config["redis"]["enabled"]
        self._vote_cache = self.bot._topgg_votes  # pyright: ignore [reportPrivateUsage]
        self._server = web.Server(self._webhook_handler, access_log=None)
        self._runner = web.ServerRunner(self._server)
        self._webhook_task = asyncio.create_task(self._start_webhook())

    def cog_unload(self) -> None:
        self.logger.info("Cleaning up webhook runner")
        self._webhook_task.cancel()
        asyncio.create_task(self._runner.cleanup())
        return super().cog_unload()

    async def _webhook_handler(self, request: web.BaseRequest) -> web.Response:
        request_repr = f"{request!r} from {request.remote}"
        
        if request.method != "POST":
            self.logger.log(
                logging.WARNING,
                f"Received request with disallowed method: {request_repr}",
            )
            raise web.HTTPMethodNotAllowed(request.method, ["POST"])

        if request.headers.get("Authorization") != self.__auth:
            self.logger.log(
                logging.WARNING, f"Received unauthorized request: {request_repr}"
            )
            raise web.HTTPForbidden()

        payload: _WebhookPayload = await request.json()

        if payload["type"] == "test":
            self.logger.log(
                logging.INFO,
                f"Received test request: {request_repr} with payload {payload!r}",
            )
            return web.Response()

        self.logger.log(logging.INFO, f"Received request: {request_repr}")
        user_id = int(payload["user"])

        if self.__redis_enabled:
            async with self.bot.redis() as redis:
                await redis.set(f"votes:{user_id}", str(int(datetime.utcnow().timestamp())))

        else:
            self._vote_cache[user_id] = datetime.utcnow()

        return web.Response()

    async def _start_webhook(self) -> None:
        self.logger.info("Starting webhook runner")
        await self._runner.setup()
        site = web.TCPSite(
            self._runner,
            self.__host,
            self.__port,
        )
        await site.start()
        await asyncio.Future()


def setup(bot: vbu.Bot):
    if bot.config.get("topgg_webhook", {}).get("enabled", False):
        bot.add_cog(TopggWebhookCog(bot))
