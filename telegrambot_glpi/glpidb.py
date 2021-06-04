import os
import datetime
import logging
import pymysql
from dotenv import load_dotenv


# logging
logging.basicConfig(level=logging.WARNING, filename='glpibot.log', format='%(asctime)s %(name)s %(levelname)s:%(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Credentials
load_dotenv('.env')

def db_connetion():
    # DB credentials
    DB_HOST = os.getenv('DB_HOST')
    DB_NAME = os.getenv('DB_NAME')
    DB_USER = os.getenv('DB_USER')
    DB_PASS = os.getenv('DB_PASS')

    # Connect to DB
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        db=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor)

def get_user_credentials(mobile):
    '''
    :param mobile: search creteria
    :return: dictionary with user params
    '''
    connection = db_connetion()
    user_dict = dict()
    try:
        with connection.cursor() as cursor:
            query = "SELECT id, api_token, firstname FROM glpi_users WHERE mobile = '" + mobile + "'"
            cursor.execute(query)
            for row in cursor:
                user_dict['user_token'] = row['api_token']
                user_dict['id'] = row['id']
                user_dict['firstname'] = row['firstname']
    except:
        logger.warning('get_user_credentials(mobile) - error getting user_id for %s', str(mobile))
    finally:
        logger.info('the function get_user_credentials(mobile) is done for the mobile %s', str(mobile))
        connection.close()

    return user_dict

def get_max_id(connection):
    '''
    :return: max id from table glpi_documents_items for use it as tab_id in update_doc_item
    '''
    # connection = db_connetion()
    try:
        with connection.cursor() as cursor:
            query = "SELECT MAX(id) FROM glpi_documents_items"
            cursor.execute(query)
            for row in cursor:
                max_id = row['MAX(id)']
    except:
        logger.warning('get_max_id(connection) - error getting max_id')
    finally:
        logger.info('the function get_max_id(connection) is done')
        connection.close()

    return max_id

def update_doc_item(documents_id, items_id, user_id):
    '''
    :param tab_id: glpi_documents_items max id got by get_max_id()
    :param documents_id: id uploaded image
    :param items_id: ticket id
    :param user_id: user id from get_user_credentials(mobile)
    :return:
    '''
    connection = db_connetion()
    try:
        with connection.cursor() as cursor:
            # get max id
            query = "SELECT MAX(id) FROM glpi_documents_items"
            cursor.execute(query)
            for row in cursor:
                max_id = row['MAX(id)']
            tab_id = max_id+1

            # update glpi_documents_items
            date_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            columns = 'id, documents_id, items_id, itemtype, entities_id, is_recursive, date_mod, users_id, timeline_position, date_creation'
            values = [(tab_id, documents_id, items_id, 'Ticket', 0, 1, f'{date_time}', user_id, 1, f'{date_time}')]
            query = f"INSERT INTO glpi_documents_items({columns}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            cursor.executemany(query, values)
            connection.commit()
    except:
        logger.warning('update_doc_item(connection) - error updating item_id %s', items_id)
    finally:
        logger.info('the update_doc_item(connection) is done for item_id %s', items_id)
        connection.close()

if __name__ == '__main__':
    print('glpidb module')
    connection = db_connetion()
    max_id = get_max_id(connection)
    print(max_id)
    mobile = '+79110872875'
    user = get_user_credentials(mobile)
    print(user['id'])
    print(user['user_token'])
    print(user['firstname'])
    #
    # update_doc_item(max_id+1, 678, 1574, user['id'])