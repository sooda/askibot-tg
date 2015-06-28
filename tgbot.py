import requests
import logging

class Tgbot:
    def __init__(self, token):
        self.token = token

    def apiurl(self, method):
        return 'https://api.telegram.org/bot{}/{}'.format(self.token, method)

    def makerequest(self, reqname, **params):
        logging.debug('>>> {}: {}'.format(reqname, params))
        json = requests.get(self.apiurl(reqname), params=params).json()
        logging.debug('<<< {}'.format(json))
        return json

    def getMe(self):
        return self.makerequest('getMe')
