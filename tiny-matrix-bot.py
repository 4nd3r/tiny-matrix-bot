#!/usr/bin/env python

import sys
import os
import re
import stat
import signal
import thread
import socket
import logging
import ConfigParser
from time import sleep
from subprocess import check_output
from matrix_client.client import MatrixClient

PATH_CURRENT = os.path.dirname(os.path.realpath(__file__))
PATH_SCRIPTS = os.path.join(PATH_CURRENT, "scripts")
PATH_SOCKETS = os.path.join(PATH_CURRENT, "sockets")
PATH_CONFIG  = os.path.join(PATH_CURRENT, "tiny-matrix-bot.cfg")

config = ConfigParser.ConfigParser()
config.read(PATH_CONFIG)

CONF_HOST = config.get("tiny-matrix-bot", "host")
CONF_USER = config.get("tiny-matrix-bot", "user")
CONF_PASS = config.get("tiny-matrix-bot", "pass")
CONF_NAME = config.get("tiny-matrix-bot", "name")
CONF_CHAT = config.getboolean("tiny-matrix-bot", "chat")
CONF_SOCK = config.getboolean("tiny-matrix-bot", "sock")

def exit(msg="bye!"):
    print(msg)
    sys.exit()

def on_signal(signal, frame):
    if signal == 15:
        exit()

def on_invite(room_id, state):
    print("invite {0}".format(room_id))
    join_room(room_id)

def join_room(room_id):
    room = client.join_room(room_id)
    room.add_listener(on_room_event)
    print("join {0}".format(room_id))
    if CONF_SOCK:
        thread.start_new_thread(create_socket, (room, ))

def create_socket(room):
    p = os.path.join(PATH_SOCKETS,
        re.search("^\!([A-Za-z]+):", room.room_id).group(1))
    try:
        os.remove(p)
    except OSError:
        pass
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(p)
    s.listen(1)
    print("socket {0}".format(s.getsockname()))
    while True:
        c, a = s.accept()
        t = c.recv(4096).strip()
        room.send_text(t)

def on_leave(room_id, state):
    print("leave {0}".format(room_id))
    # TODO: remove sockets etc

def on_room_event(room, event):
    if event["type"] == "m.room.message":
        if CONF_CHAT:
            print("{0} {1} {2} {3}".format(
                event["content"]["msgtype"],
                event["room_id"],
                event["sender"],
                event["content"]["body"]))
        if event["content"]["msgtype"] == "m.text":
            if event["content"]["body"].strip().startswith("!"):
                run_script(room, event)

def run_script(room, event):
    s = event["content"]["body"].strip().split()
    cmd = s[0][1:]
    s.pop(0)
    args = " ".join(s)
    script = os.path.abspath(cmd)
    if not os.path.isfile(script):
        print "ERROR: script `{0}' not found".format(script)
        return
    if not stat.S_IXUSR & os.stat(script)[stat.ST_MODE]:
        print "ERROR: script `{0}' not executable".format(script)
        return
    print("script {0} {1}".format(script, args))
    output = check_output([script, args]).strip()
    for line in output.splitlines():
        sleep(1)
        room.send_text(line)

reload(sys)
sys.setdefaultencoding("utf-8")
signal.signal(signal.SIGTERM, on_signal)
logging.basicConfig(level=logging.WARNING)

client = MatrixClient(CONF_HOST)
client.login_with_password(username=CONF_USER, password=CONF_PASS)

user = client.get_user(client.user_id)
user.set_display_name(CONF_NAME)

os.chdir(PATH_SCRIPTS)

for room_id in client.get_rooms():
    join_room(room_id)

client.add_invite_listener(on_invite)
client.add_leave_listener(on_leave)
client.start_listener_thread()

while True:
    try:
        raw_input()
    except (EOFError, KeyboardInterrupt):
        exit()
