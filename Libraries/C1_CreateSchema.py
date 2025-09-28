import json
from typing import Any, Dict, Optional, List


class JSONSchemaExtractor:
    """
    Trích xuất schema từ JSON theo phong cách hướng đối tượng.
    - Giữ hành vi gốc: log "New:", xử lý null/mixed, key phẳng "a.b.c".
    - Chính sách duyệt list cấu hình được: "first" (mặc định, giống bản gốc) | "union".
    """

    def __init__(self, list_policy: str = "first", verbose: bool = True) -> None:
        """
        :param list_policy: "first" | "union"
            - "first": nếu gặp list các object, lấy schema theo PHẦN TỬ ĐẦU (như bản gốc).
            - "union": duyệt mọi phần tử, hợp nhất các field/type.
        :param verbose: in thông tin diễn tiến (giống bản gốc).
        """
        assert list_policy in ("first", "union"), "list_policy must be 'first' or 'union'"
        self.list_policy = list_policy
        self.verbose = verbose

        # Trạng thái cho 1 lần chạy create_schema_from_data / create_schema_from_file
        self._processed_fields: set[str] = set()
        self._full_schema: Dict[str, str] = {}

    # =====================================
    # 1) Chuẩn hóa kiểu dữ liệu
    # =====================================
    @staticmethod
    def get_standard_type(value: Any) -> str:
        """
        Giữ nguyên thứ tự phân loại như mã gốc để tương thích:
        int -> number, float -> number, str -> string, bool -> boolean, list -> array, dict -> object, None -> null
        (Lưu ý: với thứ tự này, bool là subclass của int => True/False có thể bị coi là number nếu đổi thứ tự.)
        """
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
             + Ngược lại: nếu khác nhau và chưa "mixed" => set "mixed" và cảnh báo (giống log gốc).
        """
        if key not in self._full_schema:
            self._full_schema[key] = new_type
            if key not in self._processed_fields and self.verbose:
                print(f"New: {key:15} item {item_index}: Type = {new_type}")
            self._processed_fields.add(key)
            return

        old_type = self._full_schema[key]
        if old_type == new_type:
            return

        # Quy tắc giữ nguyên như bản gốc
        if new_type == "null":
            if self.verbose:
                print(f"Field '{key}' has null value in item {item_index}, keeping type: {old_type}")
            return
        if old_type == "null":
            if self.verbose:
                print(f"Field '{key}' has non-null value in item {item_index}, updating type to: {new_type}")
            self._full_schema[key] = new_type
            return

        # hai kiểu khác nhau (không liên quan null) -> mixed
        if old_type != "mixed":
            if self.verbose:
                print(f"Warning: Field '{key}' has multiple types: {old_type} and {new_type}")
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

            # Ghi nhận kiểu tại chính trường này
            vtype = self.get_standard_type(value)
            self._merge_type(new_prefix, vtype, item_index)

            # Nếu là object: đi sâu
            if isinstance(value, dict):
                self._extract_schema_from_obj(value, f"{new_prefix}.", item_index)

            # Nếu là array: nếu có phần tử & phần tử đầu là dict/list -> đệ quy
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
                    # Mô phỏng hành vi gốc: nếu phần tử đầu cũng là list -> đệ quy 1 cấp
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
        # phần tử lá (str/number/boolean/null/unknown) không tạo thêm key con — giữ nguyên hành vi gốc

    # =====================================
    # 4) API chính (data/file)
    # =====================================
    def create_schema_from_data(self, data: Any) -> Dict[str, str]:
        """
        Tạo schema từ biến Python (list | dict).
        Giữ log giống bản gốc.
        """
        # Reset trạng thái cho lần chạy này
        self._processed_fields.clear()
        self._full_schema.clear()

        # Chuẩn hóa thành list
        data_list = data if isinstance(data, list) else [data]

        if self.verbose:
            print("\nChecking fields and their types:")

        if not data_list:
            raise ValueError("JSON data is empty")

        # Duyệt từng phần tử (kỳ vọng dict như bản gốc)
        for i, item in enumerate(data_list, 1):
            if not isinstance(item, dict):
                if self.verbose:
                    print(f"Item {i} is not a dict: {type(item)}")
                    print(f"Skipping item {i}: Not a dict ({type(item)})")
                continue

            # Đệ quy trích xuất cho item hiện tại
            self._extract_schema_from_obj(item, prefix="", item_index=i)

        if self.verbose:
            print("Generated schema:")
            print(json.dumps(self._full_schema, ensure_ascii=False, indent=2))

        return dict(self._full_schema)

    def schemaRun(self, json_path: str, schema_path: Optional[str] = None) -> Dict[str, str]:
        """
        Đọc JSON từ file, tạo schema, và nếu có schema_path thì ghi ra file.
        """
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        schema = self.create_schema_from_data(data)

        if schema_path:
            self.save_schema(schema, schema_path)

        return schema

    @staticmethod
    def save_schema(schema: Dict[str, str], schema_path: str) -> None:
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, ensure_ascii=False, indent=2)
