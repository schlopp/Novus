from datetime import datetime, timedelta
from .redis import RedisConnection


async def user_has_voted(user_id: int) -> bool:
    """
    Returns whether or not the user has vote registered through the top.gg webhook, and has been
    saved in the Redis database. If the redis database is not enabled in your
    :attr:`config file<BotConfig>` then this will raise a `NotImplementedError`.

    Raises:
        `NotImplementedError`: Redis database is not enabled.
    """
    
    if not RedisConnection.enabled:
        raise NotImplementedError("Redis database is not enabled.")
    
    if not RedisConnection.enabled:
        raise NotImplementedError("Redis database is not enabled.")

    async with RedisConnection() as redis:
        last_vote_data = await redis.get(f"votes:{user_id}")

    if last_vote_data is None:
        return False
    
    last_vote_timestamp = int(last_vote_data)
    last_vote = datetime.utcfromtimestamp(last_vote_timestamp)
    
    vote_expiration_date = last_vote + timedelta(hours=12)

    return vote_expiration_date > datetime.utcnow()
