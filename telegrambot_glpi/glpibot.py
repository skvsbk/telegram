import os
import random
import time
import requests
import logging
import telebot
from telebot import types
from dotenv import load_dotenv
import glpidb
import glpiapi


# logging
logging.basicConfig(level=logging.WARNING, filename='glpibot.log', format='%(asctime)s %(name)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Credentials
load_dotenv('.env')

# bot token from @BotFather
BOT_TOKEN = os.getenv('BOT_TOKEN')
URL_GLPI = os.getenv('URL_GLPI')

# relative path for files
FILE_PATH = os.getenv('FILE_PATH')

bot = telebot.TeleBot(BOT_TOKEN)

# Dicts for each message.chat.id (for each user)
user_dict = dict()
ticket_dict = dict()
glpi_dict = dict()
msgid_dict = {"": []}

# Keyboards
def make_keyboard_inlain(row_width, **bottons):
    '''
    Make inline keyboard
    :param row_width: number of row appears
    :param bottons: callback_data="botton_name"
    :return: InlineKeyboardMarkup
    '''
    markup = types.InlineKeyboardMarkup(row_width=row_width)
    l = []
    for callback_data, botton_name in bottons.items():
        l.append(types.InlineKeyboardButton(botton_name, callback_data=callback_data))
    args = (i for i in l)
    return markup.add(*args)

def select_title(message):
    '''
    Select title and get message.chat.id
    '''
    markup = make_keyboard_inlain(3, key_exitbot="Выход", key_newitem="Заявка в ИТ", key_instructions="Инструкции")
    send_id = bot.send_message(message.chat.id, "Выберите тему обращения:", reply_markup=markup)
    msgid_dict[message.chat.id].append(send_id.id)

def set_ticket_name_or_content(message, html_text):
    '''
    Setting ticket name or content depending on ticket name
    '''
    if ticket_dict[message.chat.id].name == '':
        ticket_dict[message.chat.id].name = html_text
    else:
        ticket_dict[message.chat.id].content += html_text + ', '

def download_file(file_info, message):
    '''
    Store file in local dir for further store in GLPI
    '''
    try:
        file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(BOT_TOKEN, file_info.file_path))
        # random part of filename
        file_add = str(random.randint(0, 1000))
        # get extension from file path
        file_ext = file_info.file_path[file_info.file_path.rfind('.') + 1:]
        filename = f'{message.chat.id}_{file_add}.{file_ext}'
        with open(FILE_PATH + '/' + filename, 'wb') as new_file:
            new_file.write(file.content)
        # add filename to class
        ticket_dict[message.chat.id].attachment.append(filename)
    except Exception as err:
        logger.warning('download_file(%s) - some errors: %s', str(message.chat.id), repr(err))
    finally:
        logger.info("the function download_file(message) is done for the id %s", str(message.chat.id))
        
def set_ticket_name_from_key(chat_id, message_id, name):
    '''
    Adding "(из Telegram)" to ticket_name and show message with the selected category
    '''
    ticket_dict[chat_id].ticket_name = f'{name} (из Telegram)'
    bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                          text=f'Категория: {name}', reply_markup=None)
    bot.send_message(chat_id, "Опишите проблему, сделайте фото или видео", reply_markup=None)

@bot.message_handler(commands=['stop'])
def execute_on_exit(message):
    bot.send_message(message.chat.id, "До новых встреч")
    time.sleep(10)
    try:
        for filename in ticket_dict[message.chat.id].attachment:
            if os.path.exists(FILE_PATH + '/' + filename):
                os.remove(FILE_PATH + '/' + filename)
        user_dict.pop(message.chat.id)
        glpi_dict.pop(message.chat.id)
        ticket_dict.pop(message.chat.id)
        msgid_dict.pop(message.chat.id)
    except:
        logger.warning('execute_on_exit(%s) - error cleaning dictionaries', str(message.chat.id))
    finally:
        logger.info('the function execute_on_exit(message) is done for the id %s', str(message.chat.id))

