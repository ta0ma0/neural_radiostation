import asyncio
import json
from pathlib import Path

from channels.generic.websocket import AsyncWebsocketConsumer

HISTORY_PATH = Path(__file__).resolve().parent.parent / "radio_history.log"
HISTORY_LINES = 50


class TerminalConsumer(AsyncWebsocketConsumer):
    connected_clients = 0

    async def connect(self):
        await self.accept()

        TerminalConsumer.connected_clients += 1
        await self.broadcast_listeners_count()

        await self.channel_layer.group_add("logs", self.channel_name)
        await self.send_history()

    async def send_history(self):
        lines = await asyncio.get_event_loop().run_in_executor(None, self._read_history)
        for line in lines:
            await self.send(text_data=json.dumps({"message": line}))

    def _read_history(self):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            return lines[-HISTORY_LINES:]
        except OSError:
            return []

    async def disconnect(self, close_code):
        TerminalConsumer.connected_clients -= 1
        await self.broadcast_listeners_count()

        await self.channel_layer.group_discard("logs", self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        payload = text_data or (bytes_data.decode("utf-8") if bytes_data else "")
        try:
            data = json.loads(payload)
            if data.get("type") == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
        except json.JSONDecodeError:
            pass

    async def log_message(self, event):
        await self.send(text_data=json.dumps({"message": event["message"]}))

    async def broadcast_listeners_count(self):
        await self.send(
            text_data=json.dumps({"listeners": TerminalConsumer.connected_clients})
        )
