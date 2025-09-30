def WidgetValues(widgets_list):

    base_folder = "../Data"
    docs_folder = "../Docs"

    """GET PARENT VALUE"""
    data = widgets_list[0]        # HBox 1
    keys = widgets_list[1]        # HBox 2
    choose = widgets_list[2]      # HBox 3
    switch_model = widgets_list[3]
    embedd_model = widgets_list[4]
    search_egine = widgets_list[5]
    rerank_model = widgets_list[6]
    respon_model = widgets_list[7]
    API_drop = widgets_list[8]
    button_box = widgets_list[9]  # Buttons

    """GET CHILDREN VALUE"""
    # HBox 1
    file_name = data.children[0]
    path_end = data.children[1]
    # HBox 2
    data_key = keys.children[0]
    embe_key = keys.children[1]
    # HBox 3
    file_type = choose.children[0]
    word_limit = choose.children[1]

    """DEF VALUE"""
    data_folder = file_name.value
    file_type_val = file_type.value
    data_key_val = data_key.value
    embe_key_val = embe_key.value
    API_key_val = API_drop.value
    switch = switch_model.value
    path_end_v = path_end.value
    embedding_model = embedd_model.value
    searching_egine = search_egine.value
    reranking_model = rerank_model.value
    responing_model = respon_model.value
    WORD_LIMIT = word_limit.value

    """DETAIL"""
    dcmt_path = f"{docs_folder}/{data_folder}{path_end_v}"
    base_path = f"{base_folder}/{data_folder}/{file_type_val}_{data_folder}"
    extracted_path = f"{base_path}_Texts_Extracted.json"
    merged_path = f"{base_path}_Texts_Merged.json"
    struct_path = f"{base_path}_Texts_Struct.json"
    chunks_struct = f"{base_path}_Chunks_Struct.json"
    chunks_segment = f"{base_path}_Chunks_Segment.json"
    schema_ex_path = f"{base_path}_Chunks_Schema.json"
    embedding_path = f"{base_path}_Embeddings"
    torch_path = f"{embedding_path}.pt"
    faiss_path = f"{embedding_path}.faiss"
    mapping_path = f"{embedding_path}_mapping.json"
    map_data_path = f"{embedding_path}_map_data.json"
    meta_path = f"{embedding_path}_meta.json"

    FILE_TYPE = file_type_val
    DATA_KEY = data_key_val
    EMBE_KEY = embe_key_val
    SWITCH = switch
    EMBEDD_MODEL = embedding_model
    SEARCH_EGINE = searching_egine
    RERANK_MODEL = reranking_model
    RESPON_MODEL = responing_model
    API_KEY = API_key_val

    print(f"Model   : {SWITCH}")
    print(f"Type    : {FILE_TYPE}")
    print(f"Embedder: {EMBEDD_MODEL}")
    print(f"Searcher: {SEARCH_EGINE}")
    print(f"Reranker: {RERANK_MODEL}")
    print(f"Responer: {RESPON_MODEL}")
    print(f"Data Key: {DATA_KEY}")
    print(f"Embe Key: {EMBE_KEY}")
    print(f"File    : {data_folder}")
    print(f"Dcment  : {dcmt_path}")
    print(f"Extract : {extracted_path}")
    print(f"Merge   : {merged_path}")
    print(f"Struct  : {struct_path}")
    print(f"Chunked : {chunks_struct}")
    print(f"Segment : {chunks_segment}")
    print(f"Schema  : {schema_ex_path}")
    print(f"Torch   : {torch_path}")
    print(f"Faiss   : {faiss_path}")
    print(f"Mapping : {mapping_path}")
    print(f"Map Data: {map_data_path}")
    print(f"Meta    : {meta_path}")
    print(f"API Key : {API_KEY}")
    print(f"Word    : {WORD_LIMIT}")

    return {
        "data_folder": data_folder,
        "dcmt_path": dcmt_path,
        "base_folder": base_folder,
        "base_path": base_path,
        "extracted_path": extracted_path,
        "merged_path": merged_path,
        "struct_path": struct_path,
        "chunks_struct": chunks_struct,
        "chunks_segment": chunks_segment,
        "schema_ex_path": schema_ex_path,
        "embedding_path": embedding_path,
        "torch_path": torch_path,
        "faiss_path": faiss_path,
        "mapping_path": mapping_path,
        "map_data_path": map_data_path,
        "meta_path": meta_path,
        "FILE_TYPE": FILE_TYPE,
        "DATA_KEY": DATA_KEY,
        "EMBE_KEY": EMBE_KEY,
        "SWITCH": SWITCH,
        "EMBEDD_MODEL": EMBEDD_MODEL,
        "SEARCH_EGINE": SEARCH_EGINE,
        "RERANK_MODEL": RERANK_MODEL,
        "RESPON_MODEL": RESPON_MODEL,
        "API_KEY": API_KEY,
        "WORD_LIMIT": WORD_LIMIT
    }
