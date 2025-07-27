from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import *
import schedule
import threading
import time
from config import *
import os
from logic import create_collage

# Устанавливаем рабочую директорию в папку, где лежит этот файл
os.chdir(os.path.dirname(os.path.abspath(__file__)))

bot = TeleBot(API_TOKEN)

def gen_markup(id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Получить!", callback_data=id))
    return markup

'''@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    prize_id = call.data
    user_id = call.message.chat.id

    img = manager.get_prize_img(prize_id)
    with open(f'img/{img}', 'rb') as photo:
        bot.send_photo(user_id, photo)'''


def send_message():
    result = manager.get_random_prize()
    if result is None:
        print("[ОШИБКА] Нет доступных призов. Сбросим used.")
        manager.reset_all_prizes()
        return  # остановим выполнение
    prize_id, img = result[:2]
    manager.mark_prize_used(prize_id)
    hide_img(img)
    hidden_path = os.path.join('hidden_img', img)
    for user in manager.get_users():
        try:
            with open(f'hidden_img/{img}', 'rb') as photo:
                bot.send_photo(user, photo, reply_markup=gen_markup(id = prize_id))
        except FileNotFoundError:
            print(f"[ОШИБКА] Не найден файл: {hidden_path}")

def shedule_thread():
    schedule.every().minute.do(send_message) # Здесь ты можешь задать периодичность отправки картинок
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    if user_id in manager.get_users():
        bot.reply_to(message, "Ты уже зарегестрирован!")
    else:
        manager.add_user(user_id, message.from_user.username)
        bot.reply_to(message, """Привет! Добро пожаловать! 
Тебя успешно зарегистрировали!
Каждый час тебе будут приходить новые картинки и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку 'Получить!'

Только три первых пользователя получат картинку!)""")


@bot.message_handler(commands=['rating'])
def handle_rating(message):
    res = manager.get_rating() 
    res = [f'| @{x[0]:<11} | {x[1]:<11}|\n{"_"*26}' for x in res]
    res = '\n'.join(res)
    res = f'|USER_NAME    |COUNT_PRIZE|\n{"_"*26}\n' + res
    bot.send_message(message.chat.id, res)
    
    
    
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    prize_id = call.data
    user_id = call.message.chat.id

    if manager.get_winners_count(prize_id) < 3:
        res = manager.add_winner(user_id, prize_id)
        if res:
            img = manager.get_prize_img(prize_id)
            with open(f'img/{img}', 'rb') as photo:
                bot.send_photo(user_id, photo, caption="Поздравляем! Ты получил картинку!")
        else:
            bot.send_message(user_id, 'Ты уже получил картинку!')
    else:
        bot.send_message(user_id, "К сожалению, ты не успел получить картинку! Попробуй в следующий раз!)")

@bot.message_handler(commands=['get_my_score'])
def get_my_score(message):
    user_id = message.chat.id
    all_images = os.listdir('img')
    won = manager.get_winners_img(user_id)
    won_set = {img[0] for img in won}

    paths = [
        f'img/{name}' if name in won_set else f'hidden_img/{name}'
        for name in all_images
    ]

    collage = create_collage(paths)
    if collage is None:
        bot.send_message(user_id, "У вас пока нет ни одной картинки.")
        return

    path_to_file = f'collage_{user_id}.jpg'
    cv2.imwrite(path_to_file, collage)

    with open(path_to_file, 'rb') as photo:
        bot.send_photo(user_id, photo, caption="Ваш коллаж достижений!")

    os.remove(path_to_file)

def polling_thread():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()

    polling_thread = threading.Thread(target=polling_thread)
    polling_shedule = threading.Thread(target=shedule_thread)

    polling_thread.start()
    polling_shedule.start()
  
