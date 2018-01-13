# cut-paste this into askibot.py

def rm():
    chan_id = "-1001073076035"
    qs = Quotes(QUOTES_DIR)
    l = qs._listQuotes(chan_id)
    print(l[-2])
    del(l[-2])
    with open('%s/%s' % (QUOTES_DIR, chan_id), 'wb') as fh:
        pickle.dump(l, fh)

if __name__ == '__main__':
    rm()
