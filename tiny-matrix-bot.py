#!/usr/bin/env python3

import sys
import os
import re
import stat
import signal
import socket
import logging
import subprocess
import configparser
import time
from time import sleep
from threading import Thread
from matrix_client.client import MatrixClient

class TinyMatrixtBot():
    def __init__(self, hostname, username, password, displayname):
        signal.signal(signal.SIGTERM, self.on_signal)

        self.current_path = os.path.dirname(os.path.realpath(__file__))
        self.scripts_path = os.path.join(self.current_path, "scripts")
        self.sockets_path = os.path.join(self.current_path, "sockets")
        
        os.chdir(self.scripts_path)
        self.scripts = self.load_scripts(self.scripts_path)

        self.client = MatrixClient(hostname)
        self.client.login_with_password(username=username, password=password)

        self.user = self.client.get_user(self.client.user_id)
        self.user.set_display_name(displayname)

        for room_id in self.client.get_rooms():
            self.join_room(room_id)

        self.client.start_listener_thread()
        self.client.add_invite_listener(self.on_invite)
        self.client.add_leave_listener(self.on_leave)

        while True:
            try:
                i = input().strip()
                if i == "rooms":
                    for room_id in self.client.get_rooms():
                        print(room_id)
                if i.startswith("part "):
                    self.client.get_rooms()[i[5:]].leave()
            except (EOFError, KeyboardInterrupt):
                self.exit()

    def exit(self, msg="bye!"):
        print(msg)
        sys.exit()

    def on_signal(self, signal, frame):
        if signal == 15:
            self.exit()

    def load_scripts(self, path):
        scripts = {}
        for script in os.listdir(path):
            script = os.path.join(path, script)
            if not stat.S_IXUSR & os.stat(script)[stat.ST_MODE]:
                continue
            output = subprocess.getoutput("CONFIG=1 {}".format(script)).strip()
            if not output:
                continue
            scripts[output] = script
            print("script {} {}".format(output, script))
        return scripts

    def on_invite(self, room_id, state):
        print("invite {}".format(room_id))
        self.join_room(room_id)

    def join_room(self, room_id):
        room = self.client.join_room(room_id)
        room.add_listener(self.on_room_event)
        print("join {}".format(room_id))
        thread = Thread(target=self.create_socket, args=(room, ))
        thread.daemon = True
        thread.start()

    def create_socket(self, room):
        socket_name = re.search("^\!([A-Za-z]+):", room.room_id).group(1)
        socket_path = os.path.join(self.sockets_path, socket_name)
        try:
            os.remove(socket_path)
        except OSError:
            pass
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(socket_path)
        sock.listen(1)
        print("bind {}".format(socket_path))
        while True:
            conn, addr = sock.accept()
            recv = conn.recv(4096).decode('utf-8').strip()
            print("recv {} {}".format(socket_path, recv))
            room.send_text(recv)

    def on_leave(self, room_id, state):
        print("leave {}".format(room_id))

    def on_room_event(self, room, event):
        if event["type"] == "m.room.message":
            if event["content"]["msgtype"] == "m.text":
                body = event["content"]["body"].strip()
                for regex, script in self.scripts.items():
                    if re.search(regex, body):
                        self.run_script(room, script, body)

    def run_script(self, room, script, args):
        print("run {} {}".format(script, args))
        output = subprocess.getoutput("{} {}".format(script, args)).strip()
        for line in output.splitlines():
            sleep(1)
            print(line)
            room.send_text(line)

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) < 2:
        print("{} <path to config file>".format(sys.argv[0]))
        sys.exit()
    if not os.path.isfile(sys.argv[1]):
        print("config file `{}' not found".format(sys.argv[1]))
        sys.exit()
    config = configparser.ConfigParser()
    config.read(sys.argv[1])
    TinyMatrixtBot(
        config.get("tiny-matrix-bot", "host"),
        config.get("tiny-matrix-bot", "user"),
        config.get("tiny-matrix-bot", "pass"),
        config.get("tiny-matrix-bot", "name"))
