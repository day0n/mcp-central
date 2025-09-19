"""
多音字拼音标注工具

为中文歌词添加拼音标注，特别是多音字的消歧义处理
"""

import re
from typing import Dict, List, Tuple, Optional

# 常见多音字及其读音映射
POLYPHONIC_CHARS = {
    '重': {
        'zhòng': ['重要', '重点', '重量', '重大', '重新', '重视', '严重', '沉重', '厚重'],
        'chóng': ['重复', '重叠', '重来', '重做', '重说']
    },
    '中': {
        'zhōng': ['中国', '中心', '中间', '中午', '中等', '中年', '中央', '其中', '心中', '手中', '眼中'],
        'zhòng': ['中毒', '中奖', '中箭', '中计', '命中', '打中', '说中']
    },
    '长': {
        'cháng': ['长短', '长度', '长时间', '长远', '长期', '很长', '长长的', '成长', '长大'],
        'zhǎng': ['长辈', '长老', '长官', '长者', '队长', '班长', '校长', '市长', '省长']
    },
    '行': {
        'xíng': ['行走', '行动', '行为', '执行', '进行', '可行', '不行', '行得通', '行李'],
        'háng': ['银行', '行业', '行列', '商行', '同行', '内行', '外行', '排行']
    },
    '好': {
        'hǎo': ['好人', '好事', '好坏', '很好', '美好', '良好', '好看', '好听', '问好'],
        'hào': ['好奇', '好学', '爱好', '好战', '好胜', '好动', '好客']
    },
    '还': {
        'hái': ['还有', '还是', '还要', '还会', '还能', '还在', '还没', '还可以'],
        'huán': ['还钱', '还债', '归还', '还原', '还击', '偿还', '交还', '送还']
    },
    '为': {
        'wéi': ['为了', '为什么', '为人', '为民', '为国', '认为', '因为', '作为'],
        'wèi': ['为难', '为虎作伥']
    },
    '更': {
        'gèng': ['更加', '更好', '更多', '更大', '更新', '更换', '变更', '修更'],
        'gēng': ['更夫', '三更', '五更', '更鼓', '打更']
    },
    '看': {
        'kàn': ['看见', '看到', '观看', '查看', '看书', '看电影', '看起来', '好看'],
        'kān': ['看守', '看护', '看门', '看家', '看管']
    },
    '过': {
        'guò': ['过去', '过来', '经过', '通过', '超过', '过分', '过度', '太过'],
        'guo': ['走过', '说过', '做过', '见过', '听过', '用过', '吃过']  # 轻声
    },
    '得': {
        'dé': ['得到', '获得', '得意', '心得', '得力', '得体', '得当', '难得'],
        'děi': ['得了', '得去', '得做', '得说', '不得不', '总得', '必得'],
        'de': ['跑得快', '说得好', '做得对', '来得及', '看得见']  # 轻声
    },
    '要': {
        'yào': ['要求', '需要', '重要', '主要', '想要', '要是', '不要', '只要'],
        'yāo': ['要求', '要挟']  # 较少见
    },
    '都': {
        'dōu': ['都是', '都有', '都在', '都能', '都会', '全都', '什么都'],
        'dū': ['首都', '都市', '都城', '古都', '京都', '建都', '定都']
    },
    '地': {
        'dì': ['土地', '地方', '地球', '大地', '田地', '当地', '各地', '外地'],
        'de': ['静静地', '慢慢地', '轻轻地', '快乐地', '认真地']  # 轻声
    },
    '会': {
        'huì': ['会议', '学会', '社会', '机会', '开会', '聚会', '会面', '会见'],
        'kuài': ['会计', '财会']
    },
    '着': {
        'zhe': ['走着', '说着', '做着', '拿着', '带着', '看着', '听着'],  # 轻声
        'zháo': ['着火', '着急', '着凉', '着迷', '睡着了'],
        'zhuó': ['着手', '着力', '着重', '着眼', '着想']
    },
    '上': {
        'shàng': ['上面', '上边', '向上', '上升', '上学', '上班', '上车', '马上', '晚上'],
        'shǎng': []  # 较少见，如"上声"
    },
    '下': {
        'xià': ['下面', '下边', '向下', '下降', '下学', '下班', '下车', '一下', '天下'],
        'xia': []  # 轻声用法很少
    }
}

# 常见词语的固定读音
FIXED_PRONUNCIATIONS = {
    # 常见短语的固定读音
    '重要': '重(zhòng)要',
    '重新': '重(zhòng)新',
    '重复': '重(chóng)复',
    '中国': '中(zhōng)国',
    '中毒': '中(zhòng)毒',
    '长大': '长(zhǎng)大',
    '长短': '长(cháng)短',
    '行走': '行(xíng)走',
    '银行': '银行(háng)',
    '好人': '好(hǎo)人',
    '爱好': '爱好(hào)',
    '还有': '还(hái)有',
    '归还': '归还(huán)',
    '为了': '为(wéi)了',
    '更加': '更(gèng)加',
    '看见': '看(kàn)见',
    '看守': '看(kān)守',
    '过去': '过(guò)去',
    '得到': '得(dé)到',
    '要求': '要(yào)求',
    '都是': '都(dōu)是',
    '首都': '首都(dū)',
    '土地': '土地(dì)',
    '慢慢地': '慢慢地(de)',
    '学会': '学会(huì)',
    '会计': '会(kuài)计'
}


