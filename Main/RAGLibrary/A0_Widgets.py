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
            "switch_model": switch_model,
            "merge_otp": merge_otp,
            "path_end": path_end,
            "embedding_model": embedding_model,
            "searching_egine": searching_egine,
            "reranking_model": reranking_model,
            "responing_model": responing_model,
            "API_drop": API_drop,
            "level_input": level_input,
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
            "merge_otp": merge_otp.value,
            "path_end": path_end.value,
            "embedding_model": embedding_model.value,
            "searching_egine": searching_egine.value,
            "reranking_model": reranking_model.value,
            "responing_model": responing_model.value,
            "API_drop": API_drop.value,
            "level_input": level_input.value,
            "word_limit": word_limit.value,
            "level_values": {i: text.value for i, text in enumerate(input_box.children)},
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
    folder_path = "../Doc"

    # Kiểm tra folder có tồn tại không
    if os.path.exists(folder_path):
        input_folder = []
        for name in os.listdir(folder_path):
            full_path = os.path.join(folder_path, name)
            if os.path.isfile(full_path):
                # Nếu là file, bỏ phần mở rộng
                name = os.path.splitext(name)[0]
            # Nếu là folder, giữ nguyên
            input_folder.append(name)
    else:
        input_folder = []

    # Tải trạng thái
    state = load_state()

    # Giao diện chọn file data
    file_name = widgets.Dropdown(
        options=input_folder or ["No files available"],
        description="File:  ",
        disabled=False,
        layout=widgets.Layout(width="33%"),
        value=state.get("file_name", input_folder[0] if input_folder else None),
    )
    file_type = widgets.Dropdown(
        options=["QA", "Data"],
        description="Type:  ",
        disabled=False,
        layout=widgets.Layout(width="33%"),
        value=state.get("file_type", "Data"),
    )
    path_end = widgets.Dropdown(
        options=[
            ".pt",
            ".faiss",
            ".json",
            ".docx",
            ".pdf",
        ],
        description="End: ",
        disabled=False,
        layout=widgets.Layout(width="33%"),
        value=state.get("path_end", ".json"),
    )
    data = widgets.HBox(
        [file_name, file_type, path_end],
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
        layout=widgets.Layout(width="50%"),
        value=state.get("switch_model", "Auto Model"),
    )

    merge_otp = widgets.Dropdown(
        options=[
            "Merge",
            "no_Merge",
            "QA",
        ],
        description="Merge: ",
        disabled=False,
        layout=widgets.Layout(width="50%"),
        value=state.get("merge_otp", "no_Merge"),
    )

    choose = widgets.HBox(
        [switch_model, merge_otp],
        layout=widgets.Layout(
            width="90%", 
            justify_content="space-between", 
            padding="0px 0px 0px 0px",
        )
    )

    # Giao diện thiết lập Model
    embedding_model = widgets.Dropdown(
        options=[
            "vinai/phobert-base",
            "keepitreal/vietnamese-sbert",
            "VoVanPhuc/sup-SimCSE-VietNamese-phobert-base",
            "paraphrase-multilingual-mpnet-base-v2",
            "distiluse-base-multilingual-cased-v2",
            "sentence-transformers/all-roberta-large-v1",
            "sentence-transformers/bge-small-vi-v2",
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


    level_input = widgets.Dropdown(
        description="Max Level: ",
        options=[str(i) for i in range(0, 10)],
        layout=widgets.Layout(width="50%"),
        value=state.get("level_input", "1"),
    )
    word_limit = widgets.Text(
        description="Word Limit: ",
        placeholder="Default: 200",
        layout=widgets.Layout(width="50%"),
        value=state.get("word_limit", "200"),
    )
    chunk_input = widgets.HBox(
        [level_input, word_limit],
        layout=widgets.Layout(
            width="90%", 
            justify_content="space-between", 
            padding="0px 0px 0px 0px",
        )
    )

    input_box = widgets.VBox([])

    def update_text_inputs(change):
        level_number = int(change.new)
        prev_values = state.get("level_values", [])

        text_inputs = [
            widgets.Text(
                description=f"Level {i+1}: ",
                layout=widgets.Layout(width="44%"),
                value=prev_values[i] if i < len(prev_values) else ""
            )
            for i in range(level_number)
        ]
        input_box.children = text_inputs

    level_input.observe(update_text_inputs, names="value")
    
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

    display(data, keys, choose, embedding_model, searching_egine, reranking_model, responing_model, API_drop, chunk_input, input_box, button_box)

    level_input.value = "0"
    level_input.value = state.get("level_input", "0")

    return (
    data,               # index 0
    keys,               # index 1
    choose,             # index 2
    embedding_model,    # index 3
    searching_egine,    # index 4
    reranking_model,    # index 5
    responing_model,    # index 6 
    API_drop,           # index 7
    chunk_input,        # input 8
    input_box,          # input 9                    
    button_box,         # index 10
)