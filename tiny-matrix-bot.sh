#!/bin/sh -e

eval "$( while read -r l
do
    echo "export $l"
done \
    < tiny-matrix-bot.env )"

./tiny-matrix-bot.py
