import os
import random
import logging
from aiogram import Bot, Dispatcher, executor, types
from dotenv import load_dotenv
import glpidb
import glpiapi


# logging
logging.basicConfig(level=logging.WARNING, filename='glpibot.log',
                    format='%(asctime)s %(name)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Credentials
load_dotenv('.env')

# bot token from @BotFather
BOT_TOKEN = os.getenv('BOT_TOKEN')
URL_GLPI = os.getenv('URL_GLPI')

# relative path for files
FILE_PATH = os.getenv('FILE_PATH')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Dicts for each message.chat.id (for each user)
user_dict = dict()
ticket_dict = dict()
glpi_dict = dict()
msgid_dict = {"": []}

# Keyboards
def make_keyboard_inline(row_width, **bottons):
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

async def delete_inline_keyboard(chat_id):
    '''
    Delete message with inline keyboard
    '''
    if len(msgid_dict[chat_id]) > 0:
        for i in range(len(msgid_dict[chat_id])):
            del_msg_id = msgid_dict[chat_id].pop()
            await bot.delete_message(chat_id=chat_id, message_id=del_msg_id)

async def select_title(message):
    '''
    Select title and get message.chat.id
    '''
    markup = make_keyboard_inline(3, key_exitbot="Выход", key_newitem="Заявка в ИТ", key_instructions="Инструкции")
    title_msg = await bot.send_message(chat_id=message.chat.id, text="Выберите тему обращения:", reply_markup=markup)
    msgid_dict[message.chat.id].append(title_msg.message_id)

def set_ticket_name_or_content(message, text):
    '''
    Setting ticket name or content depending on ticket name
    '''
    if ticket_dict[message.chat.id].name == '':
        ticket_dict[message.chat.id].name = text
    else:
        ticket_dict[message.chat.id].content += text + ', '

async def set_ticket_name_from_key(chat_id, message_id, name):
    '''
    Adding "(из Telegram)" to ticket_name and show message with the selected category
    '''
    ticket_dict[chat_id].ticket_name = f'{name} (из Telegram)'
    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                          text=f'Категория: {name}', reply_markup=None)
    await bot.send_message(chat_id, text="Опишите проблему, сделайте фото или видео", reply_markup=None)

@dp.message_handler(commands=['stop'])
async def execute_on_exit(message: types.Message):
    await bot.send_message(chat_id=message.chat.id, text="До новых встреч")
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

@dp.message_handler(commands=['start'])
async def welcome(message: types.Message):
    # Registration
    keyboard_send_phone = types.ReplyKeyboardMarkup(row_width=3)
    botton_auth = types.KeyboardButton("Отправить номер", request_contact=True)
    keyboard_send_phone.add(botton_auth)
    await bot.send_message(chat_id=message.chat.id, text=f"Для авторизации необходим номер телефона.\nНажмите <b>" + \
                            "Отправить номер</b>\n\nОтправляя свой номер телефона Вы даете согласие на обработку " + \
                            "персональных данных (ФИО, номер телефона) в целях работы с информационной системой",
                     parse_mode='html', reply_markup=keyboard_send_phone)

@dp.message_handler(content_types=['contact'])
async def read_contact_phone(message: types.Message):
    phone = message.contact.phone_number
    if phone[0] != '+':
        phone = '+' + phone
    # Get user's credentials and continue if phone number contains in DB, else send /stop command
    user_credentials = glpidb.get_user_credentials(phone)  # dictionary with keys 'user_token' 'id' 'firstname'
    if user_credentials and user_credentials['user_token']:
        user_dict[message.chat.id] = glpiapi.User(id=user_credentials['id'], token=user_credentials['user_token'])
        # Get user session
        glpi_dict[message.chat.id] = glpiapi.GLPI(URL_GLPI, user=user_dict[message.chat.id])
        # Create empty ticket
        ticket_dict[message.chat.id] = glpiapi.Ticket()
        msgid_dict[message.chat.id] = [message.message_id]

        item_remove = types.ReplyKeyboardRemove()
        await bot.send_message(chat_id=message.chat.id, text=f"Добро пожаловать, {user_credentials['firstname']}!",
                               reply_markup=item_remove)
        await bot.send_message(chat_id=message.chat.id, text=f"Я - бот компании Активный компонент. Со мной можно получить помощь ИТ отдела.",
                               reply_markup=None)
        await select_title(message)
    else:
        await bot.send_message(chat_id=message.chat.id, text="К сожалению мы не смоги Вас авторизовать. Заполните в системе поля " + \
                               "Мобильный телефон и Токен API или обратитесь в IT-отдел.", reply_markup=None)
        logger.warning('read_contact_phone(message) Authorisation Error for id %s and phone %s',
                       str(message.chat.id), phone)
        await execute_on_exit(message)

