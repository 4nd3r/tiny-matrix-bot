#!/usr/bin/env python3

# pylint: disable=broad-except
# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=too-few-public-methods

import asyncio
import os
import re
import subprocess
import sys
import time

import nio


class TinyMatrixBot:
    homeserver = None
    access_token = None
    user_id = None
    accept_invites = None
    scripts_path = None
    proxy = None
    _scripts = None

    def __init__(self):
        required_env_vars = ['TMB_HOMESERVER', 'TMB_ACCESS_TOKEN', 'TMB_USER_ID']
        for env_var in os.environ:
            if not env_var.startswith('TMB_'):
                continue
            if env_var in required_env_vars:
                required_env_vars.remove(env_var)
            setattr(self, env_var.lower()[4:], os.environ[env_var])
        if required_env_vars:
            raise Exception('missing {}'.format(', '.join(required_env_vars)))
        if self.accept_invites is None:
            self.accept_invites = ':{}$'.format(re.escape(self.user_id.split(':')[1]))
        if self.scripts_path is None:
            self.scripts_path = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), 'scripts-enabled')
        if os.path.isdir(self.scripts_path):
            self._scripts = self._load_scripts(self.scripts_path)

    def _load_scripts(self, scripts_path):
        scripts = {}
        for file in os.listdir(scripts_path):
            script_path = os.path.join(self.scripts_path, file)
            script_name = os.path.basename(script_path)
            if script_name[0] == '.':
                continue
            if not os.access(script_path, os.R_OK):
                print(f'script {script_name} is not readable')
                continue
            if not os.access(script_path, os.X_OK):
                print(f'script {script_name} is not executable')
                continue
            script_regex = self._run_script(script_path, {'CONFIG': '1'})
            if not script_regex:
                print(f'script {script_name} loading failed')
                continue
            print(f'script {script_name} loaded')
            scripts.update({script_path: script_regex})
        return scripts

    def _run_script(self, script_path, script_env=None):
        script_name = os.path.basename(script_path)
        print(f'running script {script_name}')
        env = os.environ.copy()
        if script_env:
            env.update(script_env)
        try:
            run = subprocess.run(
                [script_path],
                env=env,
                stdout=subprocess.PIPE,
                check=False,
                universal_newlines=True)
        except Exception:
            print('  failed with exception')
            return False
        if run.returncode != 0:
            print('  non-zero exit code')
            return False
        output = run.stdout.strip()
        if not output:
            print('  no output')
            return False
        return output

    _client = None

    async def run(self):
        print(f'connecting to {self.homeserver}')
        self._client = nio.AsyncClient(self.homeserver, proxy=self.proxy)
        self._client.access_token = self.access_token
        self._client.user_id = self.user_id
        self._client.device_id = 'TinyMatrixBot'
        self._client.add_response_callback(self._on_error, nio.SyncError)
        self._client.add_response_callback(self._on_sync, nio.SyncResponse)
        self._client.add_event_callback(self._on_invite, nio.InviteMemberEvent)
        self._client.add_event_callback(self._on_message, nio.RoomMessageText)
        await self._client.sync_forever(timeout=30000)
        await self._client.close()

    async def _on_error(self, response):
        if self._client:
            await self._client.close()
        print(response)
        print('got error, exiting')
        sys.exit(1)

    _initial_sync_done = False

    async def _on_sync(self, _response):
        if not self._initial_sync_done:
            self._initial_sync_done = True
            for room_id in self._client.rooms:
                print(f'joined room {room_id}')
            print('initial sync done, ready for work')

    async def _on_invite(self, room, event):
        if not re.search(self.accept_invites, event.sender, re.IGNORECASE):
            print(f'invite from {event.sender} to {room.room_id} rejected')
            await self._client.room_leave(room.room_id)
        else:
            print(f'invite from {event.sender} to {room.room_id} accepted')
            await self._client.join(room.room_id)

    _last_event_timestamp = time.time() * 1000

    async def _on_message(self, room, event):
        await self._client.update_receipt_marker(room.room_id, event.event_id)
        if event.sender == self._client.user_id:
            return
        if event.server_timestamp <= self._last_event_timestamp:
            return
        self._last_event_timestamp = event.server_timestamp
        if not self._scripts:
            print('no scripts')
            return
        for script_path in self._scripts:
            if not re.search(self._scripts[script_path], event.body, re.IGNORECASE):
                continue
            script_name = os.path.basename(script_path)
            print(f'script {script_name} triggered in {room.room_id}')
            script_output = self._run_script(
                script_path,
                {'TMB_ROOM_ID': room.room_id,
                 'TMB_SENDER': event.sender,
                 'TMB_BODY': event.body})
            if not script_output:
                continue
            print(f'sending message to {room.room_id}')
            await self._client.room_typing(room.room_id, True)
            for message_body in script_output.split('\n\n'):
                time.sleep(0.8)
                await self._client.room_send(
                    room_id=room.room_id,
                    message_type='m.room.message',
                    content={'msgtype': 'm.text', 'body': message_body})
            await self._client.room_typing(room.room_id, False)


if __name__ == '__main__':
    asyncio_debug = False
    if 'TMB_DEBUG' in os.environ:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        asyncio_debug = True
    try:
        TMB = TinyMatrixBot()
        asyncio.run(TMB.run(), debug=asyncio_debug)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(e)
        print('got exception, exiting')
        sys.exit(1)
