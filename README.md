# tiny-matrix-bot

simple and dirty matrix.org bot based on matrix-python-sdk

~~no manual,~~ no support, no warranty

pull requests are welcome!

```
sudo apt-get install python3 python3-requests
git clone https://github.com/4nd3r/tiny-matrix-bot
git clone https://github.com/matrix-org/matrix-python-sdk
cd tiny-matrix-bot
ln -s ../matrix-python-sdk/matrix_client
cp tiny-matrix-bot.cfg.sample tiny-matrix-bot.cfg
vim tiny-matrix-bot.cfg
screen ./tiny-matrix-bot.py
```

scripts must have execute bit - `chmod +x`