@dp.message_handler(content_types=['text', 'photo', 'video', 'document'])
async def get_data(message: types.Message):
    if message.chat.type == 'private':
        try:
            if ticket_dict[message.chat.id].isnew:
                if message.caption is not None:
                    set_ticket_name_or_content(message, message.caption)
                if message.content_type == 'text':
                    # Delete message with inline keyboard
                    await delete_inline_keyboard(message.chat.id)
                    set_ticket_name_or_content(message, message.text)
                elif message.content_type == 'document':
                    filename = f"{message.chat.id}_{str(random.randint(0, 1000))}_{message.document.file_name}"
                    await message.document.download(f"./{FILE_PATH}/{filename}")
                    ticket_dict[message.chat.id].attachment.append(filename)
                elif message.content_type == 'photo':
                    photo = message.photo.pop()
                    filename = f"{message.chat.id}_{str(random.randint(0, 1000))}.jpg"
                    await photo.download(f"./{FILE_PATH}/{filename}")
                    ticket_dict[message.chat.id].attachment.append(filename)
                elif message.content_type == 'video':
                    filename = f"{message.chat.id}_{str(random.randint(0, 1000))}.mp4"
                    await message.video.download(f"./{FILE_PATH}/{filename}")
                    ticket_dict[message.chat.id].attachment.append(filename)
                else:
                    pass
                markup = make_keyboard_inline(3, key_continue="Дополнить", key_send="Отправить в ИТ",
                                              key_cancel="Отменить")
                get_data_msg = await bot.send_message(chat_id=message.chat.id, text="Вы можете дополнить заявку фото, видео или " + \
                                       "текстовым сообщением либо завершить", parse_mode='html',
                                       reply_markup=markup)
                msgid_dict[message.chat.id].append(get_data_msg.message_id)
            else:
                if len(msgid_dict[message.chat.id]) > 0:
                    delmsgid = msgid_dict[message.chat.id].pop()
                    await bot.delete_message(chat_id=message.chat.id, message_id=delmsgid)
                await bot.send_message(chat_id=message.chat.id, text="Используйте, пожалуйста, кнопки.", parse_mode='html',
                                       reply_markup=None)
                await select_title(message)
        except Exception as err:
            await bot.send_message(chat_id=message.chat.id, text="Что-то пошло не так. Обратитесь в IT.",
                                   parse_mode='html', reply_markup=None)
            # Delete message with inline keybaord
            if len(msgid_dict[message.chat.id]) > 0:
                delmsgid = msgid_dict[message.chat.id].pop()
                await bot.delete_message(chat_id=message.chat.id, message_id=delmsgid)
            logger.warning('get_data(%s) - some errors: %s', str(message.chat.id), repr(err))
            await execute_on_exit(message)
        finally:
            logger.info("the function get_data(message) is done for the id %s", str(message.chat.id))

# Pushing inline keyboard
@dp.callback_query_handler(lambda callback_query:True)
async def callback_inline_keyboard(call):
    try:
        if call.message:
            if call.data == 'key_newitem':
                ticket_dict[call.message.chat.id].isnew = True
                markup = make_keyboard_inline(2, key_1c="1С", key_office="Оргтехника в ИТ", key_support="поддержка")
                callback_msg = await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                                text="Выберите категорию:", reply_markup=markup)
            if call.data == 'key_instructions':
                markup = make_keyboard_inline(3, key_guest_wifi="Пароль Wi-Fi", key_VCC="Видеосвязь в ИТ",
                                              key_url_support="Система", key_url_docs="Другие инструкции")
                await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Выберите инструкцию:", reply_markup=markup)
            if call.data == 'key_guest_wifi':
                await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=f"Имя WiFi:  <b>{os.getenv('GUEST_SSID')}</b>\nПароль:  <b>{os.getenv('GUEST_PASS')}</b>",
                                      parse_mode='html', reply_markup=None)
                await select_title(call.message)
            if call.data == 'key_VCC':
                await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=f"Видеоконференцсвязь: \n\n{os.getenv('VCC_1')}\n\n{os.getenv('VCC_2')}\n\n{os.getenv('VCC_3')}\n\n{os.getenv('VCC_4')}\n\n{os.getenv('VCC_5')}\n",
                                      parse_mode='html', reply_markup=None)
                await select_title(call.message)
            if call.data == 'key_url_support':
                await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=f"Инструкция по входу в GLPI\n{os.getenv('URL_SUPPORT')}", reply_markup=None)
                await select_title(call.message)
            if call.data == 'key_url_docs':
                await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text=f"Другие инструкции\n{os.getenv('URL_DOCS')}", reply_markup=None)
                await select_title(call.message)
            elif call.data == 'key_continue':
                await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Опишите проблему, сделайте фото или видео...", reply_markup=None)
            elif call.data == 'key_send':
                # Delete message with inline keyboard
                await delete_inline_keyboard(call.message.chat.id)
                await bot.send_chat_action(chat_id=call.message.chat.id, action='upload_document')
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
                    await bot.send_message(chat_id=call.message.chat.id,
                                          text="Заявка №" + str(ticket_id) + " успешно оформлена", reply_markup=None)
                else:
                    await bot.send_message(chat_id=call.message.chat.id,
                                          text="Заявка не создана. Обратитесь в ИТ-отдел.", reply_markup=None)
                await execute_on_exit(call.message)
            elif call.data == 'key_cancel' or call.data == 'key_exitbot':
                if ticket_dict[call.message.chat.id].name == '':
                    await bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                else:
                    await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          text="Заявка отменена", reply_markup=None)
                await execute_on_exit(call.message)
            elif call.data == 'key_1c':
                await set_ticket_name_from_key(call.message.chat.id, call.message.message_id, '1C')
            elif call.data == 'key_office':
                await set_ticket_name_from_key(call.message.chat.id, call.message.message_id, 'Оргтехника')
            elif call.data == 'key_support':
                await set_ticket_name_from_key(call.message.chat.id, call.message.message_id, 'Тех.поддержка')
            else:
                pass
    except Exception as err:
        logger.warning('callback_inline(%s) - some errors: %s', str(call.message.chat.id), repr(err))
        await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Что-то пошло не так. Заявка не создана. Обратитесь в IT.", reply_markup=None)
        await execute_on_exit(call.message)
    finally:
        logger.info("the function callback_inline(call) is done for the id %s", str(call.message.chat.id))

if __name__ == "__main__":
    # run bot
    executor.start_polling(dp, skip_updates=True)

