import os
import re
import time
import uuid
import requests
import subprocess
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
FORWARD_TO_ID = os.getenv("FORWARD_TO_ID")
GENIUS_ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text, reply_to=None, parse_mode="Markdown"):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_to:
        data["reply_to_message_id"] = reply_to
    requests.post(f"{API_URL}/sendMessage", data=data)

def forward_to_owner(user_data, message):
    log = f"👤 *User ID:* `{user_data.get('id')}`\n" \
          f"🧑 *Username:* @{user_data.get('username', 'N/A')}\n" \
          f"💬 *Message:* {message}"
    send_message(FORWARD_TO_ID, log)

def fetch_lyrics(song):
    headers = {"Authorization": f"Bearer {GENIUS_ACCESS_TOKEN}"}
    search_url = f"https://api.genius.com/search?q={quote(song)}"
    response = requests.get(search_url, headers=headers)
    data = response.json()
    hits = data.get("response", {}).get("hits", [])
    if not hits:
        return "❌ Lyrics not found."

    song_url = hits[0]["result"]["url"]
    page = requests.get(song_url).text

    match = re.search(r'<div class="Lyrics__Root.*?>(.*?)</div>', page, re.DOTALL)
    if match:
        raw_lyrics = match.group(1)
        clean = re.sub(r'<.*?>', '', raw_lyrics).strip()
        return f"*📄 Full Lyrics:*\n\n{clean[:4000]}"  # 4000 Telegram limit
    return f"🔗 [View Full Lyrics]({song_url}) on Genius"

def fetch_anime_info(anime_name):
    query = """
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title { romaji english }
        description(asHtml: false)
        episodes
        status
        averageScore
        coverImage { large }
        recommendations(perPage: 3, sort: RATING_DESC) {
          nodes {
            mediaRecommendation {
              title { romaji }
            }
          }
        }
      }
    }"""
    variables = {"search": anime_name}
    url = "https://graphql.anilist.co"
    response = requests.post(url, json={"query": query, "variables": variables})
    media = response.json().get("data", {}).get("Media")
    if not media:
        return "❌ Anime not found.", None

    title = media["title"]["romaji"]
    desc = media["description"][:500].replace("<br>", "\n")
    score = media.get("averageScore", "N/A")
    status = media.get("status", "N/A")
    episodes = media.get("episodes", "N/A")
    cover = media["coverImage"]["large"]
    recs = media.get("recommendations", {}).get("nodes", [])
    recommendations = "\n".join([f"🔸 {r['mediaRecommendation']['title']['romaji']}" for r in recs])

    info = f"*🎞️ {title}*\n\n" \
           f"*Status:* {status}\n" \
           f"*Episodes:* {episodes}\n" \
           f"*Score:* {score}\n\n" \
           f"*📝 Description:*\n{desc}...\n\n" \
           f"*🔥 Recommendations:*\n{recommendations}"
    return info, cover

def download_video(url):
    file_id = str(uuid.uuid4())
    out_file = f"/tmp/{file_id}.mp4"
    cmd = [
        "yt-dlp", "-f", "mp4", "-o", out_file, url
    ]
    try:
        subprocess.run(cmd, check=True)
        return out_file
    except Exception as e:
        return None

def send_video(chat_id, file_path, caption=None):
    with open(file_path, "rb") as video:
        requests.post(
            f"{API_URL}/sendVideo",
            data={"chat_id": chat_id, "caption": caption or "", "parse_mode": "Markdown"},
            files={"video": video}
        )

def get_updates(offset=None):
    url = f"{API_URL}/getUpdates"
    if offset:
        url += f"?offset={offset}"
    return requests.get(url).json()

def main():
    print("✅ Bot is running...")
    last_update_id = None

    while True:
        updates = get_updates(last_update_id)
        for update in updates.get("result", []):
            last_update_id = update["update_id"] + 1
            msg = update.get("message")
            if not msg:
                continue

            chat_id = msg["chat"]["id"]
            message_id = msg["message_id"]
            text = msg.get("text", "")
            user = msg.get("from", {})

            forward_to_owner(user, text)

            if text.startswith("/start"):
                send_message(chat_id, "👋 Welcome! Use `/lyrics Song - Artist`, `/anime AnimeName`, or `/video URL`", reply_to=message_id)

            elif text.startswith("/lyrics"):
                query = text.replace("/lyrics", "").strip()
                if not query:
                    send_message(chat_id, "❌ Please provide a song name.", reply_to=message_id)
                else:
                    lyrics = fetch_lyrics(query)
                    send_message(chat_id, lyrics, reply_to=message_id)

            elif text.startswith("/anime"):
                query = text.replace("/anime", "").strip()
                if not query:
                    send_message(chat_id, "❌ Please provide an anime name.", reply_to=message_id)
                else:
                    info, image_url = fetch_anime_info(query)
                    if image_url:
                        img = requests.get(image_url, stream=True).raw
                        requests.post(
                            f"{API_URL}/sendPhoto",
                            data={"chat_id": chat_id, "caption": info, "parse_mode": "Markdown"},
                            files={"photo": img}
                        )
                    else:
                        send_message(chat_id, info, reply_to=message_id)

            elif text.startswith("/video"):
                url = text.replace("/video", "").strip()
                if not url:
                    send_message(chat_id, "❌ Please provide a video URL.", reply_to=message_id)
                else:
                    send_message(chat_id, "📥 Downloading video, please wait...")
                    path = download_video(url)
                    if path:
                        send_video(chat_id, path, caption="📹 Here's your video!")
                        os.remove(path)
                    else:
                        send_message(chat_id, "❌ Failed to download video.")

        time.sleep(2)

if __name__ == "__main__":
    main()
