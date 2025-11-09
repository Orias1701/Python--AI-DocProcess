import faiss
import fitz

from sentence_transformers import CrossEncoder

from Config import Configs
from Config import ModelLoader as ML
from Libraries import Common_MyUtils as MU, Common_TextProcess as TP, Common_PdfProcess as PP
from Libraries import PDF_QualityCheck as QualityCheck, PDF_ExtractData as ExtractData, PDF_MergeData as MergeData
from Libraries import Json_ChunkUnder as ChunkUnder, Json_GetStructures as GetStructures, Json_ChunkMaster as ChunkMaster, Json_SchemaExt as SchemaExt
from Libraries import Faiss_Embedding as F_Embedding, Faiss_Searching as F_Searching, Faiss_ChunkMapping as ChunkMapper
from Libraries import Summarizer_Runner as SummaryRun


## ==============================
## CONFIGURATION
## ==============================

#### HARD CODE
service = "Categories"
infilename = "HNMU"
JsonKey = "paragraphs"
JsonField = "Text"

MODEL_DIR = "Models"
MODEL_SUMARY = "Summarizer"
MODEL_ENCODE = "Sentence_Transformer"


#### LOAD CONFIG
config = Configs.ConfigValues(pdfname=infilename, service=service)

PdfPath = config["PdfPath"]
exceptPath = config["exceptPath"]
markerPath = config["markerPath"]
statusPath = config["statusPath"]

RawDataPath = config["RawDataPath"]
RawLvlsPath = config["RawLvlsPath"]
StructsPath = config["StructsPath"]
SegmentPath = config["SegmentPath"]
SchemaPath = config["SchemaPath"]
FaissPath = config["FaissPath"]
MappingPath = config["MappingPath"]
MapDataPath = config["MapDataPath"]
MapChunkPath = config["MapChunkPath"]
MetaPath = config["MetaPath"]

serviceSegmentPath = config["serviceSegmentPath"]
serviceFaissPath = config["serviceFaissPath"]
serviceMappingPath = config["serviceMappingPath"]
serviceMapDataPath = config["serviceMapDataPath"]
serviceMapChunkPath = config["serviceMapChunkPath"]
serviceMetaPath = config["serviceMetaPath"]

DATA_KEY = config["DATA_KEY"]
EMBE_KEY = config["EMBE_KEY"]
SEARCH_EGINE = config["SEARCH_EGINE"]
RERANK_MODEL = config["RERANK_MODEL"]
RESPON_MODEL = config["RESPON_MODEL"]
EMBEDD_MODEL = config["EMBEDD_MODEL"]
CHUNKS_MODEL = config["CHUNKS_MODEL"]
SUMARY_MODEL = config["SUMARY_MODEL"]
WORD_LIMIT = config["WORD_LIMIT"]

EMBEDD_CACHED_MODEL = f"{MODEL_DIR}/{MODEL_ENCODE}/{EMBEDD_MODEL}"
CHUNKS_CACHED_MODEL = F"{MODEL_DIR}/{MODEL_ENCODE}/{CHUNKS_MODEL}"
SUMARY_CACHED_MODEL = f"{MODEL_DIR}/{MODEL_SUMARY}/{SUMARY_MODEL}"

MAX_INPUT = 1024
MAX_TARGET = 256
MIN_TARGET = 64
TRAIN_EPOCHS = 3
LEARNING_RATE = 3e-5
WEIGHT_DECAY = 0.01
BATCH_SIZE = 4




## ==============================
## EXCEPTIONS
## ==============================

#### FUNCTIONS
def loadHardcodes(file_path, wanted=None):
    data = MU.read_json(file_path)
    if "items" not in data:
        return
    result = {}
    for item in data["items"]:
        key = item["key"]
        if (not wanted) or (key in wanted):
            result[key] = item["values"]
    return result


#### LOAD EXCEPTIONS
exceptData = loadHardcodes(exceptPath, wanted=["common_words", "proper_names", "abbreviations"])
markerData = loadHardcodes(markerPath, wanted=["keywords", "markers"])
statusData = loadHardcodes(statusPath, wanted=["brackets", "sentence_ends"])




## ==============================
## MODELS
## ==============================

#### CLASS
Loader = ML.ModelLoader()


#### LOAD MODELS
indexer, embeddDevice = Loader.load_encoder(EMBEDD_MODEL, EMBEDD_CACHED_MODEL)
chunker, chunksDevice = Loader.load_encoder(CHUNKS_MODEL, CHUNKS_CACHED_MODEL)

tokenizer, summarizer, summaryDevice = Loader.load_summarizer(SUMARY_MODEL, SUMARY_CACHED_MODEL)




## ==============================
## MAIN FLOW CLASSES
## ==============================

