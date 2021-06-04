import os
import random
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

# Dicts for each message.chat.id (for each user)
user_dict = dict()
ticket_dict = dict()
glpi_dict = dict()
msgid_dict = {"": []}

bot = telebot.TeleBot(BOT_TOKEN)

def start_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=3)
    item1 = types.InlineKeyboardButton("Выход", callback_data='key_exitbot')
    item2 = types.InlineKeyboardButton("Заявка в ИТ", callback_data='key_newitem')
    item3 = types.InlineKeyboardButton("Инструкции", callback_data='key_instructions')

    markup.add(item1, item2, item3)
    send_id = bot.send_message(message.chat.id, "Выберите тему обращения:", reply_markup=markup)
    msgid_dict[message.chat.id].append(send_id.id)

@bot.message_handler(commands=['stop'])
def exitmsg(message):
    bot.send_message(message.chat.id, "До новых встреч")
    try:
        for filename in ticket_dict[message.chat.id].attachment:
            if os.path.exists(FILE_PATH + '/' + filename):
                os.remove(FILE_PATH + '/' + filename)
        user_dict.pop(message.chat.id)
        glpi_dict.pop(message.chat.id)
        ticket_dict.pop(message.chat.id)
        msgid_dict.pop(message.chat.id)
    except:
        logger.warning('exitmsg(%s) - error cleaning dictionaries', str(message.chat.id))
    finally:
        logger.info('the function exitmsg(message) is done for the id %s', str(message.chat.id))

@bot.message_handler(commands=['start'])
def welcome(message):
    # Registration
    reply_markup = types.ReplyKeyboardMarkup(row_width=3)
    item = types.KeyboardButton("Отправить номер", request_contact=True)
    reply_markup.add(item)
    bot.send_message(chat_id=message.chat.id, text=f"Для авторизации необходим номер телефона.\nНажмите <b>Отправить номер</b>\n\nОтправляя свой номер телефона Вы даете согласие на обработку персональных данных (ФИО, номер телефона) в целях работы с информационной системой",
                     parse_mode='html', reply_markup=reply_markup)

@bot.message_handler(content_types=['contact'])
def read_contact_phone(message):
    phone = message.contact.phone_number
    if phone[0] != '+':
        phone = '+'+phone
    # Get user's credentials and continue if phone number contains in DB, else send /stop command
    user_credentials = glpidb.get_user_credentials(phone)   # dictionary 'user_token' 'id' 'firstname'
    if len(user_credentials) != 0 and len(user_credentials['user_token']) != 0:
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
        start_menu(message)
    else:
        bot.send_message(message.chat.id, "К сожалению мы не смоги Вас авторизовать. Обратитесь в IT-отдел.",
                         reply_markup=None)
        logger.warning('read_contact_phone(message) Authorisation Error for id %s and phone %s', str(message.chat.id), phone)
        exitmsg(message)

@bot.message_handler(content_types=['text', 'photo', 'document'])
def item(message):
    if message.chat.type == 'private':
        try:
            if glpi_dict[message.chat.id].session is not None:
                if ticket_dict[message.chat.id].new:
                    if message.content_type == 'text':
                        if ticket_dict[message.chat.id].name == '':
                            ticket_dict[message.chat.id].name = message.html_text
                        else:
                            ticket_dict[message.chat.id].content += message.html_text + ' '
                            # ticket_dict[message.chat.id].print_ticket()
                    elif message.content_type == 'document':
                        file_info = bot.get_file(message.document.file_id)
                        download_file(file_info, message)
                    elif message.content_type == 'photo':
                        file_info = bot.get_file(message.photo[-1].file_id)
                        download_file(file_info, message)
                    else:
                        pass
                    markup = types.InlineKeyboardMarkup(row_width=3)
                    item1 = types.InlineKeyboardButton("Дополнить", callback_data='key_continue')
                    item2 = types.InlineKeyboardButton("Отправить", callback_data='key_send')
                    item3 = types.InlineKeyboardButton("Отменить", callback_data='key_cancel')
                    markup.add(item3, item2, item1)
                    # Delete message with inline keybaord
                    delmsgid = msgid_dict[message.chat.id].pop()
                    bot.delete_message(chat_id=message.chat.id, message_id=delmsgid)
                    send_id = bot.send_message(message.chat.id,"Вы можете дополнить заявку фото или текстовым сообщением либо завершить",
                                     parse_mode='html', reply_markup=markup)
                    msgid_dict[message.chat.id].append(send_id.id)
                else:
                    delmsgid = msgid_dict[message.chat.id].pop()
                    bot.delete_message(chat_id=message.chat.id, message_id=delmsgid)
                    bot.send_message(message.chat.id,"Используйте, пожалуйста, кнопки.",
                                     parse_mode='html', reply_markup=None)
                    start_menu(message)
        except Exception as e:
            # print(repr(e))
            bot.send_message(message.chat.id, "Вероятно Вы не авторизованы. Введите /start",
                             parse_mode='html', reply_markup=None)
            logger.warning('item(%s) - some errors', str(message.chat.id))
            exitmsg(message)
        finally:
            logger.info("the function item(message) is done for the id %s", str(message.chat.id))

