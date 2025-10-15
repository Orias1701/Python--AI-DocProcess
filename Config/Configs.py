import logging
import os
import faiss

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
os.environ["TORCH_USE_CUDA_DSA"] = "1"

def ConfigValues(service="Search", inputs="file.pdf"):

    # Inputs
    inputFolder = f"./Inputs"
    inputPath = f"{inputFolder}/{inputs}"

    # Assets
    assetsFolder = f"./Assets"
    exceptPath = f"{assetsFolder}/ex.exceptions.json"
    markerPath = f"{assetsFolder}/ex.markers.json"
    statusPath = f"{assetsFolder}/ex.status.json"

    # Documents
    DocFolder = "./Documents"
    DocPath = f"{DocFolder}/{service}"
    PdfPath = f"{DocPath}.pdf"
    DocPath = f"{DocPath}.docx"

    # Database
    DBFolder = "./Database"
    DBPath = f"{DBFolder}/{service}/{service}"

    RawExtractPath = f"{DBPath}_Extract"
    ChunksPath = f"{DBPath}_Chunks"
    EmbeddingPath = f"{DBPath}_Embedding"

    RawDataPath = f"{RawExtractPath}_Raw.json"
    RawLvlsPath = f"{RawExtractPath}_Levels.json"

    StructsPath = f"{ChunksPath}_Struct.json"
    SegmentPath = f"{ChunksPath}_Segment.json"
    SchemaPath = f"{ChunksPath}_Schema.json"
    
    FaissPath = f"{EmbeddingPath}_Index.faiss"
    MappingPath = f"{EmbeddingPath}_Mapping.json"
    MapDataPath = f"{EmbeddingPath}_MapData.json"
    MapChunkPath = f"{EmbeddingPath}_MapChunk.json"
    MetaPath = f"{EmbeddingPath}_Meta.json"

    # Keys
    DATA_KEY = "contents"
    EMBE_KEY = "embeddings"

    # Models
    SEARCH_EGINE = faiss.IndexFlatIP
    RERANK_MODEL = "BAAI/bge-reranker-base"
    CHUNKS_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDD_MODEL = "VoVanPhuc/sup-SimCSE-VietNamese-phobert-base"
    RESPON_MODEL = "gpt-3.5-turbo"
    SUMARY_MODEL = "vinai/bartpho-syllable"

    WORD_LIMIT = 1000

    return {
        "inputPath": inputPath,
        "PdfPath": PdfPath,
        "DocPath": DocPath,
        "exceptPath": exceptPath,
        "markerPath": markerPath,
        "statusPath": statusPath,
        "RawDataPath": RawDataPath,
        "RawLvlsPath": RawLvlsPath,
        "StructsPath": StructsPath,
        "SegmentPath": SegmentPath,
        "SchemaPath": SchemaPath,
        "FaissPath": FaissPath,
        "MappingPath": MappingPath,
        "MapDataPath": MapDataPath,
        "MapChunkPath": MapChunkPath,
        "MetaPath": MetaPath,
        "DATA_KEY": DATA_KEY,
        "EMBE_KEY": EMBE_KEY,
        "SEARCH_EGINE": SEARCH_EGINE,
        "RERANK_MODEL": RERANK_MODEL,
        "RESPON_MODEL": RESPON_MODEL,        
        "CHUNKS_MODEL": CHUNKS_MODEL,
        "EMBEDD_MODEL": EMBEDD_MODEL,
        "SUMARY_MODEL": SUMARY_MODEL,
        "WORD_LIMIT": WORD_LIMIT
    }
