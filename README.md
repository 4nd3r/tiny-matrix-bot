# tiny-matrix-bot

Simple (and tiny!) [Matrix](https://matrix.org)
bot based on [matrix-nio](https://github.com/poljar/matrix-nio).

Bot triggers on messages matching regular expressions, executes related script
and sends output to room.

That's it.

Sans E2E support, I consider this bot feature complete.

Code could be better, but I'll try to "improve" it as I get better with Python 😏

PRs are welcome, but no promises are given. You might be better off with fork 🙏

## Configuration

Required environment variables:

* `TMB_HOMESERVER` = `https://example.com`
* `TMB_ACCESS_TOKEN` = `ABCDEFGH`
* `TMB_USER_ID` = `@bot:example.com`

Optional environment variables with defaults:

* `TMB_SCRIPTS_PATH` = `scripts-enabled`
* `TMB_ACCEPT_INVITES` = `:example\.com$` (derived from `TMB_USER_ID` when unset)

## Scripts

### Trigger

Bot sets environment variable `CONFIG` and executes script.

Script output MUST contain
[Python compatible regular expression](https://docs.python.org/3.7/library/re.html#regular-expression-syntax),
which will execute or "trigger" script.

Matching is case-insensitive.

### Executing

Following environment variables are set:

* `TMB_ROOM_ID`
* `TMB_SENDER`
* `TMB_BODY`

For compatibility (fow now), message body is also given as first argument.

Execution output (if exit code is zero) will be sent to room as plain text.

Empty lines will separate messages.

To mimic interaction, messages are sent to room with small delay 🤖

## Previous version

[matrix-python-sdk](https://github.com/matrix-org/matrix-python-sdk) based version's last commit is
[3e6fa5978492020876e8a70feac12663d6530bcd](https://github.com/4nd3r/tiny-matrix-bot/tree/3e6fa5978492020876e8a70feac12663d6530bcd).
