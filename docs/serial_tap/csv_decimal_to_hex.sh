#!/bin/sh

while IFS=, read -r val1 
do
    printf "0x%.2x\n" $val1 
done


