#!/bin/bash
set -e

echo "gpu_id,pid,user"
for GPU in $(nvidia-smi --query-gpu=index --format=csv,noheader,nounits | sed '/^$/d'); do
    nvidia-smi -i $GPU --query-compute-apps=pid --format=csv,noheader,nounits | while read PID; do
        USER=$(ps -o user= -p $PID)
        echo "$GPU,$PID,$USER"
    done
done
