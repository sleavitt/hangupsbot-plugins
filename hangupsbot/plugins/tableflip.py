import os
import re
import random
import asyncio
import aiohttp
import urllib.request

from bs4 import BeautifulSoup

import hangups

import plugins

def _initialise(bot):
    plugins.register_handler(_handle_me_action)
    plugins.register_user_command(["tableflip"])

@asyncio.coroutine
def _retrieve(url, css_selector, attribute):
    print("tableflip._retrieve(): getting {}".format(url))
    html_request = yield from aiohttp.request('get', url)
    html = yield from html_request.read()
    soup = BeautifulSoup(str(html, 'utf-8'))
    links = []
    for link in soup.select(css_selector):
        links.append(link.get(attribute))
    return links

def _handle_me_action(bot, event, command):
    if event.text.startswith('/me'):
        m = re.search('(flip(s|ped)?\s+a\s+(.*\s+)?table.*)', event.text)
        if m:
            yield from asyncio.sleep(0.2)
            yield from command.run(bot, event, *["tableflip", m.group(0)])
        else:
            pass

def tableflip(bot, event, *args):
    if (len(args) > 0):
        tableflip_text = " ".join(args)
    else:
        tableflip_text = "flipped a table"

    msg = _("{} {}").format(event.user.full_name, tableflip_text)

    meme_url = "http://knowyourmeme.com/memes/flipping-tables-%E2%95%AF%E2%96%A1%EF%BC%89%E2%95%AF%EF%B8%B5-%E2%94%BB%E2%94%81%E2%94%BB/photos"
    img_links = yield from _retrieve(meme_url, "#photo_gallery img", "data-src")

    if len(img_links) > 0:
        img_link = random.choice(img_links)

        image_data = urllib.request.urlopen(img_link)
        filename = os.path.basename(img_link)

        legacy_segments = [hangups.ChatMessageSegment(msg, hangups.SegmentType.TEXT, is_italic=True)]

        print("tableflip(): uploading {} from {}".format(filename, img_link))
        photo_id = yield from bot._client.upload_image(image_data, filename=filename)

        bot.send_message_segments(event.conv.id_, legacy_segments, image_id=photo_id)
    else:
        bot.send_message_parsed(event.conv, _("<i>{}</i><br/>(ﾉಥ益ಥ）ﾉ ┻━┻").format(msg))
