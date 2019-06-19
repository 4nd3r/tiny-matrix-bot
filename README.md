# tiny-matrix-bot

simple and dirty [matrix](https://matrix.org) bot based on [matrix-python-sdk](https://github.com/matrix-org/matrix-python-sdk)

no support, no warranty, works for me

scripts must have execute bit - `chmod +x`

```
sudo apt install python3 python3-requests
git clone https://github.com/4nd3r/tiny-matrix-bot
git clone https://github.com/matrix-org/matrix-python-sdk
cd tiny-matrix-bot
mkdir run
ln -s ../matrix-python-sdk/matrix_client
cp tiny-matrix-bot.cfg.sample tiny-matrix-bot.cfg
vim tiny-matrix-bot.cfg
cp tiny-matrix-bot.service /etc/systemd/system
systemctl enable tiny-matrix-bot
systemctl start tiny-matrix-bot
systemctl reload tiny-matrix-bot
systemctl stop tiny-matrix-bot
```
