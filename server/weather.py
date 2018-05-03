#-*- coding:utf-8 -*-
"""
" Autho: BaileyMarais(maxun@live.cn)
" Date : 2018-05-03
"""

import requests
from bs4 import BeautifulSoup
import pymysql
import time
import json
import conf


class weather:
    def __init__(self):
        self.__headers = { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/11.1 Safari/605.1.15' }
        self.__db = pymysql.connect(host=conf.db_server, user=conf.db_user, password=conf.db_pass, db=conf.db_catalog, use_unicode=True, charset=conf.db_charset)
        self.__cursor = self.__db.cursor()
        self.__datasourceId = ""
        self.__cursor.execute("select id from datasource where name='www.weather.com.cn';")
        temp = self.__cursor.fetchone()
        if temp and len(temp) > 0:
            self.__datasourceId = str(temp[0])


    def __del__(self):
        self.__db.close()


    """
    将某一个城市加入任务列表，如果任务列表中有这个城市，那么返回空字符串，否则返回对应的城市编号
    """
    def cachecity(self, cityname):
        if self.__datasourceId == "":
            return ""

        url = "http://toy1.weather.com.cn/search?cityname=%s&r=%d" % (cityname, time.time())
        r = requests.get(url, headers=self.__headers, timeout=10)
        if 200 == r.status_code:
            r.encoding = "utf-8"
            http_result = json.loads(r.text[1:len(r.text)-1])
            if http_result and len(http_result) > 0:
                cityid = http_result[0]['ref'].split("~")[0]

                sql = "select id from citylist where datasource_id={0} and citynum='{1}'".format(
                    self.__datasourceId,
                    cityid
                )
                self.__cursor.execute(sql)
                existeditem = self.__cursor.fetchone()
                if existeditem == None or len(existeditem) == 0:
                    sql = "insert into citylist(datasource_id,cityname,citynum,dataurl) values({0},'{1}','{2}', 'http://www.weather.com.cn/weather/{2}.shtml')".format(
                        self.__datasourceId,
                        cityname,
                        cityid
                    )
                    self.__cursor.execute(sql)
                    self.__db.commit()
                    return cityid
        return ""


    """
    重新刷新数据库
    datasourceId: 数据源在数据库中的编号
    cityidList: 指定更新某一部分城市编号
    """
    def rebase(self, cityidList = None):
        if self.__datasourceId == "":
            return

        sql = "select datasource_id, cityname,dataurl,id from citylist where datasource_id={0}".format(self.__datasourceId)
        if cityidList and len(cityidList) > 0:
            sql += "and citynum in " + str(cityidList).replace("[", "(").replace("]",")")

        self.__cursor.execute(sql)
        data = self.__cursor.fetchall()
        for item in data:
            print("正在更新[{0}]的数据...".format(item[1]))
            r = requests.get(item[2], headers=self.__headers)
            if 200 == r.status_code:
                r.encoding = "utf-8"
                soup = BeautifulSoup(r.text, "html.parser")
                weatherlist = soup.find_all('li', class_=["sky skyid lv3 on", "sky skyid lv3", "sky skyid lv2 on", "sky skyid lv2"])

                # 更新最近7天的天气
                if len(weatherlist) == 7:
                    dayindex = 0
                    for everyday in weatherlist:
                        if everyday.h1:
                            forecast_min = everyday.i.get_text().replace("℃","")
                            forecast_max = everyday.span.get_text().replace("℃","")

                            localtime = time.localtime(time.time() + 86400 * dayindex)
                            sql = 'select id from weatherlist where forecast_date = "{0}" and citylist_id={1}'.format(
                                time.strftime("%Y-%m-%d", localtime),
                                item[3]
                            )
                            self.__cursor.execute(sql)
                            forecast_id = self.__cursor.fetchone()
                            if forecast_id and len(forecast_id) > 0:
                                # 这一天的数据存在，更新它
                                sql = 'update weatherlist set {0} {1} updated=now() where id={2}'.format(
                                    "forecast_min=" + forecast_min + "," if len(forecast_min) > 0 else "",
                                    "forecast_max=" + forecast_max + "," if len(forecast_max) > 0 else "",
                                    forecast_id[0]
                                )
                            else:
                                sql = 'insert into weatherlist(forecast_date, forecast_min, forecast_max, updated, citylist_id) values("{0}",{1},{2},now(), {3});'.format(
                                    time.strftime("%Y-%m-%d", localtime),
                                    forecast_min if len(forecast_min) > 0 else "-1",
                                    forecast_max if len(forecast_max) > 0 else "-1",
                                    item[3]
                                )

                                self.__cursor.execute(sql)
                            dayindex += 1

                    self.__db.commit()