@bot.message_handler(commands=['start'])
def welcome(message):
    # Registration
    keyboard_send_phone = types.ReplyKeyboardMarkup(row_width=3)
    botton_auth = types.KeyboardButton("Отправить номер", request_contact=True)
    keyboard_send_phone.add(botton_auth)
    bot.send_message(chat_id=message.chat.id, text=f"Для авторизации необходим номер телефона.\nНажмите <b>" + \
                    "Отправить номер</b>\n\nОтправляя свой номер телефона Вы даете согласие на обработку " + \
                    "персональных данных (ФИО, номер телефона) в целях работы с информационной системой",
                     parse_mode='html', reply_markup=keyboard_send_phone)

@bot.message_handler(content_types=['contact'])
def read_contact_phone(message):
    phone = message.contact.phone_number
    if phone[0] != '+':
        phone = '+'+phone
    # Get user's credentials and continue if phone number contains in DB, else send /stop command
    user_credentials = glpidb.get_user_credentials(phone)   # dictionary with keys 'user_token' 'id' 'firstname'
    if user_credentials and user_credentials['user_token']:
        user_dict[message.chat.id] = glpiapi.User(id=user_credentials['id'], token=user_credentials['user_token'])
        # Get user session
        glpi_dict[message.chat.id] = glpiapi.GLPI(URL_GLPI, user=user_dict[message.chat.id])
        # Create empty ticket
        ticket_dict[message.chat.id] = glpiapi.Ticket()
        msgid_dict[message.chat.id] = [message.message_id]

        item_remove = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id,  f"Добро пожаловать, {user_credentials['firstname']}!",
                         reply_markup=item_remove)
        bot.send_message(message.chat.id, f"Я - бот компании Активный компонент. Со мной можно получить помощь ИТ отдела.",
                         reply_markup=None)
        select_title(message)
    else:
        bot.send_message(message.chat.id, "К сожалению мы не смоги Вас авторизовать. Заполните в системе поля " + \
                         "Мобильный телефон и Токен API или обратитесь в IT-отдел.", reply_markup=None)
        logger.warning('read_contact_phone(message) Authorisation Error for id %s and phone %s',
                       str(message.chat.id), phone)
        execute_on_exit(message)

@bot.message_handler(content_types=['text', 'photo', 'video', 'document'])
def get_data(message):
    if message.chat.type == 'private':
        try:
            if glpi_dict[message.chat.id].session is not None:
                if ticket_dict[message.chat.id].isnew:
                    if message.content_type == 'text':
                        set_ticket_name_or_content(message, message.html_text)
                    elif message.content_type == 'document':
                        file_info = bot.get_file(message.document.file_id)
                        download_file(file_info, message)
                    elif message.content_type == 'photo':
                        if message.html_caption is not None:
                            set_ticket_name_or_content(message, message.html_caption)
                        file_info = bot.get_file(message.photo[-1].file_id)
                        download_file(file_info, message)
                    elif message.content_type == 'video':
                        if message.html_caption is not None:
                            set_ticket_name_or_content(message, message.html_caption)
                        file_info = bot.get_file(message.video.file_id)
                        download_file(file_info, message)
                    else:
                        pass
                    # Delete message with inline keybaord
                    delmsgid = msgid_dict[message.chat.id].pop()
                    bot.delete_message(chat_id=message.chat.id, message_id=delmsgid)
                    markup = make_keyboard_inlain(3, key_continue="Дополнить", key_send="Отправить в ИТ",
                                                  key_cancel="Отменить")
                    send_id = bot.send_message(message.chat.id,"Вы можете дополнить заявку фото, видео или " + \
                                               "текстовым сообщением либо завершить", parse_mode='html',
                                               reply_markup=markup)
                    msgid_dict[message.chat.id].append(send_id.id)
                else:
                    delmsgid = msgid_dict[message.chat.id].pop()
                    bot.delete_message(chat_id=message.chat.id, message_id=delmsgid)
                    bot.send_message(message.chat.id,"Используйте, пожалуйста, кнопки.", parse_mode='html', 
                                     reply_markup=None)
                    select_title(message)
        except Exception as err:
            bot.send_message(message.chat.id, "Вероятно Вы не авторизованы. Введите /start",
                             parse_mode='html', reply_markup=None)
            logger.warning('get_data(%s) - some errors: %s', str(message.chat.id), repr(err))
            execute_on_exit(message)
        finally:
            logger.info("the function get_data(message) is done for the id %s", str(message.chat.id))

