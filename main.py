# --- Improved Telegram Bot Code ---

import os
import re
import time
import requests
import subprocess
import uuid
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")  # Make sure .env is present in the same directory

BOT_TOKEN = os.getenv("BOT_TOKEN")
FORWARD_TO_ID = os.getenv("FORWARD_TO_ID")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})


def send_audio(chat_id, file_path, caption=None):
    with open(file_path, "rb") as f:
        requests.post(f"{API_URL}/sendAudio", data={"chat_id": chat_id, "caption": caption or ""}, files={"audio": f})


def send_video(chat_id, file_path, caption=None):
    with open(file_path, "rb") as f:
        requests.post(f"{API_URL}/sendVideo", data={"chat_id": chat_id, "caption": caption or ""}, files={"video": f})


def fetch_lyrics(song_query):
    try:
        response = requests.get(f"https://api.lyrics.ovh/v1/{song_query}", timeout=10)
        if response.status_code == 200:
            return response.json().get("lyrics", "No lyrics found.")
        else:
            return "Lyrics not found."
    except:
        return "Lyrics fetch error."


def fetch_anime_info(anime_name):
    query = """
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title {
          romaji
          english
        }
        description(asHtml: false)
        episodes
        status
        averageScore
        coverImage {
          large
        }
      }
    }
    """
    variables = {"search": anime_name}
    url = "https://graphql.anilist.co"
    response = requests.post(url, json={"query": query, "variables": variables})
    data = response.json()
    media = data.get("data", {}).get("Media")
    if not media:
        return "Anime not found."

    return f"Title: {media['title']['romaji']}\nStatus: {media['status']}\nEpisodes: {media['episodes']}\nScore: {media['averageScore']}\nDescription: {media['description'][:300]}..."


def handle_user_message(message):
    chat_id = message["chat"]["id"]
    user_msg = message.get("text", "")

    if user_msg.startswith("/start"):
        send_message(chat_id, "👋 Welcome to the Music & Anime Bot! Use /help to see all features.")
        return

    if user_msg.startswith("/help"):
        send_message(chat_id, "Here are commands you can use:\n- Send a Spotify/YouTube link to get audio\n- Send Instagram reel link for video\n- @lyrics SongName - ArtistName\n- @animeinfo AnimeName")
        return

    # Forward all messages to private group
    requests.post(f"{API_URL}/forwardMessage", json={
        "chat_id": FORWARD_TO_ID,
        "from_chat_id": chat_id,
        "message_id": message["message_id"]
    })

    # Handle Lyrics Command
    if user_msg.startswith("@lyrics"):
        song = user_msg.replace("@lyrics", "").strip()
        if not song:
            send_message(chat_id, "Please provide song and artist: @lyrics SongName - Artist")
            return
        lyrics = fetch_lyrics(song)
        send_message(chat_id, f"🎶 Lyrics for {song}:\n\n{lyrics[:4000]}")
        return

    # Handle Anime Command
    if user_msg.startswith("@animeinfo"):
        name = user_msg.replace("@animeinfo", "").strip()
        if not name:
            send_message(chat_id, "Please provide an anime name like: @animeinfo Jujutsu Kaisen")
            return
        info = fetch_anime_info(name)
        send_message(chat_id, info)
        return

    # Handle Downloading Music/Video
    yt_match = re.search(r"(https?://[\w./?=-]+)", user_msg)
    if yt_match:
        url = yt_match.group(1)
        filename = str(uuid.uuid4()) + ".mp3"
        try:
            send_message(chat_id, "🔄 Downloading your file, please wait...")
            subprocess.run(["yt-dlp", "--extract-audio", "--audio-format", "mp3", "-o", filename, url], check=True)
            send_audio(chat_id, filename)
        except Exception as e:
            send_message(chat_id, f"Download failed: {e}")
        finally:
            if os.path.exists(filename):
                os.remove(filename)
        return

    send_message(chat_id, "❓ Unknown command or link. Use /help to see available commands.")


def main():
    offset = 0
    while True:
        response = requests.get(f"{API_URL}/getUpdates", params={"offset": offset, "timeout": 30})
        updates = response.json().get("result", [])

        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message")
            if message:
                handle_user_message(message)

        time.sleep(1)


if __name__ == "__main__":
    main()
