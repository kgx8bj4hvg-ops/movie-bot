import pandas as pd
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes


print("Loading data...")
print("Current files:", os.listdir())

df = pd.read_csv("tmdb_5000_movies.csv", encoding="utf-8")
df = df[['title', 'overview', 'vote_average', 'genres', 'keywords', 'production_countries']].dropna()


def parse_json(text):
    try:
        return [x['name'].lower() for x in json.loads(text)]
    except:
        return []


df['genres'] = df['genres'].apply(parse_json)
df['production_countries'] = df['production_countries'].apply(parse_json)

print("Data ready")

all_genres = sorted({g for sublist in df['genres'] for g in sublist})
all_countries = sorted({c for sublist in df['production_countries'] for c in sublist})


def make_keyboard(options, row_size=3):
    return [options[i:i+row_size] for i in range(0, len(options), row_size)]


user_preferences = {}


def recommend(genre=None, country=None, rating=None):
    filtered = df.copy()

    if genre:
        filtered = filtered[filtered['genres'].apply(lambda x: genre in x)]
    if country:
        filtered = filtered[filtered['production_countries'].apply(lambda x: country in x)]
    if rating:
        filtered = filtered[filtered['vote_average'] >= rating]

    if filtered.empty:
        return None

    return filtered.sort_values(by='vote_average', ascending=False).head(5)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["🎬 Choose"], ["🎲 Random"], ["❌ Reset"]]
    await update.message.reply_text(
        "Welcome 🎬",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    user_id = update.message.from_user.id

    if user_id not in user_preferences:
        user_preferences[user_id] = {}

    prefs = user_preferences[user_id]

    if "reset" in text:
        user_preferences[user_id] = {}
        await start(update, context)
        return

    if "random" in text:
        row = df.sample(1).iloc[0]
        await update.message.reply_text(f"🎲 {row['title']} ⭐ {row['vote_average']}")
        return

    if "choose" in text:
        prefs.clear()
        keyboard = make_keyboard(all_genres)
        await update.message.reply_text(
            "Choose genre 🎬",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    if "genre" not in prefs:
        prefs["genre"] = text

        keyboard = make_keyboard(all_countries)
        keyboard.append(["none"])

        await update.message.reply_text(
            "Choose country 🌍",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    if "country" not in prefs:
        prefs["country"] = None if text == "none" else text

        keyboard = [["5", "6"], ["7", "8"], ["none"]]

        await update.message.reply_text(
            "Choose rating ⭐",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    if "rating" not in prefs:
        if text != "none":
            try:
                prefs["rating"] = float(text)
            except:
                prefs["rating"] = None
        else:
            prefs["rating"] = None

        results = recommend(
            genre=prefs.get("genre"),
            country=prefs.get("country"),
            rating=prefs.get("rating")
        )

        if results is None:
            await update.message.reply_text("Nothing found 😢")
        else:
            msg = "🎬 Movies:\n\n"
            for _, r in results.iterrows():
                msg += f"{r['title']} ⭐ {r['vote_average']}\n"

            await update.message.reply_text(msg)

        user_preferences[user_id] = {}
        await start(update, context)


# ===== TELEGRAM APP =====
app = ApplicationBuilder().token("token_here").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))


# ===== FAKE WEB SERVER (Render) =====
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running')


def run_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    server.serve_forever()

# ===== MAIN =====
if __name__ == "__main__":
    print("Bot is running...")

    
    threading.Thread(target=run_web).start()

 
    app.run_polling()