# Pushing inline keyboard
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    try:
        if call.message:
            if call.data == 'key_newitem':
                ticket_dict[call.message.chat.id].isnew = True
                markup = make_keyboard_inlain(2, key_1c="1С", key_office="Оргтехника в ИТ", key_support="поддержка")
                send_id = bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Выберите категорию:", reply_markup=markup)
                msgid_dict[call.message.chat.id].append(send_id.id)
            if call.data == 'key_instructions':
                markup = make_keyboard_inlain(3, key_guest_wifi="Пароль", key_VCC="Видеосвязь в ИТ",
                                              key_url_support="Система", key_url_docs="Другие инструкции")
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Выберите инструкцию:", reply_markup=markup)
            if call.data == 'key_guest_wifi':
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=f"Имя WiFi:  <b>{os.getenv('GUEST_SSID')}</b>\nПароль:  <b>{os.getenv('GUEST_PASS')}</b>",
                                      parse_mode='html', reply_markup=None)
                select_title(call.message)
            if call.data == 'key_VCC':
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=f"Видеоконференцсвязь: \n\n{os.getenv('VCC_1')}\n\n{os.getenv('VCC_2')}\n\n{os.getenv('VCC_3')}\n\n{os.getenv('VCC_4')}\n\n{os.getenv('VCC_5')}\n",
                                      parse_mode='html', reply_markup=None)
                select_title(call.message)
            if call.data == 'key_url_support':
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=f"Инструкция по входу в GLPI\n{os.getenv('URL_SUPPORT')}", reply_markup=None)
                select_title(call.message)
            if call.data == 'key_url_docs':
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=f"Другие инструкции\n{os.getenv('URL_DOCS')}", reply_markup=None)
                select_title(call.message)
            elif call.data == 'key_continue':
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Опишите проблему, сделайте фото или видео...", reply_markup=None)
            elif call.data == 'key_send':
                # send ticket
                glpi_dict[call.message.chat.id].ticket = ticket_dict[call.message.chat.id]
                ticket_id = glpi_dict[call.message.chat.id].create_ticket()
                ticket_dict[call.message.chat.id].id = ticket_id
                # upload files/photos/videos to glpi
                for filename in ticket_dict[call.message.chat.id].attachment:
                    doc_id = glpi_dict[call.message.chat.id].upload_doc(FILE_PATH, filename)
                    if doc_id is not None:
                        # update table glpi_documents_items
                        glpidb.update_doc_item(doc_id, ticket_id, user_dict[call.message.chat.id].id)
                if ticket_id is not None:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          text="Заявка №" + str(ticket_id) + " успешно оформлена", reply_markup=None)
                else:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          text="Заявка не создана. Обратитесь в ИТ-отдел.", reply_markup=None)
                execute_on_exit(call.message)
            elif call.data == 'key_cancel' or call.data == 'key_exitbot':
                if ticket_dict[call.message.chat.id].name == '':
                    bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                else:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          text="Заявка отменена", reply_markup=None)
                execute_on_exit(call.message)
            elif call.data == 'key_1c':
                set_ticket_name_from_key(call.message.chat.id, call.message.message_id, '1C')
            elif call.data == 'key_office':
                set_ticket_name_from_key(call.message.chat.id, call.message.message_id, 'Оргтехника')
            elif call.data == 'key_support':
                set_ticket_name_from_key(call.message.chat.id, call.message.message_id, 'Тех.поддержка')
            else:
                pass
    except Exception as err:
        logger.warning('callback_inline(%s) - some errors: %s', str(call.message.chat.id), repr(err))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Что-то пошло не так. Заявка не создана. Обратитесь в IT.", reply_markup=None)
    finally:
        logger.info("the function callback_inline(call) is done for the id %s", str(call.message.chat.id))

# run bot
bot.polling(none_stop=True)

