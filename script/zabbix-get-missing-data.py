#!/usr/bin/env python

import sys
import os
import datetime
import time
import atexit
import subprocess
import shlex
from socket import gethostname

import psycopg2

import zabbix_api

DEBUG = False

PG_HOST = "localhost"
PG_PORT = 5432
PG_USER = "zabbix"
PG_PASS = "qwerty"
PG_DB = "zabbix"

ZABBIX_SERVER = "https://zabbix.domain.tld"
ZABBIX_USER = "zabbix-api"
ZABBIX_PASS = "qwerty"
ZABBIX_HOSTNAME = "zabbix"
ZABBIX_FILE = '/tmp/zabbix-missing-data.tmp'
ZABBIX_COMMAND = '/usr/bin/zabbix_sender'

TRIGGER_STATES = {
        "problem": {"value": 0},
        "ok": {"value": 1},
        "unknown": {"value_flags": 1}
        }

ITEM_STATUSES = {
        "ACTIVE": 0,
        "DISABLED": 1,
        "NOT_SUPPORTED": 3
        }

ITEM_NO_DATA_MINUTES = 10

EMPTY_MESSAGE = 'none'
TRIGGER_UNKNOWN_MESSAGE = 'Triggers in unknown state found:\n'
TRIGGER_UNKNOWN_ENTRY = '''{number}) hostname: {hostname}, host ip: {host_ip}, trigger name: {name}'''
ITEM_NOT_SUPPORTED_MESSAGE = 'Items in not supported state found:\n'
ITEM_NOT_SUPPORTED_ENTRY = '''{number}) hostname: {hostname}, host ip: {host_ip}, item name: {name}'''
ITEM_NO_DATA_MESSAGE = 'Items missing data for %d min found:\n' % (
        ITEM_NO_DATA_MINUTES, )
ITEM_NO_DATA_ENTRY = '''{number}) hostname: {hostname}, host ip: {host_ip}, item name: {name}'''



def connect_pg():
    conn = psycopg2.connect(host=PG_HOST,
                         user=PG_USER,
                         password=PG_PASS,
                         database=PG_DB,
                         port=PG_PORT,
                         )
    cursor = conn.cursor()

    # close connection on script exit
    @atexit.register
    def _close():
        cursor.close()
        conn.close()
    return cursor

def get_no_data():
    cursor = connect_pg()
    cursor.execute("""
            SELECT h.STATUS AS host_status, h.name AS host, i.name AS name,
            i.itemid, i.STATUS AS item_status, h.hostid as hostid,
            age(now(),to_timestamp(i.lastclock+i.delay))

            FROM items i LEFT JOIN hosts h ON h.hostid=i.hostid

            WHERE age(now(),to_timestamp(i.lastclock+i.delay)) > interval '10
            minutes'

            AND ( h.STATUS = 0 AND i.STATUS = 0 ) -- both enabled

            AND (i.type != '7') -- log

            AND (i.type != '2') -- trapper

            AND (h.available = '1')

            ORDER BY h.name;
            """)
    names = [r[0] for r in cursor.description]
    data = [dict(zip(names, entry)) for entry in cursor.fetchall()]
    return data

def main():
    zapi = zabbix_api.ZabbixAPI(server=ZABBIX_SERVER)
    zapi.login(ZABBIX_USER, ZABBIX_PASS)
    host_interfaces = dict([(hi['hostid'], hi)
        for hi in zapi.hostinterface.get({"output": ["ip", "hostid"]})
        ])
    hosts = dict([(h['hostid'], h)
        for h in zapi.host.get({"filter":{"available": 1}, "output": ["name"]})
        ])
    trigger_res = zapi.trigger.get({
        "filter": TRIGGER_STATES['unknown'],
        "expandData": True,
        "active": True,
        "output": ["description"]
        })
    def make_message(data, msg, head='', empty=EMPTY_MESSAGE):
        if not data:
            return empty
        result = head
        num = 1
        data_msg = ''
        for entry in data:
            hostid = str(entry['hostid'])
            if 'name' in entry:
                name = entry['name']
            elif 'description' in entry:
                name = entry['description']
            else:
                name = None
            if hostid not in hosts:
                continue
            data_msg += msg.format(
                    number=num,
                    hostname=hosts[hostid]['name'],
                    host_ip=host_interfaces[hostid]['ip'],
                    name=name
                    )
            num += 1
            data_msg += '\n'
        if not data_msg.strip():
            return empty
        result = result + data_msg
        return result

    trigger_message = make_message(trigger_res, TRIGGER_UNKNOWN_ENTRY, TRIGGER_UNKNOWN_MESSAGE)

    item_no_support_res = zapi.item.get({
        "filter": {
            "status": ITEM_STATUSES['NOT_SUPPORTED'],
            },
        "output": ["hostid", "name"]
        })
    item_no_support_msg = make_message(item_no_support_res,
            ITEM_NOT_SUPPORTED_ENTRY, ITEM_NOT_SUPPORTED_MESSAGE)

    item_no_data_res = get_no_data()
    item_no_data_msg = make_message(item_no_data_res, ITEM_NO_DATA_ENTRY,
            ITEM_NO_DATA_MESSAGE)

    write_to_zabbix([
        {
            "key": "zabbix.triggers.unknown",
            "value": trigger_message
            },
        {
            "key": "zabbix.items.notsupported",
            "value": item_no_support_msg
            },
        {
            "key": "zabbix.items.missingdata",
            "value": item_no_data_msg
            }
        ])

def write_to_zabbix(data):
    for entry in data:
        if not 'key' in entry or not 'value' in entry:
            continue

        key = entry['key']
        msg = entry['value']
        if DEBUG:
            print msg
            continue
        # msg = msg.replace('\n', ' ')

        cmd = ('{command} -c /etc/zabbix/zabbix_agentd.conf \
                -k "{key}" -o "{value}"'.format(
                    command=ZABBIX_COMMAND,
                    key=key,
                    value=msg
                    ))
        args = shlex.split(cmd)
        # hostname = gethostname()
        # with open(ZABBIX_FILE, 'w') as fp:
        #     fp.write('%s %s %s' % (hostname, key, msg))
        subprocess.call(args)



if __name__ == '__main__':
    main()
