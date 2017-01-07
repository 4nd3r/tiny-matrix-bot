#!/usr/bin/env python

import sys
import os
import re
import stat
import signal
import socket
import logging
import ConfigParser
from time import sleep
from threading import Thread
from subprocess import check_output
from matrix_client.client import MatrixClient

reload(sys)
sys.setdefaultencoding("utf-8")
logging.basicConfig(level=logging.WARNING)

path_current = os.path.dirname(os.path.realpath(__file__))
path_scripts = os.path.join(path_current, "scripts")
path_sockets = os.path.join(path_current, "sockets")
path_config  = os.path.join(path_current, "tiny-matrix-bot.cfg")

config = ConfigParser.ConfigParser()
config.read(path_config)
config_host = config.get("tiny-matrix-bot", "host")
config_user = config.get("tiny-matrix-bot", "user")
config_pass = config.get("tiny-matrix-bot", "pass")
config_name = config.get("tiny-matrix-bot", "name")
config_chat = config.getboolean("tiny-matrix-bot", "chat")
config_sock = config.getboolean("tiny-matrix-bot", "sock")

def exit(msg="bye!"):
    print(msg)
    sys.exit()

def on_signal(signal, frame):
    if signal == 15:
        exit()

signal.signal(signal.SIGTERM, on_signal)

def on_invite(room_id, state):
    print("invite {0}".format(room_id))
    join_room(room_id)

def join_room(room_id):
    r = client.join_room(room_id)
    r.add_listener(on_room_event)
    print("join {0}".format(room_id))
    if config_sock:
        t = Thread(target=create_socket, args=(r, ))
        t.daemon = True
        t.start()

def create_socket(room):
    p = os.path.join(path_sockets,
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

def on_room_event(room, event):
    if event["type"] == "m.room.message":
        if config_chat:
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

client = MatrixClient(config_host)
client.login_with_password(username=config_user, password=config_pass)

user = client.get_user(client.user_id)
user.set_display_name(config_name)

os.chdir(path_scripts)

for room_id in client.get_rooms():
    join_room(room_id)

client.start_listener_thread()
client.add_invite_listener(on_invite)
client.add_leave_listener(on_leave)

while True:
    try:
        input = raw_input().strip()
        if input == "rooms":
            for room_id in client.get_rooms():
                print(room_id)
        if input.startswith("part "):
            client.get_rooms()[input[5:]].leave()
    except (EOFError, KeyboardInterrupt):
        exit()
