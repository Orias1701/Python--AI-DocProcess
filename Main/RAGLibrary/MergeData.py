import json
import os
from collections import Counter  # Để tính CaseStyle nếu cần
# Giả định rằng get_CaseStyle và determine_alignment từ ExtractData.py, bạn có thể import nếu cần
# Ở đây tôi sẽ tái hiện ngắn gọn nếu cần

def determine_alignment(left, right, mid):
    """
    Xác định kiểu căn lề dựa trên Left, Right, Mid.
    - Justified: L <= 0, R <= 0, M = 0
    - Center: L > 0, R > 0, M = 0
    - Left: M < 0
    - Right: M > 0
    """
    if mid > -0.5 and mid < 0.5:
        if left <= 0 and right <= 0:
            return "Justified"
        elif left > 0 and right > 0:
            return "Center"
    elif mid < 0:
        return "Left"
    elif mid > 0:
        return "Right"
    return "Unknown"  # Trường hợp không xác định

def process_json(input_path):
    """
    Đọc file JSON, thêm thuộc tính Align, bỏ LineWidth, Coord và BracketStatus (trừ bản ghi chung),
    trả về dữ liệu đã chỉnh sửa.
    """
    # Kiểm tra file đầu vào tồn tại
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"File {input_path} không tồn tại")

    # Đọc file JSON
    with open(input_path, 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)

    # Sao chép dữ liệu để chỉnh sửa
    modified_data = data.copy()

    # Xử lý các bản ghi trong 'lines'
    if 'lines' in modified_data:
        for line in modified_data['lines']:
            # Xác định căn lề
            left = line.get('Left', 0)
            right = line.get('Right', 0)
            mid = line.get('Mid', 0)
            line['Align'] = determine_alignment(left, right, mid)

            # Xóa LineWidth, Coord và BracketStatus
            line.pop('LineWidth', None)
            line.pop('Coord', None)
            line.pop('BracketStatus', None)

    return modified_data

def is_same_fontsize(fs1, fs2, fs_last1=None, fs_first2=None, fs_last2=None):
    # Same FontSize: Kiểm tra |fs_a - fs_b| < 0.3 với các cặp
    if abs(fs1 - fs2) < 0.3:
        return True
    if fs_last1 and abs(fs1 - fs_last1) < 0.3:
        return True
    if fs_first2 and abs(fs_first2 - fs2) < 0.3:
        return True
    if fs_last1 and fs_first2 and abs(fs_last1 - fs_first2) < 0.3:
        return True
    return False

def is_same_casestyle(cs1, cs2, cs_last1=None, cs_first2=None, cs_last2=None):
    # Same CaseStyle: So sánh các cặp
    if cs1 == cs2:
        return True
    if cs_last1 and cs1 == cs_last1:
        return True
    if cs_first2 and cs_first2 == cs2:
        return True
    if cs_last1 and cs_first2 and cs_last1 == cs_first2:
        return True
    return False

def is_same_style(st1, st2, st_last1=None, st_first2=None, st_last2=None):
    # Same Style: So sánh các cặp
    if st1 == st2:
        return True
    if st_last1 and st1 == st_last1:
        return True
    if st_first2 and st_first2 == st2:
        return True
    if st_last1 and st_first2 and st_last1 == st_first2:
        return True
    return False

