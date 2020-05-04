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
        root_path = os.path.dirname(os.path.realpath(__file__))
        self.config = configparser.ConfigParser()
        if "CONFIG" in os.environ:
            config_path = os.environ["CONFIG"]
        else:
            config_path = os.path.join(root_path, "tiny-matrix-bot.cfg")
        self.config.read(config_path)
        self.base_url = self.config.get("tiny-matrix-bot", "base_url")
        self.token = self.config.get("tiny-matrix-bot", "token")
        self.connect()
        if len(sys.argv) > 1:
            if sys.argv[1] not in self.client.rooms:
                sys.exit(1)
            if len(sys.argv) == 3:
                text = sys.argv[2]
            else:
                text = sys.stdin.read()
            logger.info("send message to {}".format(sys.argv[1]))
            self.client.rooms[sys.argv[1]].send_text(text)
            logger.info("message sent, exiting")
            sys.exit(0)
        run_path = self.config.get(
            "tiny-matrix-bot", "run_path",
            fallback=os.path.join(root_path, "run"))
        os.chdir(run_path)
        scripts_path = self.config.get(
            "tiny-matrix-bot", "scripts_path",
            fallback=os.path.join(root_path, "scripts"))
        enabled_scripts = self.config.get(
            "tiny-matrix-bot", "enabled_scripts", fallback=None)
        self.scripts = self.load_scripts(scripts_path, enabled_scripts)
        self.inviter = self.config.get(
            "tiny-matrix-bot", "inviter", fallback=None)
        self.client.add_invite_listener(self.on_invite)
        self.client.add_leave_listener(self.on_leave)
        for room_id in self.client.rooms:
            self.join_room(room_id)
        self.client.start_listener_thread(
            exception_handler=lambda e: self.connect())
        while True:
            sleep(1)

    def connect(self):
        try:
            logger.info("connecting to {}".format(self.base_url))
            self.client = MatrixClient(self.base_url, token=self.token)
            logger.info("connection established")
        except Exception:
            logger.warning(
                "connection to {} failed".format(self.base_url) +
                ", retrying in 5 seconds...")
            sleep(5)
            self.connect()

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
            script_env = os.environ
            script_env["CONFIG"] = "1"
            script_regex = subprocess.Popen(
                [script_path],
                env=script_env,
                stdout=subprocess.PIPE,
                universal_newlines=True
                ).communicate()[0].strip()
            if not script_regex:
                continue
            del script_env["CONFIG"]
            if self.config.has_section(script_name):
                for key, value in self.config.items(script_name):
                    script_env["__" + key] = value
            script = {
                "name": script_name,
                "path": script_path,
                "regex": script_regex,
                "env": script_env
            }
            scripts.append(script)
            logger.info("script {}".format(script["name"]))
            logger.debug("script {}".format(script))
        return scripts

    def on_invite(self, room_id, state):
        sender = "someone"
        for event in state["events"]:
            if event["type"] != "m.room.join_rules":
                continue
            sender = event["sender"]
            break
        logger.info("invited to {} by {}".format(room_id, sender))
        if self.inviter:
            if not re.search(self.inviter, sender):
                logger.info(
                    "{} is not inviter, ignoring invite"
                    .format(sender))
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
        script["env"]["__room_id"] = event["room_id"]
        script["env"]["__sender"] = event["sender"]
        logger.debug("script {}".format(script))
        if "__whitelist" in script["env"]:
            if not re.search(script["env"]["__whitelist"],
                             event["room_id"]+event["sender"]):
                logger.debug("script not whitelisted")
                return
        if "__blacklist" in script["env"]:
            if re.search(script["env"]["__blacklist"],
                         event["room_id"]+event["sender"]):
                logger.debug("script blacklisted")
                return
        logger.debug("script run {}".format([script["name"], args]))
        run = subprocess.Popen(
            [script["path"], args],
            env=script["env"],
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
    if "DEBUG" in os.environ:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    try:
        TinyMatrixtBot()
    except Exception:
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(1)
