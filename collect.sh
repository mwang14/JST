#!/bin/bash

while IFS=' ' read -r col1 col2
do 
    node collection2.js $col1 $col2
done <websites.txt
