import requests
import logging

class Tgbot:
    def __init__(self, token):
        self.token = token

    def apiurl(self, method):
        return 'https://api.telegram.org/bot{}/{}'.format(self.token, method)

    def makeRequest(self, reqname, **params):
        logging.debug('>>> {}: {}'.format(reqname, params))
        json = requests.get(self.apiurl(reqname), params=params).json()
        logging.debug('<<< {}'.format(json))
        if not json['ok']:
            raise RuntimeError('Bad request, response: {}'.format(json))
        return json['result']

    def getMe(self):
        return self.makeRequest('getMe')

    def getUpdates(self, offset=None, limit=None, timeout=None):
        return self.makeRequest('getUpdates', offset=offset, limit=limit, timeout=timeout)

    def sendMessage(self, chat_id, text):
        return self.makeRequest('sendMessage', chat_id=chat_id, text=text)
