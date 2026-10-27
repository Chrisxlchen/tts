#!/bin/zsh
# Designs candidate takes for every voice type in the library that is not a preset (see refs/voices.json).
set -e
cd "${0:A:h}"
design() { uv run --script engines/mlx_tts.py design --ref "$1" --takes 4 --describe "$2"; }
design old_m   "一位七十岁左右的老年男性，普通话，嗓音低沉略带沙哑，说话缓慢温和，有阅历感"
design old_f   "一位七十岁左右的老奶奶，普通话，声音苍老但吐字清楚，略带一点颤音，说话慢，慈祥亲切"
design mid_m   "一位四十五岁左右的中年男性，普通话标准，嗓音浑厚沉稳，说话干脆有分量"
design teen_m  "一位十五岁左右的少年男生，普通话，刚变声不久，声音清亮，说话有朝气，略带青涩"
design teen_f  "一位十五岁左右的少女，普通话，声音清脆明亮，说话轻快活泼"
design child_m "一个七八岁的小男孩，普通话，童声稚嫩清脆，说话天真，语速稍快"
design child_f "一个七八岁的小女孩，普通话，童声甜美稚嫩，说话天真可爱"
