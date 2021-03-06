# tiny-matrix-bot

Simple (and tiny!) [Matrix](https://matrix.org) bot based on [matrix-nio](https://github.com/poljar/matrix-nio).

Bot triggers on messages matching regular expressions, executes corresponding script and sends output to room.

That's it.

Sans E2EE support, I consider this bot feature complete, but not bug free.

Code could be better, but I'll try to "improve" it as I get better with Python 😏

PRs are welcome, but no promises are given. You might be better off with fork 🙏

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

Optional environment variables with defaults:

* `TMB_SCRIPTS_PATH` = `scripts-enabled`
* `TMB_ACCEPT_INVITES` = `:example\.com$` (derived from `TMB_USER_ID` when unset)

## Scripts

Scripts can be written in any language and they MUST have execute bit set (`chmod +x`).

### Trigger

To get the trigger, bot sets environment variable `CONFIG` and executes script.

Standard output MUST contain
[Python compatible regular expression](https://docs.python.org/3.7/library/re.html#regular-expression-syntax),
which will execute (trigger) the script.

Matching is case-insensitive.

### Executing

Following environment variables are set:

* `TMB_ROOM_ID`
* `TMB_SENDER`
* `TMB_BODY`

For compatibility message body is also given as first argument. I'll probably remove this in future.

Standard output (if exit code is zero) will be sent to room as plain text.

Empty lines will separate messages.

To mimic interaction, messages are sent to room with small delay 🤖

## Previous version

[matrix-python-sdk](https://github.com/matrix-org/matrix-python-sdk) based version's last commit is
[3e6fa5978492020876e8a70feac12663d6530bcd](https://github.com/4nd3r/tiny-matrix-bot/tree/3e6fa5978492020876e8a70feac12663d6530bcd).
