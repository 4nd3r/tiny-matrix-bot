#!/bin/sh
cd sockets || exit
ls | while read l
do test -S $l && date | socat - UNIX-CONNECT:$l
done
