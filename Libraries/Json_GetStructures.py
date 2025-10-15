import json
import re
from collections import Counter, defaultdict
from typing import List, Dict, Any

class StructureAnalyzer:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    # ---------------- B1 ---------------- #
    def extract_markers(self, RawDataDict) -> List[str]:
        bullet_pattern = re.compile(r"^\s*[-•●♦▪‣–—]+\s*$")

        paragraphs = RawDataDict.get("paragraphs", [])
        common_markers = set(RawDataDict.get("general", {}).get("commonMarkers", []))

        raw_markers: List[Any] = []
        for p in paragraphs:
            mt = p.get("MarkerText")
            mtype = p.get("MarkerType")

            # Bỏ bullet
            if bullet_pattern.match(mt or "") or bullet_pattern.match(mtype or ""):
                continue

            # Giữ nếu thuộc common hoặc là None
            if mtype in common_markers or mtype is None:
                raw_markers.append(mtype)

        # Loại bỏ trùng kề nhau và chuẩn hóa None -> "none"
        cleaned: List[str] = []
        prev = object()
        for m in raw_markers:
            val = str(m) if m is not None else "none"
            if val != prev:
                cleaned.append(val)
                prev = val

        return cleaned

    # ---------------- B2 ---------------- #
    def build_structures(self, markers: List[str]) -> List[Dict[str, Any]]:
        unique_markers = list(dict.fromkeys(markers))
        counter1 = Counter(markers)
        results = [{"Depth": 1, "Structure": [m], "Count": counter1[m]} for m in unique_markers]

        max_depth = len(unique_markers)
        prev_structures = set((m,) for m in unique_markers)

        for i in range(2, max_depth + 1):
            counter = Counter()
            for j in range(len(markers) - i + 1):
                seq_raw = tuple(markers[j:j+i])
                prefix = seq_raw[:-1]

                # Điều kiện 1: phải có cha
                if prefix not in prev_structures:
                    continue
                # Điều kiện 2: không trùng MarkerType trong cùng cấu trúc
                if len(seq_raw) != len(set(seq_raw)):
                    continue
                # Điều kiện 3: chỉ chấp nhận nếu "none" không có, hoặc nằm ở cuối
                if "none" in seq_raw and seq_raw[-1] != "none":
                    continue

                counter[seq_raw] += 1

            if not counter:
                break

            min_count = min(counter.values())
            max_count = max(counter.values())
            filtered = {s: f for s, f in counter.items() if not (f == min_count and f != max_count)}
            sorted_structs = sorted(filtered.items(), key=lambda x: x[1], reverse=True)

            depth_lines = [{"Depth": i, "Structure": list(s), "Count": f} for s, f in sorted_structs]
            results.extend(depth_lines)

            prev_structures = set(s for s, _ in sorted_structs)

        return results

    # ---------------- B3 ---------------- #
    def deduplicate(self, structures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped = defaultdict(list)
        for item in structures:
            depth = item["Depth"]
            key = (depth, tuple(sorted(item["Structure"])))
            grouped[key].append(item)

        filtered = []
        for _, group in grouped.items():
            best = max(group, key=lambda x: x["Count"])
            filtered.append(best)

        filtered.sort(key=lambda x: (x["Depth"], -x["Count"], x["Structure"]))

        return filtered

    # ---------------- B4 ---------------- #
    def select_top(self, dedup: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not dedup:
            return []

        max_depth = max(item["Depth"] for item in dedup)
        at_max = [x for x in dedup if x["Depth"] == max_depth]
        max_count = max(x["Count"] for x in at_max)
        top = [x for x in at_max if x["Count"] == max_count]

        result = []
        for t in top:
            level_dict = {}
            for i, marker in enumerate(t["Structure"]):
                if i == len(t["Structure"]) - 1:
                    # phần tử cuối cùng
                    level_dict["Contents"] = marker
                else:
                    level_dict[f"Level {i+1}"] = marker
            result.append(level_dict)

        return result

    def level_rank(level: str) -> int:
        """Quy đổi level thành số để so sánh"""
        if level == "Contents":
            return 9999  # Contents coi như cao nhất
        if level.startswith("Level "):
            try:
                return int(level.split()[1])
            except Exception:
                return 0
        return 0

    def extend_top(self, top: List[Dict[str, Any]], dedup: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Mở rộng top bằng cách thêm tail từ dedup:
        - Nếu Contents: chỉ giữ tail == ['none']
        - Các level khác: thêm tail vào các level tiếp theo
        - Nếu level đã có -> gộp vào list
        - Luôn chuẩn hóa: mọi giá trị là list
        """
        if not top:
            return []

        RawLvlsDict = dict(top[0])  # copy để tránh sửa trực tiếp
        all_markers = set(v for val in RawLvlsDict.values() for v in (val if isinstance(val, list) else [val]))
        seen_tails = set()

        # snapshot tránh lỗi "dict changed size"
        snapshot_items = list(RawLvlsDict.items())

        for level, marker_values in reversed(snapshot_items):
            if level == "Level 1":
                continue

            # chuẩn hóa về list để dễ xử lý
            markers = marker_values if isinstance(marker_values, list) else [marker_values]

            for marker in markers:
                for d in dedup:
                    struct = d["Structure"]
                    if d["Depth"] < 2:
                        continue

                    if struct and struct[0] == marker:
                        if not (set(struct) & (all_markers - {marker})):
                            tail = tuple(struct[1:])

                            # xử lý riêng cho Contents
                            if level == "Contents" and tail != ("none",):
                                continue
                            if tail in seen_tails:
                                continue
                            seen_tails.add(tail)

                            # xác định base level
                            if level.startswith("Level "):
                                base_level_num = int(level.split()[1])
                            elif level == "Contents":
                                base_level_num = max(
                                    int(l.split()[1]) for l in RawLvlsDict if l.startswith("Level ")
                                )
                            else:
                                base_level_num = 0

                            # thêm từng phần tử tail vào level tiếp theo
                            for i, t in enumerate(tail, start=1):
                                next_level = f"Level {base_level_num+i}"
                                if next_level not in RawLvlsDict:
                                    RawLvlsDict[next_level] = []
                                if not isinstance(RawLvlsDict[next_level], list):
                                    RawLvlsDict[next_level] = [RawLvlsDict[next_level]]
                                if t not in RawLvlsDict[next_level]:
                                    RawLvlsDict[next_level].append(t)

        # đổi level cao nhất thành Contents (và gộp nếu đã có)
        level_nums = [int(l.split()[1]) for l in RawLvlsDict if l.startswith("Level ")]
        if level_nums:
            max_level = f"Level {max(level_nums)}"
            new_contents = RawLvlsDict.pop(max_level)

            if "Contents" not in RawLvlsDict:
                RawLvlsDict["Contents"] = []
            if not isinstance(RawLvlsDict["Contents"], list):
                RawLvlsDict["Contents"] = [RawLvlsDict["Contents"]]

            for v in (new_contents if isinstance(new_contents, list) else [new_contents]):
                if v not in RawLvlsDict["Contents"]:
                    RawLvlsDict["Contents"].append(v)

        # --- 🔹 Đổi nhãn ngay trước khi trả kết quả --- #
        keys = list(RawLvlsDict.keys())
        if len(keys) > 1 and keys[-2].startswith("Level "):
            RawLvlsDict["Article"] = RawLvlsDict.pop(keys[-2])
        if "Contents" in RawLvlsDict:
            RawLvlsDict["Content"] = RawLvlsDict.pop("Contents")

        # chuẩn hóa tất cả value thành list
        for k, v in RawLvlsDict.items():
            if not isinstance(v, list):
                RawLvlsDict[k] = [v]

        return [RawLvlsDict]
