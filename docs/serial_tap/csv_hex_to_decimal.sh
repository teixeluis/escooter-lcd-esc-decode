#!/bin/sh

while IFS=, read -r value 
do
    printf "%d\n" 0x$value 
done


