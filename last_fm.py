import os

import requests
from dotenv import load_dotenv

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