def can_merge(line1, line2, line_height2):
    # Điều kiện cơ bản
    if line2.get('MarkerText') is not None:
        return False
    
    # Same FontSize
    fs1 = line1.get('FontSize', 0)
    fs2 = line2.get('FontSize', 0)
    fs_last1 = line1.get('LastWord', {}).get('FontSize', fs1) if 'LastWord' in line1 else fs1
    fs_first2 = line2.get('FirstWord', {}).get('FontSize', fs2) if 'FirstWord' in line2 else fs2
    if not is_same_fontsize(fs1, fs2, fs_last1, fs_first2):
        return False
    
    # Same CaseStyle or Same Style
    cs1 = line1.get('CaseStyle', 'mixed')
    cs2 = line2.get('CaseStyle', 'mixed')
    cs_last1 = line1.get('LastWord', {}).get('CaseStyle', cs1) if 'LastWord' in line1 else cs1
    cs_first2 = line2.get('FirstWord', {}).get('CaseStyle', cs2) if 'FirstWord' in line2 else cs2
    st1 = line1.get('Style', '000')
    st2 = line2.get('Style', '000')
    st_last1 = line1.get('LastWord', {}).get('Style', st1) if 'LastWord' in line1 else st1
    st_first2 = line2.get('FirstWord', {}).get('Style', st2) if 'FirstWord' in line2 else st2
    if not (is_same_casestyle(cs1, cs2, cs_last1, cs_first2) or is_same_style(st1, st2, st_last1, st_first2)):
        return False
    
    # Top[2] < Top[1] + 0.3
    top1 = line1.get('Top', 0)
    top2 = line2.get('Top', 0)
    if top2 >= top1 + 0.3:
        return False
    
    # Top[2] < 2 * LineHeight[2]
    # Giả định LineHeight ≈ FontSize (có thể thay bằng giá trị chính xác nếu có)
    if top2 >= 2 * line_height2:
        return False
    
    # Điều kiện căn lề
    align1 = line1.get('Align', 'Unknown')
    align2 = line2.get('Align', 'Unknown')
    if align1 == 'Center' and align2 == 'Center':
        return True
    if align1 == 'Justified' and align2 == 'Justified':
        return True
    if align1 == 'Right' and align2 == 'Right':
        return True
    weight = fs1  # Giả định Weight = FontSize[1]
    first_word2_width = line2.get('FirstWord', {}).get('width', 0)
    if align2 == 'Left':
        extra_space1 = line1.get('Right', 0)
        if extra_space1 < first_word2_width - weight * 1.3:
            return True
    if align2 == 'Right':
        margin_left1 = line1.get('Left', 0)
        if margin_left1 < first_word2_width - weight * 1.3:
            return True
    return False

def merge_group(group):
    if not group:
        return None
    
    # Merge Text
    merged_text = ' '.join([g['Text'] for g in group])
    
    # MarkerText và MarkerFormat từ đầu tiên
    marker_text = group[0].get('MarkerText')
    marker_format = group[0].get('MarkerFormat')
    
    # CaseStyle: Tính lại từ merged_text (sử dụng get_CaseStyle nếu có, ở đây giả định)
    case_style = group[0].get('CaseStyle')  # Nếu không có get_CaseStyle, dùng của đầu

    # Style: Min của từng chữ số
    styles = [g.get('Style', '000') for g in group]
    min_b = min(int(s[0]) for s in styles)
    min_i = min(int(s[1]) for s in styles)
    min_u = min(int(s[2]) for s in styles)
    style = f"{min_b}{min_i}{min_u}"

    # FirstWord từ đầu, LastWord từ cuối
    first_word = group[0].get('FirstWord')
    last_word = group[-1].get('LastWord')
    
    # FontSize: Trung bình
    font_sizes = [g.get('FontSize', 0) for g in group]
    font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 0

    # Left: Min
    lefts = [g.get('Left', 0) for g in group]
    left = min(lefts)

    # Top: Từ đầu
    top = group[0].get('Top', 0)

    # Right: Min
    rights = [g.get('Right', 0) for g in group]
    right = min(rights)

    # Mid: Trung bình
    mids = [g.get('Mid', 0) for g in group]
    mid = sum(mids) / len(mids) if mids else 0

    # Tính lại Align
    align = determine_alignment(left, right, mid)

    # Line: Tự động, sẽ được gán sau
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
        line1 = group[-1]  # Dòng cuối trong group
        line2 = lines[i]
        line_height2 = line2.get('FontSize', 12)  # Giả định LineHeight ≈ FontSize

        if can_merge(line1, line2, line_height2):
            group.append(line2)
        else:
            # Merge group và thêm vào merged_lines
            merged = merge_group(group)
            if merged:
                merged['Line'] = len(merged_lines) + 1
                merged_lines.append(merged)
            group = [line2]

    # Merge group cuối
    merged = merge_group(group)
    if merged:
        merged['Line'] = len(merged_lines) + 1
        merged_lines.append(merged)

    data['lines'] = merged_lines
    return data