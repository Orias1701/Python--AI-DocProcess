import os
import pickle
import ipywidgets as widgets
from IPython.display import display

def create_name_form():
    """ DISPLAY """

    # Định nghĩa tên tệp trạng thái
    state_file = "# Widgets.pkl"

    # Hàm lưu trạng thái
    def save_state():
        # Kiểm tra xem các biến có phải là widget hợp lệ không
        required_widgets = {
            "file_name": file_name,
            "file_type": file_type,
            "data_key": data_key,
            "embe_key": embe_key,
            "embedding_model": embedding_model,
            "searching_egine": searching_egine,
            "reranking_model": reranking_model,
            "responing_model": responing_model,
            "switch_model": switch_model,
            "merge_otp": merge_otp,
            "path_end": path_end,
            "API_drop": API_drop,
        }
        for key, widget in required_widgets.items():
            if not hasattr(widget, "value"):
                raise ValueError(f"{key} is not a valid widget (missing 'value' attribute)")

        state = {
            "file_name": file_name.value,
            "file_type": file_type.value,
            "data_key": data_key.value,
            "embe_key": embe_key.value,
            "embedding_model": embedding_model.value,
            "searching_egine": searching_egine.value,
            "reranking_model": reranking_model.value,
            "responing_model": responing_model.value,
            "switch_model": switch_model.value,
            "merge_otp": merge_otp.value,
            "path_end": path_end.value,
            "API_drop": API_drop.value,
        }
        try:
            with open(state_file, "wb") as f:
                pickle.dump(state, f)
        except Exception as e:
            print(f"Error saving state: {e}")

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

    # Đường dẫn thư mục dữ liệu
    folder_path = "../Data"
    input_folder = os.listdir(folder_path) if os.path.exists(folder_path) else []

    # Tải trạng thái
    state = load_state()

    # Giao diện chọn file data
    file_name = widgets.Dropdown(
        options=input_folder or ["No files available"],
        description="File:  ",
        disabled=False,
        layout=widgets.Layout(width="50%"),
        value=state.get("file_name", input_folder[0] if input_folder else None),
    )
    file_type = widgets.Dropdown(
        options=["QA", "Data"],
        description="Type:  ",
        disabled=False,
        layout=widgets.Layout(width="50%"),
        value=state.get("file_type", "Data"),
    )
    data = widgets.HBox(
        [file_name, file_type],
        layout=widgets.Layout(
            width="90%", 
            justify_content="space-between", 
            padding="0px 0px 0px 0px",
        )
    )

    # Giao diện thiết lập Key
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
    keys = widgets.HBox(
        [data_key, embe_key],
        layout=widgets.Layout(
            width="90%", 
            justify_content="space-between", 
            padding="0px 0px 0px 0px",
        )
    )

    switch_model = widgets.Dropdown(
        options=[
            "Auto Model",
            'Sentence Transformer',
        ],
        description="Model: ",
        disabled=False,
        layout=widgets.Layout(width="33%"),
        value=state.get("switch_model", "Auto Model"),
    )

    merge_otp = widgets.Dropdown(
        options=[
            "Merge",
            "no_Merge",
        ],
        description="Merge: ",
        disabled=False,
        layout=widgets.Layout(width="33%"),
        value=state.get("merge_otp", "no_Merge"),
    )

    path_end = widgets.Dropdown(
        options=[
            ".pt",
            ".faiss",
            ".json",
        ],
        description="End: ",
        disabled=False,
        layout=widgets.Layout(width="33%"),
        value=state.get("path_end", ".json"),
    )
    choose = widgets.HBox(
        [switch_model, merge_otp, path_end],
        layout=widgets.Layout(
            width="90%", 
            justify_content="space-between", 
            padding="0px 0px 0px 0px",
        )
    )

    # Giao diện thiết lập Model
    embedding_model = widgets.Dropdown(
        options=[
            "sentence-transformers/bge-small-vi-v2",
            "VoVanPhuc/sup-SimCSE-VietNamese-phobert-base",
            "sentence-transformers/all-roberta-large-v1",
        ],
        description="Embedder: ",
        disabled=False,
        layout=widgets.Layout(width="90%"),
        value=state.get("embedding_model", "sentence-transformers/bge-small-vi-v2"),
    )
    searching_egine = widgets.Dropdown(
        options=[
            "faiss.IndexHNSWFlat",
            "faiss.IndexFlatIP",
            "faiss.IndexFlatL2",
        ],
        description="Searcher: ",
        disabled=False,
        layout=widgets.Layout(width="90%"),
        value=state.get("searching_egine", "faiss.IndexHNSWFlat"),
    )
    reranking_model = widgets.Dropdown(
        options=[
            "BAAI/bge-reranker-base",
            ],
        description="Reranker: ",
        disabled=False,
        layout=widgets.Layout(width="90%"),
        value=state.get("reranking_model", "BAAI/bge-reranker-base"),
    )
    responing_model = widgets.Dropdown(
        options=[
            "gemini-2.0-flash-exp",
            "vinai/PhoGPT-7B5-Instruct",
            "viet-llm/vietnamese-llama2-7b-chat",
        ],
        description="Response: ",
        disabled=False,
        layout=widgets.Layout(width="90%"),
        value=state.get("responing_model", "vinai/PhoGPT-7B5-Instruct"),
    )

    API_drop = widgets.Dropdown(
        options=[
            "AIzaSyDaHS-8h6GJkyVPhoX4svvYeBTTVLNO-2w",
            "AIzaSyD81vpriaNcvCyGOxy3TRR0w_njxgPJYfE",
            "AIzaSyCsQo1gnYSLELV9flyPkYgHBdEvz7lqPjk",
            "AIzaSyAJ7QFBJtozfyooguHAqsJsLO0a2L--tKo",
            "AIzaSyBPjyMfHkS9OW3h7G0kmLSQkWQMfqfX5v0",
            "AIzaSyA4HvCdIc4gGK4YCBlWS3vfXGjY3y9Zadg",
            "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",
        ],
        description="API Key:",
        disabled=False,
        layout=widgets.Layout(width="90%"),
        value=state.get("API_drop", "AIzaSyDaHS-8h6GJkyVPhoX4svvYeBTTVLNO-2w"),
    )

    # Nút lưu và chạy
    save_button = widgets.Button(description="Save State", button_style="success")
    run_button = widgets.Button(description="Run All Below", button_style="primary")

    def on_save_clicked(b):
        try:
            save_state()
            print("State saved successfully")
        except Exception as e:
            print(f"Error saving state: {e}")

    save_button.on_click(on_save_clicked)

    button_box = widgets.HBox(
        [save_button, run_button],
        layout=widgets.Layout(
            width="50%", 
            justify_content="space-between", 
            padding="0px 4% 0px 12%",
        )
    )

    display(data, keys, choose, embedding_model, searching_egine, reranking_model, responing_model, API_drop, button_box)
    
    return (
    data,               # index 0
    keys,               # index 1
    choose,             # index 2
    embedding_model,    # index 3
    searching_egine,    # index 4
    reranking_model,    # index 5
    responing_model,    # index 6 
    API_drop,           # index 7
    button_box,         # index 8
    file_name,          # index 9
    file_type,          # index 10
    data_key,           # index 11
    embe_key,           # index 12
    switch_model,       # index 13
    merge_otp,          # index 14
    path_end            # index 15                   
)