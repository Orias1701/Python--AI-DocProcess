from collections import OrderedDict
from copy import deepcopy

class ChunkBuilder:
    def readInput(self, RawLvlsDict=None, RawDataDict=None):
        # Đọc dữ liệu

        self.struct_spec = RawLvlsDict[0]
        self.paragraphs = sorted(
            RawDataDict.get("paragraphs", []),
            key=lambda x: x.get("Paragraph", 0)
        )

        # Chuẩn bị cấu trúc
        self.ordered_fields = list(self.struct_spec.keys())
        self.last_field = self.ordered_fields[-1]
        self.level_fields = self.ordered_fields[:-1]

        # Tập marker cho từng field
        self.marker_dict = {}
        for fld in self.ordered_fields:
            vals = self.struct_spec.get(fld, [])
            self.marker_dict[fld] = set(vals) if isinstance(vals, list) else set()

        # Biến tạm
        self.StructDict = []
        self.index_counter = 1

    # ===== Các hàm tiện ích =====
    def _new_temp(self):
        return {fld: "" for fld in self.level_fields} | {self.last_field: []}

    def _temp_has_data(self, temp):
        return any(temp[f].strip() for f in self.level_fields) or bool(temp[self.last_field])

    def _reset_deeper(self, temp, touched_field):
        idx = self.level_fields.index(touched_field)
        for f in self.level_fields[idx+1:]:
            temp[f] = ""
        temp[self.last_field] = []

    def _has_data_from_level(self, temp, fld):
        """Kiểm tra từ level fld trở xuống có dữ liệu không"""
        if fld not in self.level_fields:
            return False
        idx = self.level_fields.index(fld)
        for f in self.level_fields[idx:]:
            if temp[f].strip():
                return True
        if temp[self.last_field]:
            return True
        return False

    def _with_index(self, temp, idx):
        """Tạo OrderedDict với Index đứng đầu"""
        od = OrderedDict()
        od["Index"] = idx
        for f in self.level_fields:
            od[f] = temp[f]
        od[self.last_field] = temp[self.last_field]
        return od

    # ===== Hàm chính =====
    def build(self, RawLvlsDict=None, RawDataDict=None):
        self.readInput(RawLvlsDict, RawDataDict)
        temp = self._new_temp()
        for p in self.paragraphs:
            text = p.get("Text") or ""
            marker = p.get("MarkerType", None) or "none"

            matched_field = None
            for fld in self.level_fields:
                if marker in self.marker_dict.get(fld, set()):
                    matched_field = fld
                    break

            if matched_field is not None:
                if self._has_data_from_level(temp, matched_field):
                    self.StructDict.append(self._with_index(deepcopy(temp), self.index_counter))
                    self.index_counter += 1

                temp[matched_field] = text
                self._reset_deeper(temp, matched_field)
            else:
                temp[self.last_field].append(text)

        if self._temp_has_data(temp):
            self.StructDict.append(self._with_index(deepcopy(temp), self.index_counter))
            self.index_counter += 1
        
        return self.StructDict