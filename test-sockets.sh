#!/bin/sh
find sockets | while read -r l
do test -S "$l" && date | socat - "UNIX-CONNECT:$l"
done
