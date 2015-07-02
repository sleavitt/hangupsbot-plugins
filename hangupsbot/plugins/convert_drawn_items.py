import asyncio
import json
from jsonschema import validate
import re
from collections import OrderedDict
from urllib.parse import urlparse, parse_qs
import logging

import hangups

import plugins


IITC_DRAWTOOLS_JSON_SCHEMA = {
    "type": "array",
    "items": {
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "type": {
                        "enum": [ "circle" ]
                    },
                    "latLng": {
                        "type": "object",
                        "properties": {
                            "lat": {
                                "type": "number"
                            },
                            "lng": {
                                "type": "number"
                            }
                        }
                    },
                    "radius": {
                        "type": "number"
                    },
                    "color": {
                        "type": "string",
                        "pattern": "^#(?:[0-9a-f]{3}|[0-9a-f]{6})$"
                    }
                },
                "required": [ "type", "latLng", "radius", "color" ]
            },
            {
                "type": "object",
                "properties": {
                    "type": {
                        "enum": [ "polygon" ]
                    },
                    "latLngs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "lat": {
                                    "type": "number"
                                },
                                "lng": {
                                    "type": "number"
                                }
                            }
                        },
                        "maxItems": 2,
                        "minItems": 2
                    },
                    "color": {
                        "type": "string",
                        "pattern": "^#(?:[0-9a-f]{3}|[0-9a-f]{6})$"
                    }
                },
                "required": [ "type", "latLngs", "color" ]
            },
            {
                "type": "object",
                "properties": {
                    "type": {
                        "enum": [ "polyline" ]
                    },
                    "latLngs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "lat": {
                                    "type": "number"
                                },
                                "lng": {
                                    "type": "number"
                                }
                            }
                        },
                        "maxItems": 2,
                        "minItems": 2
                    },
                    "color": {
                        "type": "string",
                        "pattern": "^#(?:[0-9a-f]{3}|[0-9a-f]{6})$"
                    }
                },
                "required": [ "type", "latLngs", "color" ]
            },
            {
                "type": "object",
                "properties": {
                    "type": {
                        "enum": [ "marker" ]
                    },
                    "latLng": {
                        "type": "object",
                        "properties": {
                            "lat": {
                                "type": "number"
                            },
                            "lng": {
                                "type": "number"
                            }
                        }
                    },
                    "color": {
                        "type": "string",
                        "pattern": "^#(?:[0-9a-f]{3}|[0-9a-f]{6})$"
                    }
                },
                "required": [ "type", "latLng", "color" ]
            }
        ]
    }
}


def _initialise(bot):
    plugins.register_handler(_handle_drawn_items, type="message")


@asyncio.coroutine
def _handle_drawn_items(bot, event, command):
    convert_drawn_items_enabled = bot.get_config_suboption(event.conv.id_, 'convert_drawn_items_enabled')
    if not convert_drawn_items_enabled:
        logging.info(_("convert_drawn_items in {} disabled/unset").format(event.conv.id_))
        return

    json = _handle_stock_intel_link(bot, event, event.text.strip())
    if json is not None:
        bot.send_message_parsed(event.conv, json)
        return

    link = _handle_iitc_draw_tools_json(bot, event, event.text.strip())
    if link is not None:
        bot.send_message_parsed(event.conv, link)
        return


def _handle_stock_intel_link(bot, event, text):
    url = urlparse(text)
    if re.match('(?:www\\.)?ingress\\.com(?::\d+)?', url.netloc) and url.path == '/intel':
        print("Found stock Intel link!")
        qs = parse_qs(url.query)

        if qs['pls']:
            print("Found drawn items on stock Intel link!")
            pls = qs['pls'][0]
            lines = []
            tmpLines = pls.split('_')

            try:
                for line in tmpLines:
                    floats = line.split(',')
                    floats = list(map(lambda x: float(x), floats))

                    if len(floats) != 4:
                        print("URL item not a set of 4 floats")
                        pass

                    startLatLng = OrderedDict((("lat", floats[0]), ("lng", floats[1])))
                    endLatLng   = OrderedDict((("lat", floats[2]), ("lng", floats[3])))

                    lines.append(OrderedDict((("type", "polyline"), ("latLngs", [startLatLng, endLatLng]), ("color", "#a24ac3"))))

                return json.dumps(lines)
            except ValueError:
                print("URL had an invalid number")

            pass
    else:
        pass


def _handle_iitc_draw_tools_json(bot, event, text):
    try:
        iitc_draw_tools = json.loads(text)
        validate(iitc_draw_tools, IITC_DRAWTOOLS_JSON_SCHEMA)

        print("Found IITC DrawTools JSON!")

        stockWarnings = {}
        stockLinks = []
        for obj in iitc_draw_tools:
            if obj['type'] == 'circle':
                stockWarnings['noCircle'] = true
                continue
            elif obj['type'] == 'polygon':
                stockWarnings['polyAsLine'] = true
                """ export polygons as individual polylines """
            elif obj['type'] == 'polyline':
                """ polylines are fine """
            elif obj['type'] == 'marker':
                stockWarnings['noMarker'] = true
                continue
            else:
                stockWarnings['unknown'] = true
                continue

            latLngs = obj['latLngs']
            length = len(latLngs)
            for i in range(0, length - 1):
                stockLinks.append([latLngs[i]['lat'], latLngs[i]['lng'], latLngs[i + 1]['lat'], latLngs[i + 1]['lng']])

            if obj['type'] == 'polygon':
                stockLinks.append([latLngs[length - 1]['lat'], latLngs[length - 1]['lng'], latLngs[0]['lat'], latLngs[0]['lng']])

        lat = "<lat>"
        lng = "<lng>"
        zoom = "<zoom>"

        intel_map = bot.get_config_suboption(event.conv.id_, 'intel_map')
        if intel_map is not None:
            if 'lat' in intel_map.keys() and intel_map['lat']:
                lat = intel_map['lat']
            if 'lng' in intel_map.keys() and intel_map['lng']:
                lng = intel_map['lng']
            if 'zoom' in intel_map.keys() and intel_map['zoom']:
                zoom = intel_map['zoom']

        pls = '_'.join([','.join(map(lambda y: '{}'.format(y), x)) for x in stockLinks])

        stockUrl = 'https://www.ingress.com/intel?ll={},{}&z={}&pls={}'.format(lat,lng,zoom,pls)

        stockWarnTexts = []
        if 'polyAsLine' in stockWarnings.keys() and stockWarnings['polyAsLine']:
            stockWarnTexts.append('Note: polygons are exported as lines');
        if len(stockLinks) > 40:
            stockWarnTexts.append('Warning: Stock intel may not work with more than 40 line segments - there are ' + ( '%d' % len(stockLinks) ))
        if 'noCircle' in stockWarnings.keys() and stockWarnings['noCircle']:
            stockWarnTexts.append('Warning: Circles cannot be exported to stock intel')
        if 'noMarker' in stockWarnings.keys() and stockWarnings['noMarker']:
            stockWarnTexts.append('Warning: Markers cannot be exported to stock intel')
        if 'unknown' in stockWarnings.keys() and stockWarnings['unknown']:
            stockWarnTexts.append('Warning: UNKNOWN ITEM TYPE')

        html = '<a href="' + stockUrl + '">' + stockUrl + '</a>'
        if len(stockWarnTexts) > 0:
            html = html + '<br/><ul><li>' + '</li><li>'.join(stockWarnTexts) + '</li></ul>'

        return html

    except ValueError:
        pass
