#!/bin/zsh
# Designs candidate takes for every library voice that is not a preset (see refs/voices.json).
# With arguments, only those voices: ./design_voices.sh young_f2 young_f3
set -e
cd "${0:A:h}"
WANT=" $* "
design() {
  [[ $# -eq 0 || "$WANT" == "  " || "$WANT" == *" $1 "* ]] || return 0
  uv run --script engines/mlx_tts.py design --ref "$1" --takes 4 --describe "$2"
}
design old_m   "一位七十岁左右的老年男性，普通话，嗓音低沉略带沙哑，说话缓慢温和，有阅历感"
design old_f   "一位七十岁左右的老奶奶，普通话，声音苍老但吐字清楚，略带一点颤音，说话慢，慈祥亲切"
design mid_m   "一位四十五岁左右的中年男性，普通话标准，嗓音浑厚沉稳，说话干脆有分量"
design teen_m  "一位十五岁左右的少年男生，普通话，刚变声不久，声音清亮，说话有朝气，略带青涩"
design teen_f  "一位十五岁左右的少女，普通话，声音清脆明亮，说话轻快活泼"
design child_m "一个七八岁的小男孩，普通话，童声稚嫩清脆，说话天真，语速稍快"
design child_f "一个七八岁的小女孩，普通话，童声甜美稚嫩，说话天真可爱"
# Variants, so a book's main characters of the same Voice Type can each get their own voice
design young_f2 "一位二十岁出头的年轻女子，普通话，声音温柔甜润，说话轻柔细腻，带着关切"
design young_f3 "一位二十多岁的年轻女剑客，普通话，声音清冷干净，语气平静克制，略带疏离感"
design young_f4 "一位十八九岁的年轻姑娘，普通话，声音明亮灵动，说话俏皮活泼，带点狡黠"
design young_f5 "一位二十多岁的年轻女子，普通话，声音华丽而有威仪，说话从容笃定，略带高傲"
design young_m2 "一位二十岁左右的年轻男子，普通话，声音清朗干净，说话从容温和，带一点少年意气"
design young_m3 "一位二十多岁的年轻男子，普通话，嗓音低沉冷峻，说话简短有力"
design teen_f2  "一位十四五岁的小姑娘，普通话，声音软糯清甜，说话乖巧，偶尔撒娇"
design young_f6 "一位二十多岁的年轻女子，普通话，声音干练爽利，带着英气，说话果断利落"
design young_f7 "一位二十多岁的年轻女子，普通话，声音慵懒柔媚，说话不紧不慢，尾音带一丝笑意"
design young_f8 "一位二十七八岁的年轻女子，普通话，声音沉静低柔，成熟知性，说话不疾不徐"
design young_m4 "一位二十多岁的年轻男子，普通话，嗓音略带沙哑，语气慵懒随意，带点玩世不恭"
design young_m5 "一位二十多岁的年轻男子，普通话，声音洪亮粗犷，说话大大咧咧，带点咋呼"
