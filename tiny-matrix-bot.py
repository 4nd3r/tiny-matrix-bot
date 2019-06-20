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
        scripts = []
        for script_name in os.listdir(path):
            script_path = os.path.join(path, script_name)
            if enabled:
                if script_name not in enabled:
                    continue
            if (not os.access(script_path, os.R_OK) or
                    not os.access(script_path, os.X_OK)):
                continue
            script_regex = subprocess.Popen(
                [script_path],
                env={"CONFIG": "1"},
                stdout=subprocess.PIPE,
                universal_newlines=True
                ).communicate()[0].strip()
            if not script_regex:
                continue
            script_config = None
            if self.config.has_section(script_name):
                script_config = {}
                for key, value in self.config.items(script_name):
                    script_config["__" + key] = value
            script = {
                "name": script_name,
                "path": script_path,
                "regex": script_regex,
                "config": script_config
            }
            scripts.append(script)
            logger.info("script {}".format(script["name"]))
            logger.debug("script {}".format(script))
        return scripts

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
        sender = "someone"
        for event in state["events"]:
            if event["type"] != "m.room.join_rules":
                continue
            sender = event["sender"]
            break
        logger.info("invited to {} by {}".format(room_id, sender))
        if self.inviter_whitelist:
            if not re.search(self.inviter_whitelist, sender, re.IGNORECASE):
                logger.info(
                    "no whitelist match, ignoring invite from {}"
                    .format(_sender))
                return
        self.join_room(room_id)

    def join_room(self, room_id):
        logger.info("join {}".format(room_id))
        room = self.client.join_room(room_id)
        room.add_listener(self.on_room_event)

    def on_leave(self, room_id, state):
        sender = "someone"
        for event in state["timeline"]["events"]:
            if not event["membership"]:
                continue
            sender = event["sender"]
        logger.info("kicked from {} by {}".format(room_id, sender))

    def on_room_event(self, room, event):
        if event["sender"] == self.client.user_id:
            return
        if event["type"] != "m.room.message":
            return
        if event["content"]["msgtype"] != "m.text":
            return
        args = event["content"]["body"].strip()
        for script in self.scripts:
            if not re.search(script["regex"], args, re.IGNORECASE):
                continue
            self.run_script(room, event, script, args)

    def run_script(self, room, event, script, args):
        env = {}
        if script["config"]:
            env = script["config"]
        env["__room_id"] = event["room_id"]
        env["__sender"] = event["sender"]
        logger.debug("script env {}".format(env))
        logger.debug("script run {}".format([script["name"], args]))
        run = subprocess.Popen(
            [script["path"], args],
            env=env,
            stdout=subprocess.PIPE,
            universal_newlines=True
        )
        output = run.communicate()[0].strip()
        if run.returncode != 0:
            logger.debug("script exit {}".format(run.returncode))
            return
        sleep(0.5)
        for p in output.split("\n\n"):
            for l in p.split("\n"):
                logger.debug("script output {}".format(l))
            room.send_text(p)
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