#### EXTRACTOR
checker = QualityCheck.PDFQualityChecker()

dataExtractor = ExtractData.B1Extractor(
    exceptData,
    markerData,
    statusData,
    proper_name_min_count=10
)

merger = MergeData.ParagraphMerger()


#### STRUCT CHUNKER
structAnalyzer = GetStructures.StructureAnalyzer(
    verbose=True
)

chunkBuilder = ChunkMaster.ChunkBuilder()

schemaExt = SchemaExt.JSONSchemaExtractor(
    list_policy="first", 
    verbose=True
)


#### INDEXER
faissIndexer = F_Embedding.DirectFaissIndexer(
    indexer=indexer,
    device=str(embeddDevice),
    batch_size=32,
    show_progress=True,
    flatten_mode="split",
    join_sep="\n",
    allowed_schema_types=("string", "array", "dict"),
    max_chars_per_text=2000,
    normalize=True,
    verbose=False
)


#### SEGMENT CHUNKER
chunkUnder = ChunkUnder.ChunkUndertheseaBuilder(
    embedder=indexer,
    device=embeddDevice,
    min_words=256,
    max_words=768,
    sim_threshold=0.7,
    key_sent_ratio=0.4
)


#### SUMMARIZER
summaryEngine = SummaryRun.RecursiveSummarizer(
    tokenizer=tokenizer,
    summarizer=summarizer,
    sum_device=summaryDevice,
    chunk_builder=chunkUnder,
    max_length=200,
    min_length=100,
    max_depth=4
)


#### SEARCHER
reranker = CrossEncoder(RERANK_MODEL, device=str(embeddDevice))
searchEngine = F_Searching.SemanticSearchEngine(
    indexer=indexer,
    reranker=reranker,
    device=str(embeddDevice),
    normalize=True,
    top_k=20,
    rerank_k=10,
    rerank_batch_size=16
)




## ==============================
## MAIN FLOW FUNCTIONS
## ==============================

### PREPROCESS

#### CHECKER
def pdfCheck(pdf_doc):
    is_good, metrics = checker.evaluate(pdf_doc)
    return is_good, metrics


#### EXTRACTOR
def extractRun(pdf_doc):
    extractedData = dataExtractor.extract(pdf_doc)
    RawDataDict = merger.merge(extractedData)
    return RawDataDict



### PROCESS FOR SEARCHING

#### STRUCT GETTER
def structRun(RawDataDict):
    markers =       structAnalyzer.extract_markers(RawDataDict)
    structures =    structAnalyzer.build_structures(markers)
    dedup =         structAnalyzer.deduplicate(structures)
    top =           structAnalyzer.select_top(dedup)
    RawLvlsDict =   structAnalyzer.extend_top(top, dedup)
    
    print(MU.json_convert(RawLvlsDict, pretty=True))
    return RawLvlsDict


#### STRUCT CHUNKER
def chunkRun(RawLvlsDict=None, RawDataDict=None):
    StructsDict = chunkBuilder.build(RawLvlsDict, RawDataDict)
    return StructsDict


#### SEGMENT CHUNKER
def SegmentRun(StructsDict, RawLvlsDict):
    first_key = list(RawLvlsDict[0].keys())[0]

    SegmentDict = []
    for item in StructsDict:
        value = item.get(first_key)
        if not value:
            continue
        
        if isinstance(value, list):
            value = " ".join(
                v.strip() for v in value
                if isinstance(v, str) and v.strip().lower() != "none"
            )
            if value.strip():
                SegmentDict.append(item)

        elif isinstance(value, str):
            text = value.strip()
            if text and text.lower() != "none":
                SegmentDict.append(item)

    for i, item in enumerate(SegmentDict, start=1):
        item["Index"] = i

    return SegmentDict


#### SCHEMA GETTER
def schemaRun(SegmentDict):
    SchemaDict = schemaExt.schemaRun(SegmentDict=SegmentDict)
    print(SchemaDict)
    return SchemaDict


#### INDEXER
def Indexing(SchemaDict):
    FaissIndex, Mapping, MapData, chunk_groups = faissIndexer.build_from_json(
        SegmentPath=SegmentPath,
        SchemaDict=SchemaDict,
        FaissPath=FaissPath,
        MapDataPath=MapDataPath,
        MappingPath=MappingPath,
        MapChunkPath=MapChunkPath
    )
    return FaissIndex, Mapping, MapData, chunk_groups


### PROCESS FOR CLASSIFICATION

#### RAW MERGER
def mergebyText(RawDataDict):
    merged_text = TP.merge_txt(RawDataDict, JsonKey, JsonField)
    return merged_text


#### SUMMARIZER
def summaryRun(merged_text):
    summarized = summaryEngine.summarize(merged_text, minInput = 256, maxInput = 1024)
    return summarized



