import json
from typing import Any, Dict, Optional, List
from . import Common_MyUtils as MyUtils

class JSONSchemaExtractor:

    def __init__(self, list_policy: str = "first", verbose: bool = True) -> None:
        """
        :param list_policy: "first" | "union"
            - "first": nếu gặp list các object, lấy schema theo PHẦN TỬ ĐẦU (như bản gốc).
            - "union": duyệt mọi phần tử, hợp nhất các field/type.
        """
        assert list_policy in ("first", "union"), "list_policy must be 'first' or 'union'"
        self.list_policy = list_policy
        self.verbose = verbose

        self._processed_fields: set[str] = set()
        self._full_schema: Dict[str, str] = {}

    # =====================================
    # 1) Chuẩn hóa kiểu dữ liệu
    # =====================================
    @staticmethod
    def get_standard_type(value: Any) -> str:

        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "number"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        elif value is None:
            return "null"
        return "unknown"

    # =====================================
    # 2) Hợp nhất kiểu (null / mixed)
    # =====================================
    def _merge_type(self, key: str, new_type: str, item_index: int) -> None:
        """
        Cập nhật self._full_schema[key] theo quy tắc:
         - Nếu chưa có: đặt = new_type và log "New: ..."
         - Nếu khác:
             + Nếu new_type == "null": giữ kiểu cũ.
             + Nếu kiểu cũ == "null": cập nhật = new_type.
             + Ngược lại: nếu khác nhau và chưa "mixed" => set "mixed" và cảnh báo.
        """
        if key not in self._full_schema:
            self._full_schema[key] = new_type
            self._processed_fields.add(key)
            return

        old_type = self._full_schema[key]
        if old_type == new_type:
            return

        if new_type == "null":
            return
        
        if old_type == "null":
            self._full_schema[key] = new_type
            return

        if old_type != "mixed":
            self._full_schema[key] = "mixed"

    # =====================================
    # 3) Đệ quy trích xuất schema
    # =====================================
    def _extract_schema_from_obj(self, data: Dict[str, Any], prefix: str, item_index: int) -> None:
        """
        Duyệt dict hiện tại, cập nhật _full_schema với kiểu tại key (phẳng),
        và nếu là object/array lồng thì đệ quy theo quy tắc gốc.
        """
        for key, value in data.items():
            new_prefix = f"{prefix}{key}" if prefix else key

            vtype = self.get_standard_type(value)
            self._merge_type(new_prefix, vtype, item_index)

            if isinstance(value, dict):
                self._extract_schema_from_obj(value, f"{new_prefix}.", item_index)

            elif isinstance(value, list) and value:
                first = value[0]
                if isinstance(first, dict):
                    if self.list_policy == "first":
                        self._extract_schema_from_obj(first, f"{new_prefix}.", item_index)
                    else:  # union
                        for elem in value:
                            if isinstance(elem, dict):
                                self._extract_schema_from_obj(elem, f"{new_prefix}.", item_index)
                elif isinstance(first, list):
                    if self.list_policy == "first":
                        self._extract_schema_from_list(first, f"{new_prefix}.", item_index)
                    else:
                        for elem in value:
                            if isinstance(elem, list):
                                self._extract_schema_from_list(elem, f"{new_prefix}.", item_index)

    def _extract_schema_from_list(self, data_list: List[Any], prefix: str, item_index: int) -> None:
        """
        Hỗ trợ cho trường hợp list lồng list (ít gặp). Duyệt tương tự _extract_schema_from_obj.
        """
        if not data_list:
            return

        first = data_list[0]
        if isinstance(first, dict):
            if self.list_policy == "first":
                self._extract_schema_from_obj(first, prefix, item_index)
            else:
                for elem in data_list:
                    if isinstance(elem, dict):
                        self._extract_schema_from_obj(elem, prefix, item_index)
        elif isinstance(first, list):
            if self.list_policy == "first":
                self._extract_schema_from_list(first, prefix, item_index)
            else:
                for elem in data_list:
                    if isinstance(elem, list):
                        self._extract_schema_from_list(elem, prefix, item_index)

    # =====================================
    # 4) API chính (data/file)
    # =====================================
    def create_schema_from_data(self, data: Any) -> Dict[str, str]:
        """
        Tạo schema từ biến Python (list | dict).
        Giữ log giống bản gốc.
        """

        self._processed_fields.clear()
        self._full_schema.clear()

        data_list = data if isinstance(data, list) else [data]

        if not data_list:
            raise ValueError("JSON data is empty")

        for i, item in enumerate(data_list, 1):
            if not isinstance(item, dict):
                continue

            self._extract_schema_from_obj(item, prefix="", item_index=i)

        return dict(self._full_schema)

    def schemaRun(self, SegmentDict: str) -> Dict[str, str]:
        SchemaDict = self.create_schema_from_data(SegmentDict)
        return SchemaDict