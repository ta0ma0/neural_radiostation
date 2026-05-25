import json
import os
from datetime import datetime

import requests
from dotenv import load_dotenv


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


# Загрузка переменных окружения из .env файла
load_dotenv()
last_fm_key = os.getenv("LAST_FM_KEY")


def search_artist(artist_name):
    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.search&artist={artist_name}&api_key={last_fm_key}&format=json"
    print(
        f"Searching artist with URL: http://ws.audioscrobbler.com/2.0/?method=artist.search&artist={artist_name}"
    )
    response = requests.get(url)
    print(f"Response status code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        # print("Search results JSON:")
        # print(data)
        return data
    else:
        print(f"Error searching artist: {response.status_code}")
        print(f"Response content: {response.text}")
        return None


def get_artist_info(artist_name):
    url = f"http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={artist_name}&api_key={last_fm_key}&format=json"
    print(
        f"Getting artist info with URL: http://ws.audioscrobbler.com/2.0/?method=artist.getinfo&artist={artist_name}&"
    )
    response = requests.get(url)
    print(f"Response status code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        tty_log(f"Last.fm say: {response.status_code}")
        tty_log(f"")
        # print("Artist info JSON:")
        # print(data)
        return data
    else:
        print(f"Error getting artist info: {response.status_code}")
        print(f"Response content: {response.text}")
        return None


def main(artist_name_mp3):
    if not last_fm_key:
        print("LAST_FM_KEY not found in .env file")
    else:
        # print(f"Using API key: {last_fm_key}")
        artist_name = artist_name_mp3
        print(f"Searching for artist: {artist_name}")
        search_results = search_artist(artist_name)
        # if search_results:
        #     print(f"Search results for {artist_name}:")
        #     print(search_results)

        # Получение информации о первом найденном артисте
        if (
            "results" in search_results
            and "artistmatches" in search_results["results"]
            and "artist" in search_results["results"]["artistmatches"]
        ):
            first_artist = search_results["results"]["artistmatches"]["artist"][0]
            artist_name = first_artist["name"]
            print(f"First artist found: {artist_name}")
            artist_info = get_artist_info(artist_name)
            # print(artist_info)
            return artist_info


if __name__ == "__main__":
    answer = main("GusGus")
    # print(type(answer["artist"]))
    t = answer.get("artist")
    print(t.get("bio").get("summary"))
    # for key in answer["artist"]:
    #     print(key.get("bio"))
