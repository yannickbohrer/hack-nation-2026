#!/bin/bash
echo "Deploying to remote server via rsync..."
rsync -avz \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude '*.fasta' \
  --exclude '*.fna' \
  /home/yannick/Code/hack-nation/ \
  yannick@69.69.11.164:~/hack-nation/

echo "Deployment completed!"
