import json
import os
from collections import Counter

def determine_alignment(left, right, mid):
    """
    Determine alignment based on Left, Right, Mid.
    - Justified: L <= 0, R <= 0, M = 0
    - Center: L > 0, R > 0, M = 0
    - Left: M < 0
    - Right: M > 0
    """
    if -0.5 < mid < 0.5:  # Consider mid ≈ 0
        if left <= 0 and right <= 0:
            return "Justified"
        elif left > 0 and right > 0:
            return "Center"
    elif mid < 0:
        return "Left"
    elif mid > 0:
        return "Right"
    return "Unknown"

def get_CaseStyle(text):
    """
    Determine CaseStyle of text (simplified implementation).
    - 2: All uppercase
    - 1: All titlecase
    - 0: Otherwise
    """
    if not text:
        return 0
    if text.isupper():
        return 2
    if text.islower():
        return 0
    return 0

def process_json(input_path):
    """
    Read JSON file, add Align, remove LineWidth, Coord, and BracketStatus (except for general),
    return modified data.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"File {input_path} không tồn tại")

    with open(input_path, 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)

    modified_data = data.copy()

    if 'lines' in modified_data:
        for line in modified_data['lines']:
            left = line.get('Left', 0)
            right = line.get('Right', 0)
            mid = line.get('Mid', 0)
            line['Align'] = determine_alignment(left, right, mid)
            line.pop('LineWidth', None)
            line.pop('Coord', None)
            line.pop('BracketStatus', None)

    return modified_data

def is_same_fontsize(fs1, fs2, fs_last1=None, fs_first2=None):
    """
    Check if font sizes are considered the same (|diff| < 0.3).
    """
    comparisons = [
        abs(fs1 - fs2),
        abs(fs1 - fs_last1) if fs_last1 is not None else float('inf'),
        abs(fs_first2 - fs2) if fs_first2 is not None else float('inf'),
        abs(fs_last1 - fs_first2) if fs_last1 is not None and fs_first2 is not None else float('inf')
    ]
    return any(diff < 0.3 for diff in comparisons if diff != float('inf'))

def is_same_casestyle(cs1, cs2, cs_last1=None, cs_first2=None):
    """
    Check if case styles are considered the same.
    """
    comparisons = [
        (cs1, cs2),
        (cs1, cs_last1) if cs_last1 is not None else (None, None),
        (cs_first2, cs2) if cs_first2 is not None else (None, None),
        (cs_last1, cs_first2) if cs_last1 is not None and cs_first2 is not None else (None, None)
    ]
    return any(a == b for a, b in comparisons if a is not None and b is not None)

def is_same_style(st1, st2, st_last1=None, st_first2=None):
    """
    Check if styles are considered the same.
    """
    comparisons = [
        (st1, st2),
        (st1, st_last1) if st_last1 is not None else (None, None),
        (st_first2, st2) if st_first2 is not None else (None, None),
        (st_last1, st_first2) if st_last1 is not None and st_first2 is not None else (None, None)
    ]
    return any(a == b for a, b in comparisons if a is not None and b is not None)

# Hàm can_merge (sửa việc đọc CaseStyle)
def can_merge(line1, line2, line_height2):
    """
    Check if two lines can be merged based on specified conditions.
    """
    # Basic condition: MarkerText[1] must be null
    if line2.get('MarkerText') is not None:
        return False

    # Same FontSize
    fs1 = line1.get('FontSize', 0)
    fs2 = line2.get('FontSize', 0)
    fs_last1 = line1.get('LastWord', {}).get('FontSize', fs1)
    fs_first2 = line2.get('FirstWord', {}).get('FontSize', fs2)
    if not is_same_fontsize(fs1, fs2, fs_last1, fs_first2):
        return False

    # Same CaseStyle or Same Style
    cs1 = line1.get('CaseStyle', 0)
    cs2 = line2.get('CaseStyle', 0)
    cs_last1 = line1.get('LastWord', {}).get('CaseStyle', cs1)
    cs_first2 = line2.get('FirstWord', {}).get('CaseStyle', cs2)
    st1 = line1.get('Style', '000')
    st2 = line2.get('Style', '000')
    st_last1 = line1.get('LastWord', {}).get('Style', st1)
    st_first2 = line2.get('FirstWord', {}).get('Style', st2)
    if not (is_same_casestyle(cs1, cs2, cs_last1, cs_first2) or is_same_style(st1, st2, st_last1, st_first2)):
        return False

    # Top[1] < Top[0] + 0.3
    top1 = line1.get('Top', 0)
    top2 = line2.get('Top', 0)
    if top2 >= top1 + 0.3:
        return False

    # Top[1] < 2 * LineHeight[1]
    if top2 >= 2 * line_height2:
        return False

    # Alignment conditions
    align1 = line1.get('Align', 'Unknown')
    align2 = line2.get('Align', 'Unknown')
    weight = fs1  # Assume Weight = FontSize[0]
    first_word2_width = line2.get('FirstWord', {}).get('width', 0)

    if (align1 == 'Center' and align2 == 'Center') or \
       (align1 == 'Justified' and align2 == 'Justified') or \
       (align1 == 'Right' and align2 == 'Right'):
        return True
    elif align2 == 'Right':
        margin_left1 = line1.get('Left', 0)
        if margin_left1 < first_word2_width - weight * 1.3:
            return True
    else:
        extra_space1 = line1.get('Right', 0)
        if extra_space1 < first_word2_width - weight * 1.3:
            return True
    return False

# Hàm merge_group (sửa việc ghi CaseStyle)
def merge_group(group):
    """
    Merge a group of lines into a single line with specified attributes.
    """
    if not group:
        return None

    # Merge Text
    merged_text = ' '.join(g['Text'] for g in group)

    # MarkerText and MarkerFormat from first
    marker_text = group[0].get('MarkerText')
    marker_format = group[0].get('MarkerFormat')

    # CaseStyle: Recalculate from merged_text
    case_style = get_CaseStyle(merged_text)

    # Style: Min of each digit
    styles = [g.get('Style', '000') for g in group]
    min_b = min(int(s[0]) for s in styles)
    min_i = min(int(s[1]) for s in styles)
    min_u = min(int(s[2]) for s in styles)
    style = f"{min_b}{min_i}{min_u}"

    # FirstWord from first, LastWord from last
    first_word = group[0].get('FirstWord')
    last_word = group[-1].get('LastWord')

    # FontSize: Average
    font_sizes = [g.get('FontSize', 0) for g in group]
    font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 0

    # Left: Min
    lefts = [g.get('Left', 0) for g in group]
    left = min(lefts)

    # Top: From first
    top = group[0].get('Top', 0)

    # Right: Min
    rights = [g.get('Right', 0) for g in group]
    right = min(rights)

    # Mid: Average
    mids = [g.get('Mid', 0) for g in group]
    mid = sum(mids) / len(mids) if mids else 0

    # Recalculate Align
    align = determine_alignment(left, right, mid)

    return {
        "Text": merged_text,
        "MarkerText": marker_text,
        "MarkerFormat": marker_format,
        "CaseStyle": case_style,
        "Style": style,
        "FirstWord": first_word,
        "LastWord": last_word,
        "FontSize": font_size,
        "Left": left,
        "Top": top,
        "Right": right,
        "Mid": mid,
        "Align": align
    }

def merge_lines(modified_path):
    """
    Merge lines in the JSON file based on specified conditions.
    """
    if not os.path.exists(modified_path):
        raise FileNotFoundError(f"File {modified_path} không tồn tại")

    with open(modified_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    lines = data.get('lines', [])
    if not lines:
        return data

    merged_lines = []
    group = [lines[0]]

    for i in range(1, len(lines)):
        line1 = group[-1]  # Last line in current group
        line2 = lines[i]
        line_height2 = line2.get('FontSize', 12)  # Assume LineHeight ≈ FontSize

        if can_merge(line1, line2, line_height2):
            group.append(line2)
        else:
            # Merge current group and start new group
            merged = merge_group(group)
            if merged:
                merged['Line'] = len(merged_lines) + 1
                merged_lines.append(merged)
            group = [line2]

    # Merge final group
    merged = merge_group(group)
    if merged:
        merged['Line'] = len(merged_lines) + 1
        merged_lines.append(merged)

    data['lines'] = merged_lines
    return data