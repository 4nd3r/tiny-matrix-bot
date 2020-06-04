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
        logging.debug("arguments {}".format(sys.argv))
        logging.debug("arguments 1+ {}".format(sys.argv[1:]))
        logging.debug("arguments 1+ joined \"{}\"".format(' '.join(sys.argv[1:])))

        logging.debug("client rooms {}".format(self.client.rooms))

        if len(sys.argv) > 1:
            if sys.argv[1] not in self.client.rooms:
                logging.info("arg1 not in client rooms. Exiting ...")
                sys.exit(1)
            if len(sys.argv) == 3:
                text = sys.argv[2]
                logging.debug("arg2 text \"{}\".".format(text))
            else:
                text = sys.stdin.read()
            # downgraded this from info to debug, so that higher up programs
            # are not bothered by this output
            logger.debug("sending message to {}".format(sys.argv[1]))
            self.client.rooms[sys.argv[1]].send_text(text)
            logger.debug("message sent, now exiting")
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
            # downgraded this from info to debug, because if this program is used by other 
            # automated scripts for sending messages then this extra output is undesirable
            logger.debug("connecting to {}".format(self.base_url))
            self.client = MatrixClient(self.base_url, token=self.token)
            # same here, downgrade from info to debug, to avoid output for normal use 
            # cases in other automated scripts
            logger.debug("connection established")
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
                    logger.debug("script {} is not enabled".format(script_name))
                    continue
            if (not os.access(script_path, os.R_OK) or
                    not os.access(script_path, os.X_OK)):
                logger.debug("script {} is not executable".format(script_name))
                continue
            # the .copy() is extremely important, leaving it out is a major bug as memory is constantly overwritten!
            script_env = os.environ.copy()
            script_env["CONFIG"] = "1"
            logger.debug("script {} with script_env {}".format(script_name, script_env))
            script_regex = subprocess.Popen(
                [script_path],
                env=script_env,
                stdout=subprocess.PIPE,
                universal_newlines=True
                ).communicate()[0].strip()
            if not script_regex:
                logger.debug("script {} has no regex".format(script_name))
                continue
            del script_env["CONFIG"]
            if self.config.has_section(script_name):
                for key, value in self.config.items(script_name):
                    script_env["__" + key] = value
                    if "DEBUG" in os.environ:
                        logger.debug("add key-value pair key {} to script_env".format(key))
                        logger.debug("add key-value pair value {} to script_env".format(value))
            script = {
                "name": script_name,
                "path": script_path,
                "regex": script_regex,
                "env": script_env
            }
            scripts.append(script)
            if "DEBUG" in os.environ:
                logger.debug("script {}".format(script))
            else:
                logger.info("script {}".format(script["name"]))
            if "DEBUG" in os.environ:
                logger.debug("all scripts {}".format(scripts))

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
            if "DEBUG" in os.environ:
                logger.debug("event from sender (itself) {}".format(event["sender"]))
            return
        # ignore encrypted messages, but log them in debug mode
        if event["type"] == "m.room.encrypted":
            if "DEBUG" in os.environ:
                logger.debug("event type (m.room.encrypted) {}".format(event["type"]))
                logger.debug("sender_key (m.content.sender_key) {}".format(event["content"]["sender_key"]))
                logger.debug("ciphertext (m.content.ciphertext) {}".format(event["content"]["ciphertext"]))
            return
        if event["type"] != "m.room.message":
            if "DEBUG" in os.environ:
                logger.debug("event of type (!=room.message) {}".format(event["type"]))
            return
        # only plain text messages are processed, everything else is ignored
        if event["content"]["msgtype"] != "m.text":
            if "DEBUG" in os.environ:
                logger.debug("event of msgtype (!=m.text) {}".format(event["content"]["msgtype"]))
            return
        args = event["content"]["body"].strip()
        if "DEBUG" in os.environ:
            logger.debug("args {}".format(args))
        for script in self.scripts:
            # multiple scripts can match regex, multiple scripts can be kicked off
            if not re.search(script["regex"], args, re.IGNORECASE):
                continue
            self.run_script(room, event, script, args)

    def run_script(self, room, event, script, args):
        script["env"]["__room_id"] = event["room_id"]
        script["env"]["__sender"] = event["sender"]
        if "__whitelist" in script["env"]:
            if not re.search(script["env"]["__whitelist"],
                             event["room_id"]+event["sender"]):
                logger.debug("script {} not whitelisted".format(script["name"]))
                return
        if "__blacklist" in script["env"]:
            if re.search(script["env"]["__blacklist"],
                         event["room_id"]+event["sender"]):
                logger.debug("script {} blacklisted".format(script["name"]))
                return
        logger.debug("script {} run with env {}".format([script["name"], args], script["env"]))
        run = subprocess.Popen(
            [script["path"], args],
            env=script["env"],
            stdout=subprocess.PIPE,
            universal_newlines=True
        )
        output = run.communicate()[0].strip()
        if run.returncode != 0:
            logger.debug("script {} exited with {}".format(script["name"], run.returncode))
            return
        sleep(0.2) 
        # higher up programs or scripts have two options: 
        # Text with a single or a double linebreak (i.e. one empty line) stays together 
        # in a single messages, allowing one to write longer messages and structure
        # them clearly with separating whitespace (an empty line).
        # When two empty lines are found, the text is split up in multiple messages. 
        # That allows a single call to a script to generate multiple independent messages. 
        # In short, everything with 1 or 2 linebreaks stays together, wherever there are 3 
        # linebreaks the text is split into 2 or multiple messages.
        for p in output.split("\n\n\n"):
            for l in p.split("\n"):
                logger.debug("script {} output {}".format(script["name"], l))
            # strip again to get get rid of leading/training newlines and whitespaces left over from split
            room.send_text(p.strip()) 
            sleep(0.3) 


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
