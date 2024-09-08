#!/bin/bash

# 激活虛擬環境
#source pelican-env/bin/activate

# 生成靜態文件
pelican content -o docs -s pelicanconf.py
git add .
echo "Enter commit message:"
read commit_message
git config --global user.name "Chris Hsu"
git commit -m "$commit_message"
git push origin main

echo "Deployment complete!"