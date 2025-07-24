import os
import re
import time
import requests
import subprocess
import uuid
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")  # Ensure .env contains BOT_TOKEN and FORWARD_TO_ID

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
        artist, song = song_query.split(" - ", 1)
        res = requests.get(f"https://api.lyrics.lewagon.ai/v1/{artist}/{song}", timeout=10)
        if res.status_code == 200:
            return res.json().get("lyrics", "No lyrics found.")
        return "Lyrics not found."
    except:
        return "❌ Could not fetch lyrics. Use: @lyrics Artist - Song Name"


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
    try:
        response = requests.post(url, json={"query": query, "variables": variables})
        data = response.json()
        media = data.get("data", {}).get("Media")
        if not media:
            return "Anime not found."

        title = f"{media['title']['english']} ({media['title']['romaji']})" if media['title']['english'] else media['title']['romaji']
        description = re.sub('<[^<]+?>', '', media['description'])[:600] + "..."
        return (
            f"📺 *{title}*\n"
            f"🎯 *Status:* {media['status']}\n"
            f"🎬 *Episodes:* {media['episodes']}\n"
            f"⭐ *Score:* {media['averageScore']}\n"
            f"📝 *Description:* {description}\n"
            f"[📷 Cover Image]({media['coverImage']['large']})"
        )
    except Exception as e:
        return f"❌ Error fetching anime info: {e}"


def handle_user_message(message):
    chat_id = message["chat"]["id"]
    user_msg = message.get("text", "")

    if user_msg.startswith("/start"):
        send_message(chat_id, "👋 Welcome to the Music & Anime Bot!\nUse /help to see features.")
        return

    if user_msg.startswith("/help"):
        send_message(chat_id, (
            "Here are commands you can use:\n"
            "- Paste any YouTube/Instagram/Spotify link for audio/video\n"
            "- @lyrics Artist - SongName\n"
            "- @animeinfo AnimeName"
        ))
        return

    # Forward to private group
    requests.post(f"{API_URL}/forwardMessage", json={
        "chat_id": FORWARD_TO_ID,
        "from_chat_id": chat_id,
        "message_id": message["message_id"]
    })

    # @lyrics command
    if user_msg.startswith("@lyrics"):
        song = user_msg.replace("@lyrics", "").strip()
        if not song:
            send_message(chat_id, "❗ Use like: @lyrics Eminem - Lose Yourself")
            return
        lyrics = fetch_lyrics(song)
        send_message(chat_id, f"🎶 Lyrics for *{song}*:\n\n{lyrics[:4000]}")
        return

    # @animeinfo command
    if user_msg.startswith("@animeinfo"):
        name = user_msg.replace("@animeinfo", "").strip()
        if not name:
            send_message(chat_id, "❗ Use like: @animeinfo Jujutsu Kaisen")
            return
        info = fetch_anime_info(name)
        requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": info,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        })
        return

    # URL handler (YT, Spotify, Instagram)
    yt_match = re.search(r"(https?://[^\s]+)", user_msg)
    if yt_match:
        url = yt_match.group(1)
        is_instagram = "instagram.com" in url

        extension = ".mp4" if is_instagram else ".mp3"
        filename = str(uuid.uuid4()) + extension

        send_message(chat_id, "⏬ Downloading... Please wait.")
        try:
            cmd = ["yt-dlp", "-f", "best", "-o", filename, url] if is_instagram else [
                "yt-dlp", "--extract-audio", "--audio-format", "mp3", "-o", filename, url
            ]
            subprocess.run(cmd, check=True)

            if extension == ".mp4":
                send_video(chat_id, filename)
            else:
                send_audio(chat_id, filename)
        except Exception as e:
            send_message(chat_id, f"❌ Download failed: {e}")
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
            if "message" in update:
                handle_user_message(update["message"])
        time.sleep(1)


if __name__ == "__main__":
    main()
