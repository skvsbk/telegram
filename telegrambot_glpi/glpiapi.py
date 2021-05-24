import datetime
import requests
import json


class User:
    def __init__(self, id=None, token=None):
        self.id  = id
        self.token = token

    def print_user(self):
        print(f'user_id: {self.id}; user_token: {self.token}')

class Ticket:
    def __init__(self, id=None, name='', content='', attachment=[]):
        self.id = id
        self.name = name
        self.content = content
        self.attachment = attachment

    def print_ticket(self):
        print(f'ticket_id: {self.id}; ticket_name: {self.name}; ticket_content: {self.content}; ticket_attachment: {self.attachment}')

class GLPI:
    def __init__(self, url = None, user=None, ticket=None):
        self.url = url
        self.user  = user
        self.ticket = ticket
        headers = {
            "Content-Type": "application/json",
            "Authorization": "user_token " + self.user.token
        }
        response = requests.get(self.url+"initSession", headers=headers)
        self.session = json.loads(response.text).get('session_token')

    def __del__(self):
        '''
        :return: kill user session when destroy object
        '''
        headers = {
            'Content-Type': 'application/json',
            'Session-Token': self.session,
        }
        requests.get(self.url+"killSession", headers=headers)

    def create_ticket(self):
        '''
        :return: ticket_id
        '''
        if self.ticket.id == None:
            headers = {
                "Content-Type": "application/json",
                "Authorization": "user_token " + self.user.token,
                "Session-Token": self.session
            }
            if self.ticket.content == '':
                self.ticket.content = self.ticket.name
            if self.ticket.name.find('(из Telegram)') == -1:
                self.ticket.name += '(из Telegram)'
            time_to_resolve = str(datetime.datetime.today().date() + datetime.timedelta(5)) + ' 12:00:00'
            msg = '{"input": {"name": "'+self.ticket.name+'", "content": "'+self.ticket.content+'", "time_to_resolve":"'+\
                  time_to_resolve +'", "type": "1", "requesttypes_id": "8"}}'
            response = requests.post(self.url+"Ticket", headers=headers, data=msg.encode('utf-8'))
            if response.status_code == 201:
                self.ticket.id = json.loads(response.text).get('id')

        return self.ticket.id

    def upload_doc(self, file_path, filename):
        '''
        :param file_path: path to downloaded files
        :param filename: from ticket.attachment
        :return: noting
        '''
        headers={'Session-Token': self.session,}
        files = {
            'uploadManifest': (None, '{"input": {"name": "Документ заявки '+str(self.ticket.id)+' (tb)", "_filename": ["'+filename+'"]}}',
                               'application/json'),
            'filename[0]': (filename, open(file_path+'/'+filename, "rb")),
        }
        response = requests.post(self.url+"Document", headers=headers, files=files)
        if response.status_code == 201:
            doc_id = response.json().get('id')
        else:
            doc_id = None

        return doc_id


if __name__ == '__main__':
    print('glpiapi module')

    user = User(id='325', token='PG2HbajQdHVEOSXq9ag1uVKPFcwxLGEKPOoXf7Jd')

    glpiAPI = GLPI(url='https://support.acticomp.ru/apirest.php/', user=user)

    ticket = Ticket(name='test', content='test test')

    glpiAPI.ticket = ticket
    ticket_id = glpiAPI.create_ticket()
    ticket.id = ticket_id
    print(ticket_id)

    ticket.attachment.append('2.jpg')
    glpiAPI.upload_doc(file_path='images', filename='2.jpg')
    user.print_user()
    ticket.print_ticket()

    # kill objects
    glpiAPI = ''
    user = ''
    ticket = ''