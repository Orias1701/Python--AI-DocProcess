import os
import pickle
import json
import ipywidgets as widgets
from IPython.display import display

def create_name_form():
    """ DISPLAY """

    # === Load config.json ===
    with open("Config/Widgets.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    with open("Config/API.json", "r", encoding="utf-8") as f:
        APIkeys = json.load(f)

    # Định nghĩa tên tệp trạng thái
    state_file = "Config/Widgets.pkl"

    # -------------------------
    # Hàm lưu trạng thái
    def save_state():
        required_widgets = {
            "file_name": file_name,
            "file_type": file_type,
            "data_key": data_key,
            "embe_key": embe_key,
            "switch_model": switch_model,
            "path_end": path_end,
            "embedding_model": embedding_model,
            "searching_egine": searching_egine,
            "reranking_model": reranking_model,
            "responing_model": responing_model,
            "API_drop": API_drop,
            "word_limit": word_limit,
        }
        for key, widget in required_widgets.items():
            if not hasattr(widget, "value"):
                raise ValueError(f"{key} is not a valid widget (missing 'value' attribute)")

        state = {
            "file_name": file_name.value,
            "file_type": file_type.value,
            "data_key": data_key.value,
            "embe_key": embe_key.value,
            "switch_model": switch_model.value,
            "path_end": path_end.value,
            "embedding_model": embedding_model.value,
            "searching_egine": searching_egine.value,
            "reranking_model": reranking_model.value,
            "responing_model": responing_model.value,
            "API_drop": API_drop.value,
            "word_limit": word_limit.value,
        }
        try:
            with open(state_file, "wb") as f:
                pickle.dump(state, f)
        except Exception as e:
            print(f"Error saving state: {e}")

    # -------------------------
    # Hàm tải trạng thái
    def load_state():
        try:
            if os.path.exists(state_file):
                with open(state_file, "rb") as f:
                    state = pickle.load(f)
                    if not isinstance(state, dict):
                        print("Invalid state file format, returning default state")
                        return {}
                    return state
        except (pickle.PickleError, EOFError, FileNotFoundError) as e:
            print(f"Error loading state: {e}")
        return {}

    # -------------------------
    # Chuẩn bị dữ liệu
    folder_path = "../Docs"
    if os.path.exists(folder_path):
        input_folder = []
        for name in os.listdir(folder_path):
            full_path = os.path.join(folder_path, name)
            if os.path.isfile(full_path):
                name = os.path.splitext(name)[0]
            input_folder.append(name)
    else:
        input_folder = []

    state = load_state()

    # -------------------------
    # Widgets
    file_name = widgets.Dropdown(
        options=input_folder or ["No files available"],
        description="File:  ",
        layout=widgets.Layout(width="50%"),
        value=state.get("file_name", input_folder[0] if input_folder else None),
    )
    path_end = widgets.Dropdown(
        options=config["path_end"],
        description="End: ",
        layout=widgets.Layout(width="50%"),
        value=state.get("path_end", config["path_end"][0]),
    )
    data = widgets.HBox([file_name, path_end],
        layout=widgets.Layout(width="90%", justify_content="space-between")
    )

    # Keys
    data_key = widgets.Text(
        description="Data Key: ",
        placeholder="Default: contents",
        layout=widgets.Layout(width="50%"),
        value=state.get("data_key", "contents"),
    )
    embe_key = widgets.Text(
        description="Embe Key: ",
        placeholder="Default: embeddings",
        layout=widgets.Layout(width="50%"),
        value=state.get("embe_key", "embeddings"),
    )
    keys = widgets.HBox([data_key, embe_key],
        layout=widgets.Layout(width="90%", justify_content="space-between")
    )

    # Word limit / Type
    file_type = widgets.Dropdown(
        options=config["file_type"],
        description="Type:  ",
        layout=widgets.Layout(width="50%"),
        value=state.get("file_type", config["file_type"][0]),
    )
    word_limit = widgets.Text(
        description="Word Limit: ",
        placeholder="Default: 200",
        layout=widgets.Layout(width="50%"),
        value=state.get("word_limit", "200"),
    )
    choose = widgets.HBox([file_type, word_limit],
        layout=widgets.Layout(width="90%", justify_content="space-between")
    )

    # Switch model (đưa riêng)
    switch_model = widgets.Dropdown(
        options=config["switch_model"],
        description="Model: ",
        layout=widgets.Layout(width="90%"),
        value=state.get("switch_model", config["switch_model"][0]),
    )

    # Embedding / Searching / Reranking / Response
    embedding_model = widgets.Dropdown(
        options=config["embedding_model"],
        description="Embedder: ",
        layout=widgets.Layout(width="90%"),
        value=state.get("embedding_model", config["embedding_model"][-1]),
    )
    searching_egine = widgets.Dropdown(
        options=config["searching_egine"],
        description="Searcher: ",
        layout=widgets.Layout(width="90%"),
        value=state.get("searching_egine", config["searching_egine"][0]),
    )
    reranking_model = widgets.Dropdown(
        options=config["reranking_model"],
        description="Reranker: ",
        layout=widgets.Layout(width="90%"),
        value=state.get("reranking_model", config["reranking_model"][0]),
    )
    responing_model = widgets.Dropdown(
        options=config["responing_model"],
        description="Response: ",
        layout=widgets.Layout(width="90%"),
        value=state.get("responing_model", config["responing_model"][0]),
    )

    API_drop = widgets.Dropdown(
        options=APIkeys["API_drop"],
        description="API Key:",
        layout=widgets.Layout(width="90%"),
        value = state.get("API_drop", APIkeys.get("API_drop", [""])[0] if APIkeys.get("API_drop") else "")
    )

    # Buttons
    save_button = widgets.Button(description="Save State", button_style="success")
    run_button = widgets.Button(description="Run All Below", button_style="primary")

    def on_save_clicked(b):
        try:
            save_state()
            print("State saved successfully")
        except Exception as e:
            print(f"Error saving state: {e}")

    save_button.on_click(on_save_clicked)

    button_box = widgets.HBox([save_button, run_button],
        layout=widgets.Layout(width="50%", justify_content="space-between", padding="0px 4% 0px 12%")
    )

    # Hiển thị
    display(data, keys, choose, switch_model,
            embedding_model, searching_egine,
            reranking_model, responing_model,
            API_drop, button_box)

    return (
        data, keys, choose, switch_model,
        embedding_model, searching_egine,
        reranking_model, responing_model,
        API_drop, button_box
    )
