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

def check_retry(prize_id, message_id, chat_id):
    winners_count = manager.get_winners_count(prize_id)
    if winners_count < 3:
        img = manager.get_prize_img(prize_id)
        with open(f'hidden_img/{img}', 'rb') as photo:
            bot.send_photo(chat_id, photo, caption="Вторая попытка! Успей забрать!", reply_markup=gen_markup(id=prize_id))

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

Только три первых пользователя получат картинку!)
Зарабатывай монетки за победы и трать их на бонусы с помощью /buy_retry!""")

@bot.message_handler(commands=['rating'])
def handle_rating(message):
    res = manager.get_rating() 
    res = [f'| @{x[0]:<11} | {x[1]:<11}|\n{"_"*26}' for x in res]
    res = '\n'.join(res)
    res = f'|USER_NAME    |COUNT_PRIZE|\n{"_"*26}\n' + res
    bot.send_message(message.chat.id, res)

@bot.message_handler(commands=['buy_retry'])
def buy_retry(message):
    user_id = message.chat.id
    cost = 50
    balance = manager.get_user_balance(user_id)
    if balance < cost:
        bot.reply_to(message, f"Недостаточно монет! У тебя {balance} монет, нужно {cost}.")
        return
    result = manager.get_random_prize()
    if result is None:
        bot.reply_to(message, "Нет доступных призов!")
        return
    prize_id, img, _, _, _ = result
    manager.decrement_balance(user_id, cost)
    with open(f'hidden_img/{img}', 'rb') as photo:
        bot.send_photo(user_id, photo, caption="Ты купил повторную попытку!", reply_markup=gen_markup(id=prize_id))

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

@bot.message_handler(commands=['progress'])
def show_progress(message):
    user_id = message.chat.id
    won = manager.get_winners_img(user_id)
    total_images = len(os.listdir('img'))
    won_count = len(won)
    bot.reply_to(message, f"Ты собрал {won_count} из {total_images} картинок! {100 * won_count / total_images:.1f}% коллекции.")

@bot.message_handler(content_types=['photo'], commands=['add_prize'])
def add_prize(message):
    user_id = message.chat.id
    if not manager.is_admin(user_id):
        bot.reply_to(message, "Только админы могут добавлять призы!")
        return
    if not message.photo:
        bot.reply_to(message, "Пожалуйста, отправь фото!")
        return
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    img_name = f"prize_{int(time.time())}.jpg"
    img_path = os.path.join('img', img_name)
    with open(img_path, 'wb') as new_file:
        new_file.write(downloaded_file)
    manager.add_prize([(img_name, 1)])  # 1 - обычный приз, можно указать 2 для редкого
    hide_img(img_name)
    bot.reply_to(message, f"Приз {img_name} добавлен!")

@bot.message_handler(commands=['set_schedule'])
def set_schedule(message):
    user_id = message.chat.id
    if not manager.is_admin(user_id):
        bot.reply_to(message, "Только админы могут менять расписание!")
        return
    try:
        minutes = int(message.text.split()[1])
        schedule.clear()
        schedule.every(minutes).minutes.do(send_message)
        bot.reply_to(message, f"Расписание установлено: каждые {minutes} минут.")
    except (IndexError, ValueError):
        bot.reply_to(message, "Укажи количество минут, например: /set_schedule 5")

@bot.message_handler(commands=['add_bonus'])
def add_bonus(message):
    user_id = message.chat.id
    if not manager.is_admin(user_id):
        bot.reply_to(message, "Только админы могут начислять бонусы!")
        return
    try:
        target_user_id, amount = map(int, message.text.split()[1:3])
        manager.increment_balance(target_user_id, amount)
        bot.reply_to(message, f"Начислено {amount} монет пользователю {target_user_id}.")
    except (IndexError, ValueError):
        bot.reply_to(message, "Укажи ID пользователя и количество монет, например: /add_bonus 12345 50")

@bot.message_handler(commands=['add_admin'])
def add_admin(message):
    user_id = message.chat.id
    if not manager.is_admin(user_id):
        bot.reply_to(message, "Только админы могут назначать новых админов!")
        return
    try:
        target_user_id = int(message.text.split()[1])
        manager.add_admin(target_user_id)
        bot.reply_to(message, f"Пользователь {target_user_id} назначен админом.")
    except (IndexError, ValueError):
        bot.reply_to(message, "Укажи ID пользователя, например: /add_admin 12345")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):

    prize_id = call.data
    user_id = call.message.chat.id
    bonus_multiplier = manager.get_prize_bonus_multiplier(prize_id)
    
    if manager.get_winners_count(prize_id) < 3:
        res = manager.add_winner(user_id, prize_id)
        if res:
            img = manager.get_prize_img(prize_id)
            with open(f'img/{img}', 'rb') as photo:
                bot.send_photo(user_id, photo, caption=f"Поздравляем! Ты получил картинку! +{10 * bonus_multiplier} монет!")
        else:
            bot.send_message(user_id, 'Ты уже получил картинку!')
    else:
        bot.send_message(user_id, "К сожалению, ты не успел получить картинку! Попробуй в следующий раз!)")


        


def polling_thread():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()

    polling_thread = threading.Thread(target=polling_thread)
    polling_shedule = threading.Thread(target=shedule_thread)

    polling_thread.start()
    polling_shedule.start()
  
