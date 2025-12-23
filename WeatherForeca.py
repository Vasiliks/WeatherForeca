# -*- coding: UTF-8 -*-
# version: 23/12/2025
# author: Vasiliks
# ver 0.1
import json
import os
from datetime import datetime
from time import strftime, time
from six.moves.urllib.request import urlopen, Request

from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached
from Components.config import config
from Tools.Directories import fileExists

temperature_unit = {'c': "°C", 'f': "°F"}

json_file = "/tmp/foreca2.json"
time_update = 30
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 OPR/125.0.0.0'}

def write_log(value):
    with open("/tmp/m.log", 'a') as f:
        f.write(f'{value}\n')

def wind_speed(windspeed):
    wspeed, wunit = windspeed.split(" ")
    tab = {"ms": 1, "kmh": 3.6, "mph": 2.237}
    return round(int(wspeed) * tab.get(wunit, 1))


def winddir(windd):
    w = 0
    while w < 361:
        if windd < 23:
            return w % 360
        else:
            windd -= 45
            w += 45


def pressure(pres):
    p, un = pres.split(" ")
    if not un:
        un = "mmhg"
    tab = {"inhg": 0.0295, "mmhg": 0.75, "hPa": 1}
    
    return round(float(p) * tab.get(un, 0.75)),un  


def request_url(url, values={}, timeout=None, headers=HEADERS):
    retval = None
    data = None
    try:
        req = Request(url, None, headers)
        resp = urlopen(req, timeout=timeout)
        retval = resp.read().decode()

    except Exception as err:
        print("Error request: [%s] to url: [%s] with parametrs: [%s]" % (err, url, values))
    return retval


def get_json(id):
    API = "https://api.foreca.net/data/{}/{}.json"
    url = API.format("recent", id)
    data = request_url(url)
    c = json.loads(data).get(id)
    url = API.format("favorites", id)
    data = request_url(url)
    c["for10days"] = json.loads(data).get(id)
    url2 = "https://data.forecabox.com/daily/{}.json?lang=ru".format(id)
    img_data = request_url(url2)
    data = json.loads(img_data)
    data.pop("daily", None)
    data.pop("nowcast", None)
    with open(json_file, 'w', encoding='utf-8') as f:
        f.write(json.dumps({**data, **c}, ensure_ascii=False, sort_keys=False, indent=2))


class WeatherForeca(Poll, Converter, object):
    def __init__(self, type):
        Poll.__init__(self)
        Converter.__init__(self, type)
        self.fix = ""
        if ';' in type:
            type, self.fix = type.split(';')
        self.type = type
        self.poll_interval = 1000
        self.poll_enabled = True

    def T(self, t):
        key = self.fix.lower()
        if key == "f":
            t = int(1.8 * t + 32)
        else:
            key = "c"
        u = temperature_unit[key]
        return t, u

    @cached
    def getText(self):
        try:
            if config.plugins.meteoforeca.city.value:
                id = config.plugins.meteoforeca.city.value.split("/")[0]
        except AttributeError:
            id = "103169070"
        if fileExists(json_file):
            if int((time() - os.stat(json_file).st_mtime)/60) >= time_update:
                get_json(id)
        else:
            get_json(id)

        with open(json_file, "r") as f:
            d = f.read()
        weather_data = json.loads(d)

# ####  10 day weather  #####
        if self.type[-1].isdigit():
            day = int(self.type[-1:])
            param = self.type[:-1]
            weather_data10 = weather_data.get('for10days')[day]
            if "Temp" in param:
                tmin = weather_data10.get('tmin')
                t1, u1 = self.T(tmin)
                tmax = weather_data10.get('tmax')
                t2, u2 = self.T(tmax)
                if "min" in param:
                    return "{}{}".format(t1, u1)
                elif "max" in param:
                    return "{}{}".format(t2, u2)
                else:
                    return "{}..{}{}".format(t1, t2, u2)

            elif param == "Symb":
                return weather_data10.get("symb").upper()

            elif param == "Windd":
                return "W{}".format(winddir(weather_data10.get('windd')))

            elif param == "Wind":
                wind_item = wind_speed("{} {}".format(str(weather_data10.get('winds')), self.fix))
                return "{}".format(wind_item)

            elif param == "Date":
                d = datetime.fromisoformat(weather_data10.get("date"))
                return d.strftime(self.fix)

            elif param == "Rhum":
                return "{}%".format(weather_data10.get('rhum'))

            else:
                return " "

# ####  current weather #####

        if self.type == "Temp":
            t = weather_data.get('temp')
            t, u = self.T(t)
            return "{}{}".format(t, u)

        elif self.type == "Feelslike":
            t = weather_data.get('flike')
            t, u = self.T(t)
            return "{}{}".format(t, u)

        elif self.type == "Symb":
            return weather_data.get("symb")

        elif self.type == "Wind":
            item = wind_speed("{} {}".format(str(weather_data.get('winds')), self.fix))
            return "{}".format(item)

        elif self.type == "Windd":
            return "W{}".format(winddir(weather_data.get('windd')))

        elif self.type == "Rhum":
            return "{}%".format(weather_data.get('rhum'))

        elif self.type == "Rainp":
            return "{}%".format(weather_data.get('rainp'))

        elif self.type == "Rain":
            item = weather_data.get('rain')
            if self.fix == "in":
                item = item/2.54
            return "{}{}".format("%0.2f" % item, self.fix or "mm")

        elif self.type == "City":
            return "{}".format(weather_data.get('name'))

        elif self.type == "Pressure":
            item, unit = pressure("{} {}".format(str(weather_data.get('pres')), self.fix))
            return "{}{}".format(item, unit)

        else:
            return " "

    text = property(getText)

    def changed(self, what):
        Converter.changed(self, (self.CHANGED_POLL,))
