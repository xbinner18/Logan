import requests
import json
from telegram import Update, Bot
from haruka import dispatcher
from haruka.modules.disable import DisableAbleCommandHandler
from telegram.ext import run_async


@run_async
def bin(bot: Bot, update: Update):
    message = update.effective_message
    text = message.text[len('/bin '):]
    r = requests.get(f'https://lookup.binlist.net/{text}').json()
    try:
        info = f'''
*BIN:* `{text}`
*SCHEME:* {r['scheme']}
*TYPE:* {r['type']}
*BRAND:* {r['brand']}
*PREPAID:* {r['prepaid']}
*COUNTRY:* {str(r['country']['name'])}
*BANK:* {r['bank']['name']}
'''

    except KeyError:
        info = f'''
*BIN:* `{text}`
*SCHEME:* {r['scheme']}
*TYPE:* {r['type']}
*BRAND:* {r['brand']}
*COUNTRY:* {str(r['country']['name'])}
       '''
    message.reply_text(info, parse_mode='markdown')
    
    
BIN_HANDLER = DisableAbleCommandHandler("bin", bin, admin_ok=True)      
dispatcher.add_handler(BIN_HANDLER)
