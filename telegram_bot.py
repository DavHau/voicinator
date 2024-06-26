import os
import tempfile
import telebot
import voice_conveter
import summarize
import credentials
from telebot import TeleBot
from telebot import types
import json
# from pydub.utils import mediainfo


BOT_TOKEN = credentials.get_secret("telegram_token")
bot = telebot.TeleBot(BOT_TOKEN)
user_message_context = {}
# status for summary
# action = True


@bot.message_handler(commands=['start', 'how', '?'])
def send_welcome(message):
    bot.reply_to(message, "Hello and welcome, i am your personal speech to text bot. With /configure_language you can"
                          "define you Mother language. With /configure_summary you can add your personal preferences"
                          " for the summarization tool. And with /configure_speed you can choose a modell size for your"
                          " transcription. If you forgot any command you can type in rather /start, /how or joust"
                          " a question sign /? . Dont forget: for any command you need a slash(/)."
                          " Have fun and a produktiv time")


@bot.message_handler(commands=['configure_language'])
def configure_language(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    english = types.InlineKeyboardButton("english", callback_data="english")
    spanish = types.InlineKeyboardButton("spanish", callback_data="spanish")
    german = types.InlineKeyboardButton("german", callback_data="german")
    japanese = types.InlineKeyboardButton("japanese", callback_data="japanese")
    markup.add(english, spanish, german, japanese)

    bot.send_message(message.chat.id, 'Into which languages should the message be translated?', reply_markup=markup)

    # saving the original message to identify it later
    user_message_context[message.chat.id] = 'configure_language'


@bot.message_handler(commands=['configure_summary'])
def configure_summary(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    middle = types.InlineKeyboardButton("middle", callback_data="middle")
    soft = types.InlineKeyboardButton("soft", callback_data="soft")
    strong = types.InlineKeyboardButton("strong", callback_data="strong")
    deactivate = types.InlineKeyboardButton("deactivate", callback_data="deactivate")
    markup.add(middle, soft, strong, deactivate)

    bot.send_message(message.chat.id, 'The summarization tool allows you to summarize long audio messages. You can '
                                      'rather deactivate it, or activate it. The length of the summarization depends'
                                      'on the length of the message', reply_markup=markup)

    # saving the original message to identify it later
    user_message_context[message.chat.id] = 'configure_summary'


@bot.callback_query_handler(func=lambda call: True)
def answer(callback):
    if callback.message:
        user_context = user_message_context.get(callback.message.chat.id, None)
        # saving the users mother language in json data
        if user_context == 'configure_language':
            toggle_language_status(callback)
        # saving the users preferences for the summarization in the user specific json data
        elif user_context == 'configure_summary':
            toggle_summarization_status(callback)


def toggle_summarization_status(callback):
    action = True if callback.data != "deactivate" else False
    bot.send_message(callback.message.chat.id,
                     f"Summarization has been {'activated' if action else 'deactivated'}!")
    user_summary_pref = {"id": callback.message.chat.id, "summary_status": action,
                         "state_of_summarization": callback.data}
    save_user_settings(user_summary_pref)


def toggle_language_status(callback):
    print(callback.data)
    bot.send_message(callback.message.chat.id, f"All your messages will now be translated to {callback.data}!")
    user_language_pref = {"id": callback.message.chat.id, "language": callback.data}
    save_user_settings(user_language_pref)


def save_user_settings(user_preferences):
    # check if settings.json exists
    if os.path.exists("settings.json"):
        with open("settings.json", 'r') as file:
            data = json.load(file)
        if 'user_preferences' in data:
            data['user_preferences'].update(user_preferences)
        else:
            data['user_preferences'] = user_preferences
    else:
        # Neue Datei mit user_preferences erstellen
        data = {'user_preferences': user_preferences}

    # JSON-Daten in die Datei schreiben
    with open("settings.json", 'w') as file:
        json.dump(data, file, indent=4)


@bot.message_handler(content_types=['voice', 'audio', 'document'])
def voice_processing(message):
    if message.voice:
        file_info = bot.get_file(message.voice.file_id)
    elif message.audio:
        file_info = bot.get_file(message.audio.file_id)
    else:
        file_info = bot.get_file(message.document.file_id)
    downloaded_bytes = bot.download_file(file_info.file_path)

    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as voice_file:
        voice_file.write(downloaded_bytes)
        voice_file.seek(0)

    """MESSAGE 1"""
    used_model = voice_conveter.model_1
    print(f"Transcribing using model {used_model}")
    transcription_1 = voice_conveter.transcribe(str(voice_file.name), used_model)
    answer_transcription = bot.reply_to(message, transcription_1)
    summary_1 = summarize.gpt_message_handler(transcription_1, answer_transcription.chat.id)
    chat_id = answer_transcription.chat.id
    summarize_and_translate = bot.edit_message_text(summary_1, chat_id, answer_transcription.message_id)

    # second pass with better transcription model
    """Message 2"""
    used_model = voice_conveter.model_2
    print(f"Transcribing using model {used_model}")
    transcription_2 = voice_conveter.transcribe(str(voice_file.name), used_model)
    # edit transcription message with improved transcription
    chat_id = answer_transcription.chat.id
    bot.edit_message_text(transcription_2, chat_id, answer_transcription.message_id)
    summary_2 = summarize.gpt_message_handler(transcription_2, answer_transcription.chat.id)
    # edit summary message with improved summary
    bot.edit_message_text(summary_2, chat_id, summarize_and_translate.message_id)


print("ready to read messages")
bot.infinity_polling()
