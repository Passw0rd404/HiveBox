#!/bin/bash

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <branch_name> <commit_message>"
    exit 1
fi
if git branch --list feature/"$1" 2> /dev/null 2>&1 | grep -q; then
    git checkout feature/"$1"
else
    git checkout -b feature/"$1"
fi

git add .
git commit -m "$2"
git push -u origin feature/"$1"
