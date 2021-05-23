#!/usr/bin/env python3

import os
import random
import requests
import telebot
from telebot import types
import glpidb
import glpiapi


# bot token from @BotFather
bot_token = '148967522:SKLJFrz8kRS1Y_5XXtrVMtTeh_NK7X8Dhw'
url_glpi = 'https://glpi.mydomen.ru/apirest.php/'

# relative path for files
file_path_dl = 'images'

auth_dict = dict()
ticket_dict = dict()

bot = telebot.TeleBot(bot_token)


@bot.message_handler(commands=['stop'])
def exitmsg(message):
    bot.send_message(message.chat.id, "До новых встреч")
    try:
        for filename in ticket_dict[message.chat.id].ticket_attachment:
            if os.path.exists(file_path_dl+'/'+filename):
                os.remove(file_path_dl+'/'+filename)
        ticket_dict.pop(message.chat.id)
        auth_dict.pop(message.chat.id)
    except:
        print('Ошибка очистки словарей')

@bot.message_handler(commands=['start'])
def welcome(message):
    # Registration
    reply_markup = types.ReplyKeyboardMarkup(row_width=1)
    item = types.KeyboardButton("Авторизация", request_contact=True)
    reply_markup.add(item)
    bot.send_message(chat_id=message.chat.id, text=f"Необходимо авторизоваться.\nНажмите <b>Авторизация</b>",
                     parse_mode='html', reply_markup=reply_markup)
    auth_dict[message.chat.id] = False

@bot.message_handler(content_types=['contact'])
def read_contact_phone(message):
    phone = message.contact.phone_number
    if phone[0] != '+':
        phone = '+'+phone
    # Get user's credentials and continue if phone number contains in DB, else send /stop command
    user_credentials = glpidb.get_user_credentials(phone)   # dictionary 'user_token' 'id' 'firstname'
    if len(user_credentials) != 0 and len(user_credentials['user_token']) != 0:
        auth_dict[message.chat.id] = True
        ticket_dict[message.chat.id] = glpiapi.Ticket()
        ticket_dict[message.chat.id].url = url_glpi
        ticket_dict[message.chat.id].user_id = user_credentials['id']
        ticket_dict[message.chat.id].user_token = user_credentials['user_token']

        item_remove = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id,  f"Добро пожаловать, {user_credentials['firstname']}!",
                         reply_markup=item_remove)
        bot.send_message(message.chat.id, f"Я - бот, с моей помощью можно создать заявку в отдел ИТ.",
                         parse_mode='html', reply_markup=None)
        markup = types.InlineKeyboardMarkup(row_width=2)
        item1 = types.InlineKeyboardButton("Выход", callback_data='exitbot')
        item2 = types.InlineKeyboardButton("Новая заявка", callback_data='newitem')
        markup.add(item1, item2)

        bot.send_message(message.chat.id, "Нажмите <b>Новая заявка</b> для выбора темы обращения или введите сами.",
                         parse_mode='html', reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "К сожалению мы не смоги Вас авторизовать. Обратитесь в IT-отдел.",
                         reply_markup=None)
        exitmsg(message)

@bot.message_handler(content_types=['text', 'photo', 'document'])
def item(message):
    if message.chat.type == 'private':
        try:
            if auth_dict[message.chat.id]:
                if message.content_type == 'text':
                    if ticket_dict[message.chat.id].ticket_name == '':
                        ticket_dict[message.chat.id].ticket_name = message.html_text
                    else:
                        ticket_dict[message.chat.id].ticket_content += message.html_text + ' '
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
                item1 = types.InlineKeyboardButton("Дополнить", callback_data='continue')
                item2 = types.InlineKeyboardButton("Отправить", callback_data='send')
                item3 = types.InlineKeyboardButton("Отменить", callback_data='cancel')
                markup.add(item1, item2, item3)
                bot.send_message(message.chat.id,"Вы можете дополнить заявку фото или текстовым сообщением либо завершить",
                                 parse_mode='html', reply_markup=markup)
        except Exception as e:
            # bot.send_message(message.chat.id, "Вы не можете сделать заявку без авторизации.", reply_markup=None)
            print(repr(e))
            exitmsg(message)