def annotate_polyphonic_lyrics(lyrics: str) -> str:
    """
    为歌词中的多音字添加拼音标注

    Args:
        lyrics: 原始歌词

    Returns:
        添加了拼音标注的歌词
    """
    if not lyrics.strip():
        return lyrics

    # 分行处理
    lines = lyrics.split('\n')
    annotated_lines = []

    for line in lines:
        if not line.strip():
            annotated_lines.append(line)
            continue

        # 跳过歌曲结构标记 [Intro], [Verse] 等
        if re.match(r'^\s*\[.*\]\s*$', line):
            annotated_lines.append(line)
            continue

        annotated_line = _annotate_line(line)
        annotated_lines.append(annotated_line)

    return '\n'.join(annotated_lines)


def _annotate_line(line: str) -> str:
    """标注单行歌词"""
    result = line

    # 首先处理固定词组
    for phrase, annotation in FIXED_PRONUNCIATIONS.items():
        if phrase in result:
            result = result.replace(phrase, annotation)

    # 然后处理单个多音字
    for char, pronunciations in POLYPHONIC_CHARS.items():
        if char in result:
            result = _annotate_character(result, char, pronunciations)

    return result


def _annotate_character(text: str, char: str, pronunciations: Dict[str, List[str]]) -> str:
    """为单个多音字添加标注"""
    # 如果字符已经被标注过（包含括号），跳过
    pattern = f'{re.escape(char)}\\([^)]+\\)'
    if re.search(pattern, text):
        return text

    # 寻找最佳匹配的读音
    best_pronunciation = _find_best_pronunciation(text, char, pronunciations)

    if best_pronunciation:
        # 替换第一个未标注的字符
        # 使用简单的替换，避免复杂的lookbehind
        char_index = text.find(char)
        if char_index != -1:
            # 检查这个字符是否已经在括号内
            before_char = text[:char_index]
            after_char = text[char_index+1:]

            # 简单检查：如果字符前面有未闭合的括号，跳过
            if before_char.count('(') > before_char.count(')'):
                return text

            replacement = f'{char}({best_pronunciation})'
            text = text[:char_index] + replacement + after_char

    return text


def _find_best_pronunciation(text: str, char: str, pronunciations: Dict[str, List[str]]) -> Optional[str]:
    """根据上下文找到最佳读音"""

    # 在文本中查找包含目标字符的词语
    char_index = text.find(char)
    if char_index == -1:
        return None

    # 提取周围的上下文（前后各3个字符）
    start = max(0, char_index - 3)
    end = min(len(text), char_index + 4)
    context = text[start:end]

    # 为每个读音计算匹配分数
    scores = {}
    for pronunciation, words in pronunciations.items():
        score = 0
        for word in words:
            if word in context:
                score += len(word) * 2  # 长词匹配权重更高
            elif any(w in context for w in word):
                score += 1  # 部分匹配
        scores[pronunciation] = score

    # 返回得分最高的读音
    if scores:
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best

    # 如果没有明确匹配，返回最常用的读音（通常是第一个）
    return list(pronunciations.keys())[0] if pronunciations else None


def get_polyphonic_stats(lyrics: str) -> Dict[str, List[str]]:
    """
    获取歌词中多音字的统计信息

    Args:
        lyrics: 歌词文本

    Returns:
        多音字及其在歌词中出现的位置统计
    """
    stats = {}

    for char in POLYPHONIC_CHARS:
        if char in lyrics:
            # 找到所有出现位置
            positions = []
            start = 0
            while True:
                pos = lyrics.find(char, start)
                if pos == -1:
                    break

                # 获取周围上下文
                context_start = max(0, pos - 5)
                context_end = min(len(lyrics), pos + 6)
                context = lyrics[context_start:context_end]

                positions.append({
                    'position': pos,
                    'context': context,
                    'line_num': lyrics[:pos].count('\n') + 1
                })
                start = pos + 1

            if positions:
                stats[char] = positions

    return stats


# 为了简化使用，添加一个快速标注函数
def quick_annotate(lyrics: str) -> str:
    """快速标注歌词中的多音字（简化版本）"""
    if not lyrics:
        return lyrics

    # 只处理最常见的多音字
    common_annotations = {
        '重要': '重(zhòng)要',
        '重新': '重(zhòng)新',
        '重复': '重(chóng)复',
        '中国': '中(zhōng)国',
        '长大': '长(zhǎng)大',
        '成长': '成长(zhǎng)',
        '行走': '行(xíng)走',
        '银行': '银行(háng)',
        '还有': '还(hái)有',
        '还是': '还(hái)是',
        '归还': '归还(huán)',
        '为了': '为(wéi)了',
        '更加': '更(gèng)加',
        '都是': '都(dōu)是',
        '首都': '首都(dū)'
    }

    result = lyrics
    for word, annotated in common_annotations.items():
        result = result.replace(word, annotated)

    return result


if __name__ == "__main__":
    # 测试代码
    test_lyrics = """[Intro]
夜深了，思绪又开始泛滥

[Verse]
走过这么多路，回头看那些伤
有些痛不会忘，像刻在心上的疤
为了梦想我们都在拼搏奋斗
重新开始，让生活更加美好

[Chorus]
在这个中国大地上成长
我们的心中都有一个银行
存着那些美好的回忆
还有对未来的希望

[Outro]
无论走到哪里都不会忘记
这里是我们的根，我们的家"""

    print("原始歌词:")
    print(test_lyrics)
    print("\n" + "="*50)

    print("标注后的歌词:")
    annotated = annotate_polyphonic_lyrics(test_lyrics)
    print(annotated)

    print("\n" + "="*50)
    print("多音字统计:")
    stats = get_polyphonic_stats(test_lyrics)
    for char, positions in stats.items():
        print(f"'{char}': {len(positions)}次")
        for pos in positions:
            print(f"  行{pos['line_num']}: {pos['context']}")