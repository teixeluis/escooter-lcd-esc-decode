#!/bin/sh

while IFS=, read -r val1 val2 val3 val4 val5 val6 val7 val8 val9 val10 val11 val12 val13 val14 
do
    printf "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n" 0x$val1 0x$val2 0x$val3 0x$val4 0x$val5 0x$val6 0x$val7 0x$val8 0x$val9 0x$val10 0x$val11 0x$val12 0x$val13 0x$val14 
done


