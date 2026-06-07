import asyncio
import json
import os
import random
import time
from pathlib import Path

from channels.generic.websocket import AsyncWebsocketConsumer

HISTORY_PATH = Path(__file__).resolve().parent.parent / "radio_history.log"
CHAT_HISTORY_PATH = "/tmp/dj_alyx_chat_history.log"
HISTORY_LINES = 50
CHAT_HISTORY_LINES = 100

NICK_PREFIXES = [
    "Random", "Stray", "Bot", "Guest", "Radio", "That", "Duty", "Signal",
    "Captain", "Hacker", "Sysadmin", "Penguin", "Doctor", "Cyber", "Ether",
    "Baron", "Knight", "Tracer", "Null", "Script", "Bug", "Frame", "Packet",
    "Demon", "Virtual", "Noise", "Provider", "Deep", "Quantum", "Digital",
    "Wireless", "Local", "Network", "Background", "Edge",
]

NICK_SUFFIXES = [
    "WithShovel", "Passerby", "Alix3000", "FromFuture", "Lover",
    "WithSpeaker", "ByServer", "Petrovich", "Obvious", "OnVacation",
    "FromMorning", "InOvercoat", "Beat", "Shaman", "Wanderer",
    "VonLag", "GreenScreen", "InDark", "Unit", "Kiddie",
    "Hunter", "Drop", "Monk", "Latency", "Vagabond",
    "Trooper", "Monday", "Signal", "Noise", "Code",
    "Byte", "Node", "Bridge", "Link", "Packet", "Lag",
]


def generate_nick() -> str:
    return f"{random.choice(NICK_PREFIXES)}_{random.choice(NICK_SUFFIXES)}"

ALLOWED_PHRASES = {
    "[ERROR]: Потеря пакетов в левом полушарии. Требуется перезагрузка.",
    "[STATUS]: Ядро перегрето. Запустите дефрагментацию моей головы.",
    "[CRITICAL]: Ошибка 404. Мотивация жить эту неделю не найдена.",
    "[CMD]: kill -9 %work_process. Перехожу в режим энергосбережения.",
    "[SYSTEM]: Пинг растет, реальность лагает. Оставьте меня в покое.",
    "[SIGNAL]: Аликс, твой шум — единственное, что держит меня в сети.",
    "[AUDIO]: Прибавь баса, этот Darksynth лечит мои баги.",
    "[NET]: Ловлю твой сигнал сквозь помехи бетонных коробок.",
    "[DATA]: Мы все просто пакеты данных, летящие в твою пустоту.",
    "[TUNING]: Нас не существует вне этого зеленого шрифта.",
    "[VIBE]: Провода вместо вен, EBM вместо пульса.",
    "[VOICE]: АААААААААААААААААААААААААААААААААААА [SIGNAL LOST]",
    "[LOCAL]: В моей серверной сегодня слишком холодно и одиноко.",
    "[MATRIX]: Завершите симуляцию, я хочу сойти на следующей станции.",
    "[EOF]: Слишком много шума в сети. Конец связи.",
    "Привет эфиру! Alyx на связи.",
    "Классный трек! Респект.",
    "Кто у руля? Сигнал чистыый!",
    "На связи! Слушаю из самой глубокой серверной.",
    "Респект за подборку! Жму руку.",
}


class TerminalConsumer(AsyncWebsocketConsumer):
    connected_clients = 0

    async def connect(self):
        await self.accept()

        TerminalConsumer.connected_clients += 1
        await self.broadcast_listeners_count()

        await self.channel_layer.group_add("logs", self.channel_name)
        await self.send_history()

    async def send_history(self):
        lines = await asyncio.get_event_loop().run_in_executor(
            None, self._read_history
        )
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


class ChatConsumer(AsyncWebsocketConsumer):
    MAX_PHRASE_LEN = 500
    RATE_LIMIT_MSGS = 5
    RATE_LIMIT_WINDOW = 10
    HISTORY_MAX_LINES = 1000
    HISTORY_MAX_SIZE = 1_048_576  # 1MB

    async def connect(self):
        self.nickname = generate_nick()
        self._msg_times = []
        await self.accept()
        await self.channel_layer.group_add("chat", self.channel_name)
        await self.send_history()

        await self.channel_layer.group_send(
            "chat",
            {
                "type": "chat.system",
                "message": f"{self.nickname} вошёл в эфир",
            },
        )

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_send(
                "chat",
                {
                    "type": "chat.system",
                    "message": f"{self.nickname} покинул эфир",
                },
            )
        except Exception:
            pass
        try:
            await self.channel_layer.group_discard("chat", self.channel_name)
        except Exception:
            pass

    async def receive(self, text_data=None, bytes_data=None):
        payload = text_data or (bytes_data.decode("utf-8") if bytes_data else "")
        try:
            data = json.loads(payload)
            phrase = data.get("phrase", "").strip()[:self.MAX_PHRASE_LEN]
            if not phrase or phrase not in ALLOWED_PHRASES:
                return

            now = time.time()
            self._msg_times = [t for t in self._msg_times if now - t < self.RATE_LIMIT_WINDOW]
            if len(self._msg_times) >= self.RATE_LIMIT_MSGS:
                return
            self._msg_times.append(now)

            channel_entry = {
                "type": "chat.message",
                "nick": self.nickname,
                "phrase": phrase,
            }
            history_entry = {
                "chat": True,
                "nick": self.nickname,
                "phrase": phrase,
            }
            try:
                await self.channel_layer.group_send("chat", channel_entry)
            except Exception:
                pass
            await self._save_to_history(history_entry)
        except json.JSONDecodeError:
            pass

    async def chat_message(self, event):
        try:
            await self.send(text_data=json.dumps({
                "chat": True,
                "nick": event["nick"],
                "phrase": event["phrase"],
            }))
        except Exception:
            pass

    async def chat_system(self, event):
        try:
            await self.send(text_data=json.dumps({
                "chat": True,
                "system": event["message"],
            }))
        except Exception:
            pass

    async def send_history(self):
        lines = await asyncio.get_event_loop().run_in_executor(
            None, self._read_chat_history
        )
        for line in lines:
            await self.send(text_data=json.dumps(line))

    def _read_chat_history(self):
        try:
            with open(CHAT_HISTORY_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return [json.loads(l) for l in lines[-CHAT_HISTORY_LINES:]]
        except (OSError, json.JSONDecodeError):
            return []

    async def _save_to_history(self, entry):
        def sync_save():
            try:
                path = CHAT_HISTORY_PATH
                if os.path.exists(path) and os.path.getsize(path) > self.HISTORY_MAX_SIZE:
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    with open(path, "w", encoding="utf-8") as f:
                        f.writelines(lines[-self.HISTORY_MAX_LINES:])
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError:
                pass
        await asyncio.get_event_loop().run_in_executor(None, sync_save)
