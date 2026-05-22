import asyncio
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
import redis.asyncio as aioredis
from django.conf import settings

logger = logging.getLogger(__name__)


class AlertConsumer(AsyncWebsocketConsumer):
    _listener_task = None
    _connection_count = 0
    _lock = asyncio.Lock()

    async def connect(self):
        await self.channel_layer.group_add("alerts", self.channel_name)
        await self.accept()

        async with self._lock:
            AlertConsumer._connection_count += 1
            if AlertConsumer._listener_task is None or AlertConsumer._listener_task.done():
                AlertConsumer._listener_task = asyncio.create_task(self._start_redis_listener())

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("alerts", self.channel_name)

        async with self._lock:
            AlertConsumer._connection_count -= 1
            if AlertConsumer._connection_count <= 0 and AlertConsumer._listener_task:
                AlertConsumer._listener_task.cancel()
                AlertConsumer._listener_task = None

    async def alert_message(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

    @classmethod
    async def _start_redis_listener(cls):
        redis_url = settings.CACHES["default"]["LOCATION"]
        client = aioredis.from_url(redis_url)
        pubsub = client.pubsub()
        await pubsub.subscribe("alerts:active")

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"].decode("utf-8"))
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        await channel_layer.group_send(
                            "alerts",
                            {
                                "type": "alert_message",
                                "payload": data,
                            }
                        )
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Redis Pub/Sub listener error")
        finally:
            await pubsub.unsubscribe("alerts:active")
            await pubsub.close()
            await client.close()
