import requests
import logging

class TgbotConnection:
    REQUEST_TIMEOUT = 30
    def __init__(self, token):
        self.token = token

    def apiurl(self, method):
        return 'https://api.telegram.org/bot{}/{}'.format(self.token, method)

    def makeRequest(self, reqname, **params):
        retries = 0
        while True:
            retries += 1
            logging.debug('>>> {}: {}'.format(reqname, params))
            try:
                response = requests.get(self.apiurl(reqname),
                        params=params, timeout=self.REQUEST_TIMEOUT)
            except requests.exceptions.ConnectionError as ex:
                logging.warning('Connection error ({}) for  {} (try #{}), params: {}'.format(
                    ex, reqname, retries, params))
                continue
            except requests.exceptions.Timeout: # XXX install newer version
                logging.warning('Timed out {} (try #{}), params: {}'.format(
                    reqname, retries, params))
                continue
            except requests.exceptions.ConnectTimeout: # XXX install newer version
                logging.warning('Timed out {} (try #{}), params: {}'.format(
                    reqname, retries, params))
                continue

            response.encoding = 'utf-8'
            # version mismatches in our installs
            try:
                json = response.json()
            except TypeError:
                json = response.json
            logging.debug('<<< {}'.format(json))

            # error 502 happens sometimes
            if json is None:
                logging.warning('none json response for {} (try #{})'.format(
                    reqname, retries))
                continue

            if not json['ok']:
                if json.get('description') == 'Error: PEER_ID_INVALID': # (FIXME: is this old format? the next one seems o be used, hmm?)
                    # happens for sendMessage sometimes. FIXME: what makes the peer invalid?
                    # return value can be ignored here for now
                    logging.error('FIXME: what is this?')
                    return
                if json.get('description') == '[Error]: PEER_ID_INVALID':
                    # happens for sendMessage sometimes. FIXME: what makes the peer invalid?
                    # return value can be ignored here for now
                    logging.error('FIXME: what is this?')
                    return
                if json.get('description') == '[Error]: Bad Request: message not found':
                    # got this for cmdQuote self.conn.forwardMessage(target, response.adder['id'], response.msgid)
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

    def forwardMessage(self, chat_id, from_id, msg_id):
        return self.makeRequest('forwardMessage', chat_id=chat_id,
                from_chat_id=from_id, message_id=msg_id)
