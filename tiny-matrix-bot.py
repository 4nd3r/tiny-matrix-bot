#!/usr/bin/env python3

import os
import re
import sys
import logging
import traceback
import subprocess
import configparser
from time import sleep
from matrix_client.client import MatrixClient

logger = logging.getLogger("tiny-matrix-bot")


class TinyMatrixtBot():
    def __init__(self):
        path_root = os.path.dirname(os.path.realpath(__file__))
        self.config = configparser.ConfigParser()
        if "CONFIG" in os.environ:
            path_config = os.environ["CONFIG"]
        else:
            path_config = os.path.join(path_root, "tiny-matrix-bot.cfg")
        self.config.read(path_config)
        path_run = self.config.get(
            "tiny-matrix-bot", "path_run",
            fallback=os.path.join(path_root, "run"))
        os.chdir(path_run)
        path_scripts = self.config.get(
            "tiny-matrix-bot", "path_scripts",
            fallback=os.path.join(path_root, "scripts"))
        scripts_enabled = self.config.get(
            "tiny-matrix-bot", "scripts_enabled", fallback=None)
        self.scripts = self.load_scripts(path_scripts, scripts_enabled)
        self.inviter_whitelist = self.config.get(
            "tiny-matrix-bot",
            "inviter_whitelist",
            fallback=None)
        self.url = self.config.get("tiny-matrix-bot", "url")
        self.token = self.config.get("tiny-matrix-bot", "token")
        self.connect()
        self.client.start_listener_thread(
            exception_handler=self.listener_exception_handler)
        self.client.add_invite_listener(self.on_invite)
        for room_id in self.client.get_rooms():
            self.join_room(room_id)
        self.client.add_leave_listener(self.on_leave)
        while True:
            sleep(1)

    def load_scripts(self, path, enabled):
        _scripts = []
        for _script_name in os.listdir(path):
            _script_path = os.path.join(path, _script_name)
            if enabled:
                if _script_name not in enabled:
                    continue
            if (not os.access(_script_path, os.R_OK) or
                    not os.access(_script_path, os.X_OK)):
                continue
            _script_regex = subprocess.Popen(
                [_script_path],
                env={"CONFIG": "1"},
                stdout=subprocess.PIPE,
                universal_newlines=True
                ).communicate()[0].strip()
            if not _script_regex:
                continue
            _script_config = None
            if self.config.has_section(_script_name):
                _script_config = {}
                for key, value in self.config.items(_script_name):
                    _script_config["__" + key] = value
            _script = {
                "name": _script_name,
                "path": _script_path,
                "regex": _script_regex,
                "config": _script_config
            }
            _scripts.append(_script)
            logger.info("script {}".format(_script["name"]))
            logger.debug("script {}".format(_script))
        return _scripts

    def connect(self):
        try:
            logger.info("connecting to {}".format(self.url))
            self.client = MatrixClient(self.url, token=self.token)
        except Exception:
            logger.warning(
                "connection to {} failed".format(self.url) +
                ", retrying in 5 seconds...")
            sleep(5)
            self.connect()

    def listener_exception_handler(self, e):
        self.connect()

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
        for _script in self.scripts:
            if not re.search(_script["regex"], _args, re.IGNORECASE):
                continue
            self.run_script(room, event, _script, _args)

    def run_script(self, room, event, script, args):
        logger.debug("script room_id {}".format(event["room_id"]))
        logger.debug("script sender {}".format(event["sender"]))
        logger.debug("script run {}".format([script["name"], args]))
        _script = subprocess.Popen(
            [script["path"], args],
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
    try:
        TinyMatrixtBot()
    except Exception:
        traceback.print_exc(file=sys.stdout)
    except KeyboardInterrupt:
        sys.exit(1)
