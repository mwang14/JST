#!/bin/bash
mkdir -p crawler_data/data
while IFS=' ' read -r col1 col2
do 
    node --max-old-space-size=2048 collection2.js --data types --website $col1 --outDir crawler_data/data/$col2
done <$1
