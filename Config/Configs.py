import logging
import os
import faiss

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
os.environ["TORCH_USE_CUDA_DSA"] = "1"

def ConfigValues(pdfname="HNMU", service="Categories"):

    serviceFolder = f"./Services"
    assetsFolder = f"./Assets"
    dataFolder = f"./Database"

    servicePath = f"{serviceFolder}/{service}/{service}"
    serviceEmbeddingPath = f"{servicePath}_Embedding"
    serviceFaissPath = f"{serviceEmbeddingPath}_Index.faiss"
    serviceMappingPath = f"{serviceEmbeddingPath}_Mapping.json"
    serviceMapDataPath = f"{serviceEmbeddingPath}_MapData.json"
    serviceMapChunkPath = f"{serviceEmbeddingPath}_MapChunk.json"
    serviceMetaPath = f"{serviceEmbeddingPath}_Meta.json"
    serviceSegmentPath = f"{servicePath}_Segment.json"
    
    exceptPath = f"{assetsFolder}/ex.exceptions.json"
    markerPath = f"{assetsFolder}/ex.markers.json"
    statusPath = f"{assetsFolder}/ex.status.json"

    # Documents
    PdfFolder = f"./Documents"
    PdfPath = f"{PdfFolder}/{pdfname}.pdf"
        
    # Database
    DBPath = f"{dataFolder}/{pdfname}/{pdfname}"

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
    SUMARY_MODEL = "LongK171/bartpho-syllable-vnexpress"

    WORD_LIMIT = 1000

    return {
        "PdfPath": PdfPath,
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
        "serviceSegmentPath": serviceSegmentPath,
        "serviceFaissPath": serviceFaissPath,
        "serviceMappingPath": serviceMappingPath,
        "serviceMapDataPath": serviceMapDataPath,
        "serviceMapChunkPath": serviceMapChunkPath,
        "serviceMetaPath": serviceMetaPath,
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
