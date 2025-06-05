def WidgetValues(widgets_list):
    """GET PARENT VALUE"""
    data = widgets_list[0]  # HBox 1
    keys = widgets_list[1]  # HBox 2
    choose = widgets_list[2]  # HBox 3
    embedd_model = widgets_list[3]
    search_egine = widgets_list[4]
    rerank_model = widgets_list[5]
    respon_model = widgets_list[6]
    API_drop = widgets_list[7]
    chunk_input = widgets_list[8]  # HBox 4
    level_value = widgets_list[9]  # HBox 5
    button_box = widgets_list[10]  # Button

    """GET CHILDREN VALUE"""
    # HBox 1
    file_name = data.children[0]
    file_type = data.children[1]
    path_end = data.children[2]
    # HBox 2
    data_key = keys.children[0]
    embe_key = keys.children[1]
    # HBox 3
    switch_model = choose.children[0]
    merge_otp = choose.children[1]
    # HBox 4
    level_input = chunk_input.children[0]
    word_limit = chunk_input.children[1]
    # HBox 5
    LEVEL_VALUES = [child.value for child in level_value.children]

    """DEF VALUE"""
    data_folder = file_name.value
    file_type_val = file_type.value
    data_key_val = data_key.value
    embe_key_val = embe_key.value
    API_key_val = API_drop.value
    switch = switch_model.value
    merge = merge_otp.value
    path_end_v = path_end.value
    embedding_model = embedd_model.value
    searching_egine = search_egine.value
    reranking_model = rerank_model.value
    responing_model = respon_model.value
    
    LEVEL_INPUT = level_input.value
    WORD_LIMIT = word_limit.value

    """DETAIL"""
    dcmt_path = f"../Doc/{data_folder}{path_end_v}"
    base_folder = "../Data"
    base_path = f"{base_folder}/{data_folder}/{file_type_val}_{data_folder}"
    chunks_base = f"{base_path}_Chunks.json"
    json_file_path = f"{base_path}_Database.json"
    schema_ex_path = f"{base_path}_Schema.json"
    embedding_path = f"{base_path}_Embeds_{merge}"
    torch_path = f"{embedding_path}.pt"
    faiss_path = f"{embedding_path}.faiss"
    mapping_path = f"{embedding_path}_mapping.json"
    mapping_data = f"{embedding_path}_map_data.json"

    FILE_TYPE = file_type_val
    DATA_KEY = data_key_val
    EMBE_KEY = embe_key_val
    SWITCH = switch
    EMBEDD_MODEL = embedding_model
    SEARCH_EGINE = searching_egine
    RERANK_MODEL = reranking_model
    RESPON_MODEL = responing_model
    MERGE = merge
    API_KEY = API_key_val

    print(f"Embedder: {EMBEDD_MODEL}")
    print(f"Searcher: {SEARCH_EGINE}")
    print(f"Reranker: {RERANK_MODEL}")
    print(f"Responer: {RESPON_MODEL}")
    print(f"Data Key: {DATA_KEY}")
    print(f"Embe Key: {EMBE_KEY}")
    print(f"Dcment  : {dcmt_path}")
    print(f"Chunked : {chunks_base}")
    print(f"Database: {json_file_path}")
    print(f"Torch   : {torch_path}")
    print(f"Faiss   : {faiss_path}")
    print(f"Mapping : {mapping_path}")
    print(f"Map Data: {mapping_data}")
    print(f"Schema  : {schema_ex_path}")
    print(f"Model   : {SWITCH}")
    print(f"Merge   : {MERGE}")
    print(f"API Key : {API_KEY}")
    print(f"Word    : {WORD_LIMIT}")
    print(f"Level   : {LEVEL_INPUT}")
    print(f"Level Values: {LEVEL_VALUES}")

    return {
            "dcmt_path": dcmt_path,
            "base_folder": base_folder,
            "base_path": base_path,
            "chunks_base": chunks_base,
            "json_file_path": json_file_path,
            "schema_ex_path": schema_ex_path,
            "embedding_path": embedding_path,
            "torch_path": torch_path,
            "faiss_path": faiss_path,
            "mapping_path": mapping_path,
            "mapping_data": mapping_data,
            "FILE_TYPE": FILE_TYPE,
            "DATA_KEY": DATA_KEY,
            "EMBE_KEY": EMBE_KEY,
            "SWITCH": SWITCH,
            "EMBEDD_MODEL": EMBEDD_MODEL,
            "SEARCH_EGINE": SEARCH_EGINE,
            "RERANK_MODEL": RERANK_MODEL,
            "RESPON_MODEL": RESPON_MODEL,
            "MERGE": MERGE,
            "API_KEY": API_KEY,
            "WORD_LIMIT": WORD_LIMIT,
            "LEVEL_INPUT": LEVEL_INPUT,
            "LEVEL_VALUES": LEVEL_VALUES
        }