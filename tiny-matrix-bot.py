#!/usr/bin/env python3
# pylint: disable=missing-docstring,no-self-use,invalid-name,broad-except,too-many-instance-attributes

import asyncio
import logging
import os
import re
import subprocess
import sys
import time
import traceback

from nio import (
    AsyncClient,
    SyncError,
    SyncResponse,
    InviteMemberEvent,
    RoomMessageText
)

logger = logging.getLogger('TinyMatrixBot')


class TinyMatrixBot:
    def shell_exec(self, args, env=None):
        env_copy = os.environ.copy()
        if env:
            env_copy.update(env)
        try:
            run = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                env=env_copy,
                check=False,
                universal_newlines=True)
        except Exception as e:
            logger.error('exec %s failed: %s', args, str(e))
            return False
        output = run.stdout.rstrip()
        logger.debug('exec %s %s %s', args, env, output)
        if run.returncode != 0 or not output:
            return False
        return output

    scripts_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'scripts-enabled')
    _scripts = None

    def get_scripts(self):
        if self._scripts:
            return self._scripts
        if not os.path.isdir(self.scripts_path):
            logger.error('no scripts directory')
            return
        self._scripts = {}
        for file in os.listdir(self.scripts_path):
            script_path = os.path.join(self.scripts_path, file)
            if not os.access(script_path, os.R_OK) or not os.access(script_path, os.X_OK):
                continue
            config_output = self.shell_exec(script_path, {'CONFIG': '1'})
            if not config_output:
                continue
            logger.debug('script %s %s', script_path, config_output)
            self._scripts.update({script_path: config_output})
        return self._scripts

    async def on_error(self, response):
        logger.error(response)
        if self._client:
            await self._client.close()
        sys.exit(1)

    _initial_sync_done = False

    async def on_sync(self, _response):
        if not self._initial_sync_done:
            self._initial_sync_done = True
            for room in self._client.rooms:
                logger.info('room %s', room)
            logger.info('initial sync done, ready for work')

    accept_invites = None

    async def on_invite(self, room, event):
        if not self.accept_invites:
            user_domain = re.escape(self.user_id.split(':')[1])
            self.accept_invites = f':{user_domain}$'
        if not re.search(self.accept_invites, event.sender, re.IGNORECASE):
            logger.info('invite %s %s ignored', event.sender, room.room_id)
            return
        logger.info('invite %s %s', event.sender, room.room_id)
        await self._client.join(room.room_id)

    _last_event_timestamp = time.time() * 1000

    async def on_message(self, room, event):
        await self._client.update_receipt_marker(room.room_id, event.event_id)
        if event.sender == self._client.user_id:
            return
        if event.server_timestamp <= self._last_event_timestamp:
            return
        self._last_event_timestamp = event.server_timestamp
        scripts = self.get_scripts()
        if not scripts:
            logger.error('no scripts')
            return
        for script_path in scripts:
            if not re.search(scripts[script_path], event.body, re.IGNORECASE):
                continue
            logger.debug('trigger %s %s %s %s',
                room.room_id,
                event.sender,
                event.body,
                script_path)
            script_output = self.shell_exec(
                [script_path, event.body],
                {'TMB_ROOM_ID': room.room_id,
                'TMB_SENDER': event.sender,
                'TMB_BODY': event.body})
            if not script_output:
                continue
            await self._client.room_typing(room.room_id, True)
            for line in script_output.split('\n\n'):
                time.sleep(0.8)
                logger.debug('send %s %s', room.room_id, line)
                await self._client.room_send(
                    room_id=room.room_id,
                    message_type='m.room.message',
                    content={'msgtype': 'm.text', 'body': line})
            await self._client.room_typing(room.room_id, False)

    homeserver = None
    access_token = None
    user_id = None
    _client = None

    async def run(self):
        logger.info('connect %s', self.homeserver)
        self._client = AsyncClient(self.homeserver)
        self._client.access_token = self.access_token
        self._client.user_id = self.user_id
        self._client.device_id = 'TinyMatrixBot'
        self._client.add_response_callback(self.on_error, SyncError)
        self._client.add_response_callback(self.on_sync, SyncResponse)
        self._client.add_event_callback(self.on_invite, InviteMemberEvent)
        self._client.add_event_callback(self.on_message, RoomMessageText)
        await self._client.sync_forever(30000)
        await self._client.close()


if __name__ == '__main__':
    if 'TMB_DEBUG' in os.environ:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    try:
        TMB = TinyMatrixBot()
        TMB.homeserver = os.environ['TMB_HOMESERVER']
        TMB.access_token = os.environ['TMB_ACCESS_TOKEN']
        TMB.user_id = os.environ['TMB_USER_ID']
        if 'TMB_SCRIPTS_PATH' in os.environ:
            TMB.scripts_path = os.environ['TMB_SCRIPTS_PATH']
        if 'TMB_ACCEPT_INVITES' in os.environ:
            TMB.accept_invites = os.environ['TMB_ACCEPT_INVITES']
        asyncio.run(TMB.run())
    except Exception:
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
