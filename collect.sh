#!/bin/bash

while IFS=' ' read -r col1 col2
do 
    node --max-old-space-size=16384 collection2.js $col1 $1/$col2
done <websites.txt
