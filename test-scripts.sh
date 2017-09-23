#!/bin/sh
find scripts | while read -r l
do file "$l" | grep -q 'POSIX shell script' && shellcheck "$l"
done
