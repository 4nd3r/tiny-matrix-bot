# tiny-matrix-bot

Simple (and tiny!) [Matrix](https://matrix.org) bot based on [matrix-nio](https://github.com/poljar/matrix-nio).

Bot triggers on messages matching regular expressions, runs corresponding script and sends output to room.

That's it.

Sans E2EE support, I consider this bot feature complete, but not bug free.

PRs are welcome, but no promises are given. You might be better off with fork.

## Installation

It goes roughly like this:

```
sudo pip3 install matrix-nio
git clone https://github.com/4nd3r/tiny-matrix-bot
cd tiny-matrix-bot/scripts-enabled/
find ../scripts-available/ -type f -exec ln -s {} \;
cd ..
cp tiny-matrix-bot.env.sample tiny-matrix-bot.env
vim tiny-matrix-bot.env
./tiny-matrix-bot.sh
```

## Configuration

Required environment variables:

* `TMB_HOMESERVER` = `https://example.com`
* `TMB_ACCESS_TOKEN` = `ABCDEFGH`
* `TMB_USER_ID` = `@bot:example.com`

Optional environment variables:

* `TMB_SCRIPTS_PATH` = `scripts-enabled` (this value is used when unset)
* `TMB_ACCEPT_INVITES` = `:example\.com$` (derived from `TMB_USER_ID` when unset)
* `TMB_PROXY` = `http://proxy.example.com:3128` (this value is an example, see [matrix-nio documentation](https://matrix-nio.readthedocs.io/en/latest/nio.html?highlight=proxy#nio.AsyncClient))

## Scripts

Scripts can be written in any language and they MUST have `+x` bit set.

### Setting the trigger

Bot sets an environment variable `CONFIG` and runs the script.

Manual example:

```
$ CONFIG=1 scripts-available/ping
^!?ping(!|\?)?$
```

Standard output MUST contain [Python compatible regular expression](https://docs.python.org/3.7/library/re.html#regular-expression-syntax).

Matching is case-insensitive.

### Running triggered scripts

Following environment variables are set:

* `TMB_ROOM_ID`
* `TMB_SENDER`
* `TMB_BODY`

Manual example:

```
$ TMB_BODY='1Ms 1:1' scripts-available/piibel 
Alguses lõi Jumal taeva ja maa.
```

Non-empty standard output (if exit code is zero) will be sent to room as plain text.

Empty line between non-empty lines will separate messages.

To mimic interaction, messages are sent with small delay.

## Running with systemd

Bot itself don't need to write persistent data, so read-only system access for
long running service is reasonable thing to have, hence `ProtectSystem=strict`
and friends.

However, if script wants to write persistent data, then write path MUST be
allowed using `ReadWritePaths=` in systemd unit `[Service]` section. See
[systemd documentation](https://www.freedesktop.org/software/systemd/man/systemd.exec.html)
for details.

## Previous versions

* [0c7c79e146970f19693b37b84df35a501513ff99](https://github.com/4nd3r/tiny-matrix-bot/tree/0c7c79e146970f19693b37b84df35a501513ff99)
* [3e6fa5978492020876e8a70feac12663d6530bcd](https://github.com/4nd3r/tiny-matrix-bot/tree/3e6fa5978492020876e8a70feac12663d6530bcd)