### FINAL PROCESS

#### SEARCHER
def runSearch(query, faissIndex, Mapping, MapData, MapChunk):
    results = searchEngine.search(
        query=query,
        faissIndex=faissIndex,
        Mapping=Mapping,
        MapData=MapData,
        MapChunk=MapChunk,
        top_k=20
    )
    return results


#### RERANKER
def runRerank(query, results):
    reranked = searchEngine.rerank(
        query=query,
        results=results,
        top_k=10
    )
    return reranked




## ==============================
## MERGED FUNCTIONS
## ==============================

#### READ DATA
def ReadData(SegmentPath, FaissPath, MappingPath, MapDataPath, MapChunkPath):
    SegmentDict = MU.read_json(SegmentPath)
    FaissIndex = faiss.read_index(FaissPath)
    Mapping = MU.read_json(MappingPath)
    MapData = MU.read_json(MapDataPath)
    MapChunk = MU.read_json(MapChunkPath)
    return {
        "SegmentDict": SegmentDict,
        "FaissIndex": FaissIndex,
        "Mapping": Mapping,
        "MapData": MapData,
        "MapChunk": MapChunk
    }
    

#### READ PDF
def preReadPDF(PdfPath=None, PdfBytes=None):
    if PdfBytes is not None:
        pdf_doc = fitz.open(stream=PdfBytes, filetype="pdf")
    elif PdfPath is not None:
        pdf_doc = fitz.open(PdfPath)
    else:
        return None
    
    checker = QualityCheck.PDFQualityChecker()
    is_good, info = checker.evaluate(pdf_doc)
    print(info)
    if is_good:
        print("✅ Tiếp tục xử lý.")
    else:
        print("⚠️ Bỏ qua file này.")
        pdf_doc.close()
        return None
        
    RawDataDict = extractRun(pdf_doc)
    MU.write_json(RawDataDict, RawDataPath, indent=1)
    pdf_doc.close()
    
    return RawDataDict


#### PREPARE DATA
def PrepareData(SegmentPath, FaissPath, MappingPath, MapDataPath, MapChunkPath, RawDataDict=None):            
    if RawDataDict is not None:
        RawLvlsDict = structRun(RawDataDict)
        MU.write_json(RawLvlsDict, RawLvlsPath, indent=2)

        StructsDict = chunkRun(RawLvlsDict, RawDataDict)
        MU.write_json(StructsDict, StructsPath, indent=2)

        SegmentDict = SegmentRun(StructsDict, RawLvlsDict)
        MU.write_json(SegmentDict, SegmentPath, indent=2)
        
    elif MU.file_exists(SegmentPath):
        SegmentDict = MU.read_json(SegmentPath)
        
    else :
        return None, None, None, None, None
    
    SchemaDict = schemaRun(SegmentDict)
    MU.write_json(SchemaDict, SchemaPath, indent=2)

    FaissIndex, Mapping, MapData, chunk_groups = Indexing(SchemaDict)
    MU.write_json(Mapping, MappingPath, indent=2)
    MU.write_json(MapData, MapDataPath, indent=2)
    
    faiss.write_index(FaissIndex, FaissPath)
    MU.write_chunkmap(MapChunkPath, SegmentPath, chunk_groups)
    MapChunk = MU.read_json(MapChunkPath)
    
    print("\nCompleted!")
    
    return {
        "SegmentDict": SegmentDict,
        "FaissIndex": FaissIndex,
        "Mapping": Mapping,
        "MapData": MapData,
        "MapChunk": MapChunk
    }
    

#### SUMMARIZE
def summarizeDcmt(RawDataDict):
    merged_text = mergebyText(RawDataDict)
    summarized = summaryRun(merged_text)
    return summarized["summary_text"]


#### CLASSIFY
def classifyDocument(summaryText):
    readedData = ReadData(serviceSegmentPath, serviceFaissPath, serviceMappingPath, serviceMapDataPath, serviceMapChunkPath)
    serviceSegmentDict = readedData.get("SegmentDict")
    serviceFaissIndex = readedData.get("FaissIndex")
    serviceMapping = readedData.get("Mapping")
    serviceMapData = readedData.get("MapData")
    serviceMapChunk = readedData.get("MapChunk")
    
    searchRes = runSearch(summaryText, serviceFaissIndex, serviceMapping, serviceMapData, serviceMapChunk)
    reranked = runRerank(summaryText, searchRes)
    
    bestCategory = ChunkMapper.process_chunks_pipeline(reranked_results=reranked, SegmentDict=serviceSegmentDict, drop_fields=["Index"], fields=["Article"], n_chunks=1)
    bestArticles = [item["fields"].get("Article") for item in bestCategory["extracted_fields"]]
    bestArticle = bestArticles[0] if len(bestArticles) == 1 else ", ".join(bestArticles)
    return bestArticle




