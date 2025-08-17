"""

Xét 3 đoạn văn bản liền kề: Đoạn đang xét là [0], đoạn ngay trước nó là [-1], đoạn ngay sau nó là [1].

Khi nói Style[-1] == Style[0] cần so sánh các thuộc tính:
{
        Text[-1] Style = Text[0] Style
    or  Text[-1] Style = Text[0] Words.Last.Style
    or  Text[-1] Words.First.Style = Text[0] Style
    or  Text[-1] Words.First.Style = Text[0] Words.Last.Style
}

Các Function dùng cho gộp lines thành Para:

isNewPara(): MarkerText[0] != null
isSameFontSize(): FontSize[-1] == Fontsize[0] +- 0.7

isSameStyle(): Style[-1] == Style[0]
isSameCaseStyle(): Style[-1]/1000 == Style[0]/1000
isSameFontStyle(): Style[-1]%1000 == Style[0]%1000

isNearerPre(): Top[0] < Top[-1] * 1.3
isNearerNex(): Top[0] < Top[1] * 1.3
isNear(): isNearerPre() && isNearerNex() && Top[0] < LineHeight[0] * 4.0

isSameAlign(): Align[-1] == Align[0]
isEnoughSpace_R(): MarginRight[-1] < FirstWord[0]*1.3
isEnoughSpace_L(): MarginLeft[-1] < FirstWord[0]*1.3
isEnoughSpace(): isEnoughSpace_R() && notEnoughSpace_L()
isSentenceEnd(): LastWord[-1] == "." || "!" || "?" || ";" || ":"

isBadAlign(): Align[-1] != "right" && Align[0] == "right"
isNoSameAlign0(): Align[-1] == "justify"
isNoSameAlignC(): Align[-1] == "center"
isNoSameAlignR(): Align[-1] == "right"
isNoSameAlignL(): Align[-1] == "left" && Align[0] == "justify"

canMergeWithAlign(): isNoSameAlign0() || isNoSameAlignC() || (isNoSameAlignR() && Align[0] != "center") 
canMergeWithLeft(): isNoSameAlignL()

Điều kiện Merge 2 đoạn [-1] và [0]: 
canMerge():
  if    isNewPara() || !isSameCaseAndStyle() || !isSameFontSize() || !isNear() return false
  elif  isSameAlign() return True
  elif  isBadAlign() return False
  elif  canMergeWithAlign() || canMergeWithLeft() return True

cách merge là duyệt qua các đoạn có thể merge trước rồi merge luôn, ví dụ: 

para 1 : không xét
para 2: có thể gộp với para 1
para 3: có thể gộp với para 2
para 4: không thể gộp với para 3
tiến hành gộp para 1 - 2 - 3
tiếp tục xét 4, 5, 6, ...
para 5
para 6
...

Giữ nguyên general, chỉ Merge trong lines
Đoạn văn được merge sẽ có các thuộc tính sau của đối tượng sau.

    {
      "Paragraph": Đánh số tự động,
      "Text": Text sau khi đã gộp ngăn cách bằng space,
      "MarkerText": của line đầu tiên trong nhóm,
      "MarkerType": của line đầu tiên trong nhóm,
      "Style": 4 chữ số, mỗi chữ số đều lấy min chữ số tương ứng của các line
      "FontSize": Trung bình cộng các line trong nhóm, làm tròn 1 chữ số thập phân,
      "Align": "Lấy phổ biến của các đoạn đã merge hoặc của đoạn cuối cùng đã merge nếu không có đoạn nào",
      "Words": {
          "First": của line đầu tiên trong nhóm
          "Last": của line cuối cùng trong nhóm
        },
    },

"""