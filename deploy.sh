#!/bin/bash

# 激活虛擬環境
source pelican-env/bin/activate

# 生成靜態文件
pelican content -o docs -s pelicanconf.py

# 添加變更到 Git
#git add .

# 提交變更
#echo "Enter commit message:"
#read commit_message
#git commit -m "$commit_message"
git commit -a

# 推送到 GitHub
git push origin main

echo "Deployment complete!"