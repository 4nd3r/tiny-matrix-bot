# tiny-matrix-bot

simple [matrix](https://matrix.org) bot based on [matrix-python-sdk](https://github.com/matrix-org/matrix-python-sdk) with no support and no warranty.

```
sudo apt install python3 python3-requests
git clone https://github.com/4nd3r/tiny-matrix-bot
git clone https://github.com/matrix-org/matrix-python-sdk
cd tiny-matrix-bot
ln -s ../matrix-python-sdk/matrix_client
cp tiny-matrix-bot.cfg.sample tiny-matrix-bot.cfg
vim tiny-matrix-bot.cfg
cp tiny-matrix-bot.service /etc/systemd/system
vim /etc/systemd/system/tiny-matrix-bot.service
systemctl enable tiny-matrix-bot
systemctl start tiny-matrix-bot
systemctl stop tiny-matrix-bot
```

## notable forks

  * [8go/tiny-matrix-bot](https://github.com/8go/tiny-matrix-bot)