def download_file(file_info, message):
    try:
        file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(bot_token, file_info.file_path))
        # random part of filename
        file_add = str(random.randint(0, 1000))
        # get extention from file path
        file_ext = file_info.file_path[file_info.file_path.rfind('.') + 1:]
        filename = f'{message.chat.id}_{file_add}.{file_ext}'
        with open(FILE_PATH + '/' + filename, 'wb') as new_file:
            new_file.write(file.content)
        # add filename to class
        ticket_dict[message.chat.id].attachment.append(filename)
    except:
        logger.warning('item(%s) - some errors', str(message.chat.id))
    finally:
        logger.info("the function item(message) is done for the id %s", str(message.chat.id))

# Pushing inline keyboard
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    try:
        if call.message:
            if call.data == 'key_newitem':
                ticket_dict[call.message.chat.id].new = True
                markup = types.InlineKeyboardMarkup(row_width=2)
                item1 = types.InlineKeyboardButton("1С", callback_data='key_1c')
                item2 = types.InlineKeyboardButton("Оргтехника", callback_data='key_office')
                item3 = types.InlineKeyboardButton("Тех.поддержка", callback_data='key_support')
                markup.add(item1, item2, item3)
                send_id = bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Выберите категорию", reply_markup=markup)
                msgid_dict[call.message.chat.id].append(send_id.id)
            if call.data == 'key_instructions':
                markup = types.InlineKeyboardMarkup(row_width=2)
                item1 = types.InlineKeyboardButton("Видеосвязь", callback_data='key_VCC')
                item2 = types.InlineKeyboardButton("Система заявок", callback_data='key_url_support')
                item3 = types.InlineKeyboardButton("Пароль Wi-Fi", callback_data='key_guest_wifi')
                item4 = types.InlineKeyboardButton("Другие инструкции", callback_data='key_url_docs')
                markup.add(item3, item1, item2, item4)
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Выберите инструкцию", reply_markup=markup)
            if call.data == 'key_guest_wifi':
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=f"Имя WiFi:  <b>{os.getenv('GUEST_SSID')}</b>\nПароль:  <b>{os.getenv('GIEST_PASS')}</b>",
                                      parse_mode='html', reply_markup=None)
                start_menu(call.message)
            if call.data == 'key_VCC':
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=f"Видеоконференцсвязь: \n\n{os.getenv('VCC_1')}\n\n{os.getenv('VCC_2')}\n\n{os.getenv('VCC_3')}\n\n{os.getenv('VCC_4')}\n\n{os.getenv('VCC_5')}\n",
                                      parse_mode='html', reply_markup=None)
                start_menu(call.message)
            if call.data == 'key_url_support':
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=f"Инструкция по входу в GLPI\n{os.getenv('URL_SUPPORT')}", reply_markup=None)
                start_menu(call.message)
            if call.data == 'key_url_docs':
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=f"Другие инструкции\n{os.getenv('URL_DOCS')}", reply_markup=None)
                start_menu(call.message)
            elif call.data == 'key_continue':
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Опишите проблему или сделайте фото...", reply_markup=None)
            elif call.data == 'key_send':
                # send ticket
                glpi_dict[call.message.chat.id].ticket = ticket_dict[call.message.chat.id]
                ticket_id = glpi_dict[call.message.chat.id].create_ticket()
                ticket_dict[call.message.chat.id].id = ticket_id
                # upload files/hotos to glpi
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
                                          text="Что-то пошло не так. Обратитесь в ИТ-отдел.", reply_markup=None)
                exitmsg(call.message)
            elif call.data == 'key_cancel' or call.data == 'key_exitbot':
                if ticket_dict[call.message.chat.id].name == '':
                    bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                else:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          text="Заявка отменена", reply_markup=None)
                exitmsg(call.message)
            elif call.data == 'key_1c':
                ticket_dict[call.message.chat.id].ticket_name = '1С (из Telegram)'
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Категория: 1С", reply_markup=None)
                bot.send_message(call.message.chat.id, "Опишите проблему или сделайте фото", reply_markup=None)
            elif call.data == 'key_office':
                ticket_dict[call.message.chat.id].ticket_name = 'Оргехника (из Telegram)'
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Категория: Оргтехника", reply_markup=None)
                bot.send_message(call.message.chat.id, "Опишите проблему или сделайте фото", reply_markup=None)
            elif call.data == 'key_support':
                ticket_dict[call.message.chat.id].ticket_name = 'Тех.поддержка (из Telegram)'
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Категория: Тех.поддержка", reply_markup=None)
                bot.send_message(call.message.chat.id, "Опишите проблему или сделайте фото", reply_markup=None)
            else:
                pass
    except Exception as e:
        # print(repr(e))
        logger.warning('callback_inline(%s) - some errors', str(call.message.chat.id))
    finally:
        logger.info("the function callback_inline(call) is done for the id %s", str(call.message.chat.id))

# if __name__ == '__main__':
# run bot
bot.polling(none_stop=True)

