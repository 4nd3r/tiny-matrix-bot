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

logger = logging.getLogger(__name__)


class TinyMatrixtBot():
    def __init__(self, path_config):
        signal.signal(signal.SIGHUP,  self.on_signal)
        signal.signal(signal.SIGINT,  self.on_signal)
        signal.signal(signal.SIGTERM, self.on_signal)

        self.config = configparser.ConfigParser()
        self.config.read(path_config)

        _path_current = os.path.dirname(os.path.realpath(__file__))

        self.enabled_scripts = self.config.get(
            "tiny-matrix-bot", "enabled_scripts", fallback="").strip()

        self.path_lib = self.config.get(
            "tiny-matrix-bot", "lib",
            fallback=os.path.join(_path_current, "scripts")).strip()
        logger.debug("path_lib = {}".format(self.path_lib))
        if os.access(self.path_lib, os.R_OK):
            self.scripts = self.load_scripts(self.path_lib)
        else:
            logger.error("{} not readable".format(self.path_lib))
            sys.exit(1)

        self.path_var = self.config.get(
            "tiny-matrix-bot", "var",
            fallback=os.path.join(_path_current, "data")).strip()
        logger.debug("path_var = {}".format(self.path_var))
        if os.access(self.path_var, os.W_OK):
            os.chdir(self.path_var)
        else:
            logger.error("{} not writeable".format(self.path_var))
            sys.exit(1)

        self.path_run = self.config.get(
            "tiny-matrix-bot", "run",
            fallback=os.path.join(_path_current, "sockets")).strip()
        if os.access(self.path_run, os.W_OK):
            logger.debug("path_run = {}".format(self.path_run))
        else:
            logger.debug(
                "path_run = {}".format(self.path_run) +
                " (not writeable, disabling sockets)")
            self.path_run = False

        self.inviter_whitelist = self.config.get(
            "tiny-matrix-bot", "inviter_whitelist", fallback="").strip()

        self.connect()

        for room_id in self.client.get_rooms():
            self.join_room(room_id)

        self.client.start_listener_thread(
            exception_handler=self.listener_exception_handler)
        self.client.add_invite_listener(self.on_invite)
        self.client.add_leave_listener(self.on_leave)

        while True:
            sleep(1)

    def connect(self):
        _host = self.config.get("tiny-matrix-bot", "host")
        _user = self.config.get("tiny-matrix-bot", "user", fallback=None)
        _pass = self.config.get("tiny-matrix-bot", "pass", fallback=None)
        _token = self.config.get("tiny-matrix-bot", "token", fallback=None)
        try:
            if _token:
                self.client = MatrixClient(_host, token=_token)
                logger.info("connected to {} using token".format(_host))
            else:
                self.client = MatrixClient(_host)
                self.client.login(username=_user, password=_pass, limit=0)
                logger.info("connected to {} using password".format(_host))
        except Exception:
            logger.warning(
                "connection to {} failed".format(_host) +
                ", retrying in 5 seconds...")
            sleep(5)
            self.connect()

    def listener_exception_handler(self, e):
        self.connect()

    def on_signal(self, signal, frame):
        if signal == 1:
            self.scripts = self.load_scripts(self.path_lib)
        elif signal in [2, 15]:
            _token = self.config.get("tiny-matrix-bot", "token", fallback=None)
            if not _token:
                self.client.logout()
            sys.exit(0)

    def load_scripts(self, path):
        _scripts = {}
        for _script in os.listdir(path):
            _script_path = os.path.join(path, _script)
            if self.enabled_scripts:
                if _script not in self.enabled_scripts:
                    continue
            if (not os.access(_script_path, os.R_OK) or
                    not os.access(_script_path, os.X_OK)):
                continue
            _regex = subprocess.Popen(
                [_script_path],
                env={"CONFIG": "1"},
                stdout=subprocess.PIPE,
                universal_newlines=True
                ).communicate()[0].strip()
            if not _regex:
                continue
            _scripts[_regex] = _script_path
            logger.info("script load {}".format(_script))
            logger.debug("script regex {}".format(_regex))
        return _scripts

    def on_invite(self, room_id, state):
        _sender = "someone"
        for _event in state["events"]:
            if _event["type"] != "m.room.join_rules":
                continue
            _sender = _event["sender"]
            break
        logger.info("invited to {} by {}".format(room_id, _sender))
        if self.inviter_whitelist:
            if not re.search(self.inviter_whitelist, _sender, re.IGNORECASE):
                logger.info(
                    "no whitelist match, ignoring invite from {}"
                    .format(_sender))
                return
        self.join_room(room_id)

    def join_room(self, room_id):
        logger.info("join {}".format(room_id))
        _room = self.client.join_room(room_id)
        _room.add_listener(self.on_room_event)
        if self.path_run is not False:
            _thread = Thread(target=self.create_socket, args=(_room, ))
            _thread.daemon = True
            _thread.start()

    def create_socket(self, room):
        _socket_name = re.search(
            "^!([a-z]+):", room.room_id,
            re.IGNORECASE).group(1)
        _socket_path = os.path.join(self.path_run, _socket_name)
        try:
            os.remove(_socket_path)
        except OSError:
            pass
        _socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        _socket.bind(_socket_path)
        _socket.listen(1)
        logger.info("socket bind {}".format(_socket_path))
        while True:
            _conn, _addr = _socket.accept()
            _recv = _conn.recv(4096).decode('utf-8').strip()
            logger.debug("socket recv {} {}".format(_socket_path, _recv))
            room.send_text(_recv)

    def on_leave(self, room_id, state):
        _sender = "someone"
        for _event in state["timeline"]["events"]:
            if not _event["membership"]:
                continue
            _sender = _event["sender"]
        logger.info("kicked from {} by {}".format(room_id, _sender))

    def on_room_event(self, room, event):
        if event["sender"] == self.client.user_id:
            return
        if event["type"] != "m.room.message":
            return
        if event["content"]["msgtype"] != "m.text":
            return
        _args = event["content"]["body"].strip()
        for _regex, _script in self.scripts.items():
            if not re.search(_regex, _args, re.IGNORECASE):
                continue
            self.run_script(room, event, [_script, _args])

    def run_script(self, room, event, args):
        logger.debug("script room_id {}".format(event["room_id"]))
        logger.debug("script sender {}".format(event["sender"]))
        logger.debug("script run {}".format(args))
        _script = subprocess.Popen(
            args,
            env={
                "MXROOMID": event["room_id"],
                "MXSENDER": event["sender"]
            },
            stdout=subprocess.PIPE,
            universal_newlines=True
           )
        _output = _script.communicate()[0].strip()
        if _script.returncode != 0:
            logger.debug("script exit {}".format(_script.returncode))
            return
        sleep(0.5)
        for _p in _output.split("\n\n"):
            for _l in _p.split("\n"):
                logger.debug("script output {}".format(_l))
            room.send_text(_p)
            sleep(0.8)


if __name__ == "__main__":
    if 'DEBUG' in os.environ:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    cfg = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "tiny-matrix-bot.cfg")
    if len(sys.argv) == 2:
        cfg = sys.argv[1]
    if not os.path.isfile(cfg):
        print("config file {} not found".format(cfg))
        sys.exit(1)
    try:
        TinyMatrixtBot(cfg)
    except Exception:
        sys.exit(1)
