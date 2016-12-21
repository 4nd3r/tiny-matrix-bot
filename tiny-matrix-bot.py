#!/usr/bin/env python

import sys
import os
import stat
import logging
import ConfigParser
from time import sleep
from subprocess import check_output
from matrix_client.client import MatrixClient

reload(sys)
sys.setdefaultencoding("utf-8")

logging.basicConfig(level=logging.WARNING)

config = ConfigParser.ConfigParser()
config.read("tiny-matrix-bot.cfg")

os.chdir("scripts")

client = MatrixClient(config.get("tiny-matrix-bot", "host"))

token = client.login_with_password(
    username=config.get("tiny-matrix-bot", "user"),
    password=config.get("tiny-matrix-bot", "pass"))

def on_event(event):
    if event["type"] == "m.room.message":
        print("{0} {1} {2} {3}".format(
            event["content"]["msgtype"],
            event["room_id"],
            event["sender"],
            event["content"]["body"]))

def on_invite(room_id, state):
    print("invite {0}".format(room_id))
    join_room(room_id)

def join_room(room_id):
    room = client.join_room(room_id)
    room.add_listener(on_room_event)
    print("join {0}".format(room_id))

def on_room_event(room, event):
    if event["type"] == "m.room.message":
        if event["content"]["msgtype"] == "m.text":
            m_text(room, event)

def m_text(room, event):
    body = event["content"]["body"]
    if not body.startswith("!"):
        return
    s = body.split()
    cmd = s[0][1:]
    s.pop(0)
    args = " ".join(s)
    script = os.path.abspath(cmd)
    if not os.path.isfile(script):
        print "ERROR: file `{0}' not found".format(script)
        return
    if not stat.S_IXUSR & os.stat(script)[stat.ST_MODE]:
        print "ERROR: file `{0}' not executable".format(script)
        return
    print("script {0} {1}".format(script, args))
    output = check_output([script, args]).strip()
    for line in output.splitlines():
        sleep(1)
        room.send_text(line)

for room_id in client.get_rooms():
    join_room(room_id)

if config.getboolean("tiny-matrix-bot", "chat"):
    client.add_listener(on_event)

client.add_invite_listener(on_invite)
client.start_listener_thread()

user = client.get_user(client.user_id)
user.set_display_name(config.get("tiny-matrix-bot", "name"))

while True:
    pass
