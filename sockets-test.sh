#!/bin/sh -e
cd sockets
ls | while read l
do test -S $l && date | socat - UNIX-CONNECT:$l
done