def download_file(file_info, message):
    file = requests.get('https://api.telegram.org/file/bot{0}/{1}'.format(bot_token, file_info.file_path))
    # random part of filename
    file_add = str(random.randint(0, 1000))
    # get extention from file_path
    file_ext = file_info.file_path[file_info.file_path.rfind('.') + 1:]
    filename = f'{message.chat.id}_{file_add}.{file_ext}'
    with open(file_path_dl+'/'+filename, 'wb') as new_file:
        new_file.write(file.content)
    # add filename to class
    ticket_dict[message.chat.id].ticket_attachment.append(filename)
    # ticket_dict[message.chat.id].print_ticket()

# Pushing inline keyboard
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    try:
        if call.message:
            if call.data == 'newitem':
                markup = types.InlineKeyboardMarkup(row_width=3)
                item1 = types.InlineKeyboardButton("1С", callback_data='name_1c')
                item2 = types.InlineKeyboardButton("Оргтехника", callback_data='name_office')
                item3 = types.InlineKeyboardButton("Тех.поддержка", callback_data='name_support')
                markup.add(item1, item2, item3)
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Выберите категорию", reply_markup=markup)
                # print(call.message.chat.id)
                #call.from_user.id
            elif call.data == 'continue':
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Опишите проблему или сделайте фото...", reply_markup=None)
            elif call.data == 'send':
                # create ticket
                ticket_id = ticket_dict[call.message.chat.id].create_ticket()
                # upload files/hotos to glpi
                for filename in ticket_dict[call.message.chat.id].ticket_attachment:
                    doc_id = ticket_dict[call.message.chat.id].upload_doc(file_path_dl, filename)
                    if doc_id != None:
                        # update table glpi_documents_items
                        glpidb.update_doc_item(doc_id, ticket_dict[call.message.chat.id].ticket_id,
                                               ticket_dict[call.message.chat.id].user_id)
                if ticket_id != None:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          text="Заявка №" + str(ticket_id) + " успешно оформлена", reply_markup=None)
                    # bot.send_message(call.message.chat.id, "https://support.acticomp.ru/front/ticket.form.php?id=" +
                    #                  str(ticket_id), parse_mode='html', reply_markup=None)
                else:
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          text="Что-то пошло не так. Обратитесь в ИТ-отдел.", reply_markup=None)
                exitmsg(call.message)
            elif call.data == 'cancel' or call.data == 'exitbot':
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Заявка отменена", reply_markup=None)
                exitmsg(call.message)
            elif call.data == 'name_1c':
                ticket_dict[call.message.chat.id].ticket_name = '1С (из Telegram)'
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Категория: 1С", reply_markup=None)
                bot.send_message(call.message.chat.id, "Опишите проблему или сделайте фото", reply_markup=None)
            elif call.data == 'name_office':
                ticket_dict[call.message.chat.id].ticket_name = 'Оргехника (из Telegram)'
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Категория: Оргтехника", reply_markup=None)
                bot.send_message(call.message.chat.id, "Опишите проблему или сделайте фото", reply_markup=None)
            elif call.data == 'name_support':
                ticket_dict[call.message.chat.id].ticket_name = 'Тех.поддержка (из Telegram)'
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Категория: Тех.поддержка", reply_markup=None)
                bot.send_message(call.message.chat.id, "Опишите проблему или сделайте фото", reply_markup=None)
            else:
                # bot.send_message(call.message.chat.id, "Не знаю что ответить =(...")
                a=1

            # show alert
            # bot.answer_callback_query(callback_query_id=call.id, show_alert=False,
            #                           text="ЭТО ТЕСТОВОЕ УВЕДОМЛЕНИЕ!!11")
        # ticket_dict[call.message.chat.id].print_ticket()
    except Exception as e:
        print(repr(e))

# run bot
bot.polling(none_stop=True)

