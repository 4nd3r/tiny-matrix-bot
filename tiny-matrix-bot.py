#!/usr/bin/env python3

import sys
import os
import re
import signal
import socket
import logging
import subprocess
import configparser
from time import sleep
from threading import Thread
from matrix_client.client import MatrixClient

class TinyMatrixtBot():
    def __init__(self, path_config):
        signal.signal(signal.SIGHUP,  self.on_signal)
        signal.signal(signal.SIGINT,  self.on_signal)
        signal.signal(signal.SIGTERM, self.on_signal)

        self.logger = logging.getLogger("TinyMatrixBot")

        self.config = configparser.ConfigParser()
        self.config.read(path_config)

        path_current = os.path.dirname(os.path.realpath(__file__))

        self.path_lib = self.config.get("tiny-matrix-bot", "lib",
            fallback=os.path.join(path_current, "scripts")).strip()
        self.logger.info("SCRIPTS {}".format(self.path_lib))
        if os.access(self.path_lib, os.R_OK):
            self.scripts = self.load_scripts(self.path_lib)
        else:
            self.logger.error("ERROR {} is not readable".format(self.path_lib))
            sys.exit(0)

        self.path_var = self.config.get("tiny-matrix-bot", "var",
            fallback=os.path.join(path_current, "data")).strip()
        self.logger.info("DATA {}".format(self.path_var))
        if os.access(self.path_var, os.W_OK):
            os.chdir(self.path_var)
        else:
            self.logger.error("ERROR {} is not writeable".format(self.path_var))
            sys.exit(0)

        self.path_run = self.config.get("tiny-matrix-bot", "run",
            fallback=os.path.join(path_current, "sockets")).strip()
        if os.access(self.path_run, os.W_OK):
            self.logger.info("SOCKETS {}".format(self.path_run))
        else:
            self.logger.info("SOCKETS {} (not writeable, disabling sockets)".format(self.path_run))
            self.path_run = False

        self.connect()
        self.user = self.client.get_user(self.client.user_id)
        self.user.set_display_name(self.config.get("tiny-matrix-bot", "name"))

        for room_id in self.client.get_rooms():
            self.join_room(room_id)

        self.client.start_listener_thread(exception_handler=self.listener_exception_handler)
        self.client.add_invite_listener(self.on_invite)
        self.client.add_leave_listener(self.on_leave)

        while True:
            sleep(1)

    def connect(self):
        self.logger.info("Connecting...")
        try:
            self.client = MatrixClient(self.config.get("tiny-matrix-bot", "host"))
            self.client.login_with_password(
                username=self.config.get("tiny-matrix-bot", "user"),
                password=self.config.get("tiny-matrix-bot", "pass"))
            self.logger.info("Connected!")
        except:
            self.logger.warning("Connection failed, retrying...")
            sleep(5)
            self.connect()

    def listener_exception_handler(self, e):
        self.connect()

    def on_signal(self, signal, frame):
        if signal == 1:
            self.scripts = self.load_scripts(self.path_lib)
        elif signal in [2, 15]:
            sys.exit(0)

    def load_scripts(self, path):
        scripts = {}
        for script in os.listdir(path):
            script_path = os.path.join(path, script)
            if not os.access(script_path, os.R_OK) \
                or not os.access(script_path, os.X_OK):
                continue
            output = subprocess.Popen(
                [script_path],
                env={"CONFIG": "1"},
                stdout=subprocess.PIPE,
                universal_newlines=True
                ).communicate()[0].strip()
            if not output:
                continue
            scripts[output] = script_path
            self.logger.info("LOAD {} {}".format(script, output))
        return scripts

    def on_invite(self, room_id, state):
        self.logger.info("INVITE {}".format(room_id))
        self.join_room(room_id)

    def join_room(self, room_id):
        room = self.client.join_room(room_id)
        room.add_listener(self.on_room_event)
        self.logger.info("JOIN {}".format(room_id))
        if self.path_run is not False:
            thread = Thread(target=self.create_socket, args=(room, ))
            thread.daemon = True
            thread.start()

    def create_socket(self, room):
        socket_name = re.search("^\!([a-z]+):", room.room_id, re.IGNORECASE).group(1)
        socket_path = os.path.join(self.path_run, socket_name)
        try:
            os.remove(socket_path)
        except OSError:
            pass
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(socket_path)
        sock.listen(1)
        self.logger.info("SOCKET {}".format(socket_path))
        while True:
            conn, addr = sock.accept()
            recv = conn.recv(4096).decode('utf-8').strip()
            self.logger.info("RECV {} {}".format(socket_path, recv))
            room.send_text(recv)

    def on_leave(self, room_id, state):
        self.logger.info("LEAVE {}".format(room_id))

    def on_room_event(self, room, event):
        if event["sender"] == self.client.user_id:
            return
        if event["type"] == "m.room.message":
            if event["content"]["msgtype"] == "m.text":
                body = event["content"]["body"].strip()
                for regex, script in self.scripts.items():
                    if re.search(regex, body, re.IGNORECASE):
                        self.run_script(room, event, [script, body])

    def run_script(self, room, event, args):
        self.logger.info("ROOM {}".format(event["room_id"]))
        self.logger.info("SENDER {}".format(event["sender"]))
        self.logger.info("RUN {}".format(args))
        output = subprocess.Popen(
            args,
            env={
                "MXROOMID": event["room_id"],
                "MXSENDER": event["sender"]
            },
            stdout=subprocess.PIPE,
            universal_newlines=True
            ).communicate()[0].strip()
        sleep(0.5)
        for p in output.split("\n\n"):
            for l in p.split("\n"):
                self.logger.info("OUTPUT {}".format(l))
            room.send_text(p)
            sleep(1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "tiny-matrix-bot.cfg")
    if len(sys.argv) == 2:
        cfg = sys.argv[1]
    if not os.path.isfile(cfg):
        print("config file {} not found".format(cfg))
        sys.exit(0)
    try:
        TinyMatrixtBot(cfg)
    except Exception:
        sys.exit(1)
