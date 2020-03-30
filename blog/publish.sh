#!/bin/bash

set -eou pipefail

git add ./
git commit -m "update blog"
git push
