import requests
import logging

class TgbotConnection:
    def __init__(self, token):
        self.token = token

    def apiurl(self, method):
        return 'https://api.telegram.org/bot{}/{}'.format(self.token, method)

    def makeRequest(self, reqname, **params):
        while True:
            logging.debug('>>> {}: {}'.format(reqname, params))
            response = requests.get(self.apiurl(reqname), params=params)

            response.encoding = 'utf-8'
            # version mismatches in our installs
            try:
                json = response.json()
            except TypeError:
                json = response.json
            logging.debug('<<< {}'.format(json))

            # error 502 happens sometimes
            if json is None:
                continue

            if not json['ok']:
                if json.get('description') == 'Error: PEER_ID_INVALID':
                    # happens for sendMessage sometimes. FIXME: what makes the peer invalid?
                    # return value can be ignored here for now
                    logging.error('FIXME: what is this?')
                    return
                if json.get('description') == 'Error: Bot was kicked from a chat':
                    logging.warning('FIXME: handle this somehow?')
                    return
                raise RuntimeError('Bad request, response: {}'.format(json))
            return json['result']

    def getMe(self):
        return self.makeRequest('getMe')

    def getUpdates(self, offset=None, limit=None, timeout=None):
        return self.makeRequest('getUpdates', offset=offset, limit=limit, timeout=timeout)

    def sendMessage(self, chat_id, text):
        return self.makeRequest('sendMessage', chat_id=chat_id, text=text)