## ==============================
## SERVER DATA LOAD
## ==============================
print("Server is starting, loading main search index...")
try:
    # Tải dữ liệu chính (HNMU) để tìm kiếm
    g_readedData = ReadData(SegmentPath, FaissPath, MappingPath, MapDataPath, MapChunkPath)
    g_SegmentDict = g_readedData.get("SegmentDict")
    g_FaissIndex = g_readedData.get("FaissIndex")
    g_Mapping = g_readedData.get("Mapping")
    g_MapData = g_readedData.get("MapData")
    g_MapChunk = g_readedData.get("MapChunk")
    
    if g_FaissIndex:
        print(f"✅ Main search index '{infilename}' loaded successfully.")
    else:
        print(f"⚠️ Could not load main search index from {FaissPath}.")
        
except Exception as e:
    print(f"❌ CRITICAL: Failed to load main search index: {e}")
    g_FaissIndex = None

# Tải dữ liệu 'service' (Categories) để phân loại
print("Loading 'Categories' index for classification...")
try:
    g_serviceData = ReadData(serviceSegmentPath, serviceFaissPath, serviceMappingPath, serviceMapDataPath, serviceMapChunkPath)
    g_serviceSegmentDict = g_serviceData.get("SegmentDict")
    g_serviceFaissIndex = g_serviceData.get("FaissIndex")
    g_serviceMapping = g_serviceData.get("Mapping")
    g_serviceMapData = g_serviceData.get("MapData")
    g_serviceMapChunk = g_serviceData.get("MapChunk")
    
    if g_serviceFaissIndex:
        print("✅ 'Categories' index loaded successfully.")
    else:
        print("⚠️ Could not load 'Categories' index.")

except Exception as e:
    print(f"❌ CRITICAL: Failed to load 'Categories' index: {e}")
    g_serviceFaissIndex = None




## ==============================
## API PIPELINE FUNCTIONS
## ==============================

def process_pdf_pipeline(pdf_bytes):
    """
    Pipeline cho endpoint /process_pdf.
    Nhận PDF bytes -> tóm tắt -> phân loại.
    """
    print("Processing new PDF...")
    # 1. Trích xuất
    RawDataDict = preReadPDF(PdfPath=None, PdfBytes=pdf_bytes)
    if RawDataDict is None:
        print("PDF quality check failed or extraction failed.")
        return {
            "checkstatus": "failed",
            "summary": "",
            "category": "PDF không hợp lệ hoặc không thể trích xuất"
        }

    # 2. Tóm tắt
    print("Summarizing PDF...")
    summaryText = summarizeDcmt(RawDataDict)
    
    # 3. Phân loại (sử dụng global index 'service')
    print("Classifying PDF...")
    if not g_serviceFaissIndex:
        print("Cannot classify: 'Categories' index not loaded.")
        bestArticle = "Không thể phân loại (chưa tải index)"
    else:
        # Tái sử dụng hàm classifyDocument nhưng truyền index vào
        searchRes = runSearch(summaryText, g_serviceFaissIndex, g_serviceMapping, g_serviceMapData, g_serviceMapChunk)
        reranked = runRerank(summaryText, searchRes)
        
        bestCategory = ChunkMapper.process_chunks_pipeline(
            reranked_results=reranked, 
            SegmentDict=g_serviceSegmentDict, 
            drop_fields=["Index"], 
            fields=["Article"], 
            n_chunks=1
        )
        bestArticles = [item["fields"].get("Article") for item in bestCategory["extracted_fields"]]
        bestArticle = bestArticles[0] if bestArticles else "Không xác định"

    print(f"Done. Summary: {len(summaryText)} chars, Category: {bestArticle}")
    return {
        "checkstatus": "ok",
        "summary": summaryText,
        "category": bestArticle,
    }


def search_pipeline(query_text, k=10):
    """
    Pipeline cho endpoint /search.
    Nhận query -> tìm kiếm trên index chính (HNMU).
    """
    print(f"Searching for: '{query_text}'")
    if not g_FaissIndex:
        print("Cannot search: Main index not loaded.")
        raise Exception("Không thể tìm kiếm (chưa tải index chính)")

    # 1. Search và Rerank
    searchRes = runSearch(query_text, g_FaissIndex, g_Mapping, g_MapData, g_MapChunk)
    reranked = runRerank(query_text, searchRes)

    # 2. Map chunks và trích xuất
    chunkReturn = ChunkMapper.process_chunks_pipeline(
        reranked_results=reranked,
        SegmentDict=g_SegmentDict,
        drop_fields=["Index"],
        fields=None,
        n_chunks=k,
    )
    
    return chunkReturn.get("extracted_fields", [])