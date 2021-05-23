import datetime
import requests
import json


class Ticket:
    def __init__(self, url = None, user_id=None, user_token=None, ticket_id=None, ticket_name='', ticket_content='',
                 ticket_attachment=[]):
        self.url = url
        self.user_id  = user_id
        self.user_token = user_token
        self.ticket_id = ticket_id
        self.ticket_name = ticket_name
        self.ticket_content = ticket_content
        self.ticket_attachment = ticket_attachment

    def print_ticket(self):
        print(f'url: {self.url}, user_id: {self.user_id}; user_token: {self.user_token}; '
              f'ticket_name: {self.ticket_name}; ticket_content: {self.ticket_content}; '
              f'ticket_attachment: {self.ticket_attachment}')

    @staticmethod
    def get_session_token(url, user_token):
        '''
        :param url: glpi url with end of "/"
        :param tokenAPI: Token API from gpli user profile
        :return: request a session token to uses other API endpoints
        '''
        headers = {
            "Content-Type": "application/json",
            "Authorization": "user_token " + user_token
        }
        response = requests.get(url+"initSession", headers=headers)
        res = json.loads(response.text)
        return res.get('session_token')

    @staticmethod
    def close_session(url, session_token):
        '''
        :param url: glpi url with end of "/"
        :param session_token: session token
        :return: destroy a session identified by a session token
        '''
        headers = {
            'Content-Type': 'application/json',
            'Session-Token': session_token,
        }
        response = requests.get(url+"killSession", headers=headers)

    def create_ticket(self):    #, url, user_token, session_token, name, content):
        '''
        :param url: glpi url with end of "/"
        :param tokenAPI: Token API from gpli user profile
        :param session_token: session token
        :param name: ticket's title
        :param content: ticket's description
        :return: ticket_id
        '''
        if self.ticket_id == None:
            session_token = self.get_session_token(self.url, self.user_token)
            headers = {
                "Content-Type": "application/json",
                "Authorization": "user_token " + self.user_token,
                "Session-Token": session_token
            }
            if self.ticket_content == '':
                self.ticket_content = self.ticket_name
            if self.ticket_name.find('(из Telegram)') == -1:
                self.ticket_name += '(из Telegram)'
            time_to_resolve = str(datetime.datetime.today().date() + datetime.timedelta(5)) + ' 12:00:00'
            msg = '{"input": {"name": "'+self.ticket_name+'", "content": "'+self.ticket_content+'", "time_to_resolve":"'+\
                  time_to_resolve +'", "type": "1", "requesttypes_id": "8"}}'
            response = requests.post(self.url+"Ticket", headers=headers, data=msg.encode('utf-8'))
            if response.status_code == 201:
                self.ticket_id = json.loads(response.text).get('id')

            self.close_session(self.url, session_token)

        return self.ticket_id

    def upload_doc(self, file_path, filename):   # (url, session_token, ticket_id, filename):
        '''
        :param url: glpi url with end of "/"
        :param session_token: session token
        :param ticket_id:
        :param filename:
        :return: noting
        '''
        session_token = self.get_session_token(self.url, self.user_token)

        headers={'Session-Token': session_token,}
        files = {
            'uploadManifest': (None, '{"input": {"name": "Документ заявки '+str(self.ticket_id)+' (tb)", "_filename": ["'+filename+'"]}}',
                               'application/json'),
            'filename[0]': (filename, open(file_path+'/'+filename, "rb")),
        }
        response = requests.post(self.url+"Document", headers=headers, files=files)
        if response.status_code == 201:
            doc_id = response.json().get('id')
        else:
            doc_id = None

        self.close_session(self.url, session_token)

        return doc_id

def get_info_ticket(url, session_token, ticket_id):
    '''
    for debag uses
    :param url: glpi url with end of "/"
    :param session_token: session token
    :param ticket_id: ticket's id
    :return: ticket's fields
    '''
    headers = {
        'Content-Type': 'application/json',
        'Session-Token': session_token,
    }
    # response = requests.get(url+"Ticket/1561?expand_dropdowns=true", headers=headers)
    response = requests.get(f"https://support.acticomp.ru/apirest.php/Ticket/{ticket_id}/Document_Item/", headers=headers)
    return response.text

def get_info_user(url, session_token, user_id):
    '''
    for debug uses
    :param url: glpi url with end of "/"
    :param session_token: session token
    :param user_id: user's id
    :return: user's fields
    '''
    headers = {
        'Content-Type': 'application/json',
        'Session-Token': session_token,
    }
    #"https://support.acticomp.ru/apirest.php/User/325"
    response = requests.get(url+"User/"+str(user_id), headers=headers)
    print(response.text)

if __name__ == '__main__':
    print('glpiapi module')
    # TOKEN_user_API = 'PG2HbajQdHVEOSXq9ag1'
    # url_glpi = 'https://support.acticomp.ru/apirest.php/'
    # session_token = get_session_token(url_glpi, TOKEN_user_API)
    # ticket_id = 1574    #create_ticket(url_glpi, TOKEN_user_API, session_token)
    #get_info_ticket(url_glpi, session_token, 1541)
    # filename = "1.JPG"
    # file_id = upload_doc(url_glpi, session_token, ticket_id, filename)
    # print(file_id)

    #get_info_user(url_glpi, session_token, user_id)
    # upd = update_ticket()
    # print(upd)
    #get_info_ticket(url_glpi, session_token, ticket_id)
    # close_session(url_glpi, session_token)
