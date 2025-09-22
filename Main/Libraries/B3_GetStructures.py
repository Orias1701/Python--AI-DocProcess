import json
import re
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional


class StructureAnalyzer:
    def __init__(self, data_folder: str, verbose: bool = False):
        self.data_folder = data_folder
        self.verbose = verbose

    # ---------------- B1 ---------------- #
    def extract_markers(self) -> List[Any]:
        merged_path = self.data_folder + "_dataMerged.json"
        bullet_pattern = re.compile(r"^\s*[-•●♦▪‣–—]+\s*$")

        with open(merged_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        paragraphs = data.get("paragraphs", [])
        common_markers = set(data.get("general", {}).get("commonMarkers", []))

        raw_markers: List[Any] = []
        for p in paragraphs:
            mt = p.get("MarkerText")
            mtype = p.get("MarkerType")

            if bullet_pattern.match(mt or "") or bullet_pattern.match(mtype or ""):
                continue
            if mtype in common_markers:
                raw_markers.append(mtype)
            elif mtype is None and None in common_markers:
                raw_markers.append(None)

        # loại trùng kề nhau
        cleaned = []
        prev = object()
        for m in raw_markers:
            if m != prev:
                cleaned.append(m)
                prev = m

        if self.verbose:
            print(f"[B1] Extracted {len(cleaned)} markers")
        return cleaned

    # ---------------- B2 ---------------- #
    def build_structures(self, markers: List[Any]) -> List[Dict[str, Any]]:
        unique_markers = list(dict.fromkeys(markers))
        counter1 = Counter(markers)
        results = [{"Depth": 1, "Structure": [str(m)], "Count": counter1[m]} for m in unique_markers]

        max_depth = len(unique_markers)
        prev_structures = set((m,) for m in unique_markers)

        for i in range(2, max_depth + 1):
            counter = Counter()
            for j in range(len(markers) - i + 1):
                seq_raw = tuple(markers[j:j+i])
                prefix = seq_raw[:-1]

                if prefix not in prev_structures:
                    continue
                if len(seq_raw) != len(set(seq_raw)):
                    continue

                counter[seq_raw] += 1

            if not counter:
                break

            min_count = min(counter.values())
            max_count = max(counter.values())
            filtered = {s: f for s, f in counter.items() if not (f == min_count and f != max_count)}
            sorted_structs = sorted(filtered.items(), key=lambda x: x[1], reverse=True)

            depth_lines = [{"Depth": i, "Structure": [str(x) for x in s], "Count": f} for s, f in sorted_structs]
            results.extend(depth_lines)

            prev_structures = set(s for s, _ in sorted_structs)

        if self.verbose:
            print(f"[B2] Built {len(results)} structures")
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
        if self.verbose:
            print(f"[B3] Deduped to {len(filtered)} structures")
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
            level_dict = {f"Level {i+1}": marker for i, marker in enumerate(t["Structure"])}
            result.append(level_dict)

        if self.verbose:
            print(f"[B4] Selected {len(result)} top structures at depth {max_depth}")
        return result

    # ---------------- Save ---------------- #
    def save_json(self, data: List[Dict[str, Any]], path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if self.verbose:
            print(f"[Save] Saved to {path}")
