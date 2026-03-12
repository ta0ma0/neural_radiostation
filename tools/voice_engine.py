import os
import subprocess
from datetime import datetime


def tty_log(message, style="info"):
    colors = {
        "info": "\033[32m[SYSTEM]\033[0m",
        "on_air": "\033[36m[ON AIR]\033[0m",
        "ai": "\033[35m[⚙️ AI]\033[0m",
        "error": "\033[31m[ERROR]\033[0m",
        "time": f"\033[90m{datetime.now().strftime('%H:%M:%S')}\033[0m",
    }
    prefix = colors.get(style, colors["info"])

    # 1. Формируем строку сообщения
    full_message = f"{colors['time']} {prefix} {message}"

    # 2. Пишем в файл (для контейнера)
    with open(
        "/home/ruslan/Develop/Music/dj_alyx/django-aws-terminal-websocket/dj_alyx_radio.log",
        "a",
        encoding="utf-8",
    ) as f:
        f.write(f"{full_message}\n")

    # 3. Выводим в консоль с flush=True
    print(full_message, flush=True)


class AlyxVoice:
    def __init__(self, model_path, ref_text, ref_audio, device="cpu"):
        self.model_path = model_path
        self.ref_audio = ref_audio
        self.ref_text = ref_text
        self.device = device
        tty_log("[*] [System]: Voice Engine инициализирован.")

    def generate(self, text, output_path, speed=1.1):
        # 1. Определяем пути
        base_path = os.path.splitext(output_path)[0]
        wav_path = base_path + ".wav"
        mp3_path = base_path + ".mp3"

        output_dir = os.path.dirname(wav_path)
        output_filename = os.path.basename(wav_path)

        cmd = [
            "python",
            "-m",
            "f5_tts.infer.infer_cli",
            "-p",
            self.model_path,
            "-r",
            self.ref_audio,
            "-s",
            self.ref_text,
            "-t",
            text,
            "-o",
            output_dir,
            "-w",
            output_filename,
            "--device",
            self.device,
            "--nfe_step",
            "10",
            "--speed",
            str(speed),
        ]

        try:
            # 2. Генерация WAV
            subprocess.run(cmd, check=True, capture_output=True)

            if not os.path.exists(wav_path):
                return None

            # 3. Конвертация в MP3
            conv_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                wav_path,
                "-acodec",
                "libmp3lame",
                "-q:a",
                "2",
                mp3_path,
            ]
            subprocess.run(conv_cmd, check=True, capture_output=True)

            # 4. Удаляем исходный WAV
            if os.path.exists(wav_path):
                os.remove(wav_path)

            return mp3_path
        except subprocess.CalledProcessError as e:
            tty_log(f"[!] Ошибка CLI или FFmpeg: {e.stderr.decode()}")
            return None
