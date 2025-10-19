# main_pipeline.py
import fitz, os, faiss
from transformers import pipeline
from Config import Configs
from Config import ModelLoader as ML
from Libraries import Common_MyUtils as MU, Common_TextProcess as TP
from Libraries import PDF_ExtractData as ExtractData, PDF_MergeData as MergeData, PDF_QualityCheck as QualityCheck, Json_ChunkUnder as ChunkUnder
from Libraries import Faiss_Embedding as F_Embedding, Faiss_Searching as F_Searching
from Libraries import Summarizer_Runner as SummaryRun
from sentence_transformers import CrossEncoder

Checkpoint = "vinai/bartpho-syllable"
service = "Categories"
inputs = "BAD.pdf"
JsonKey = "paragraphs"
JsonField = "Text"

config = Configs.ConfigValues(service=service, inputs=inputs)
inputPath = config["inputPath"]
PdfPath = config["PdfPath"]
DocPath = config["DocPath"]
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
DATA_KEY = config["DATA_KEY"]
EMBE_KEY = config["EMBE_KEY"]
SEARCH_EGINE = config["SEARCH_EGINE"]
RERANK_MODEL = config["RERANK_MODEL"]
RESPON_MODEL = config["RESPON_MODEL"]
EMBEDD_MODEL = config["EMBEDD_MODEL"]
CHUNKS_MODEL = config["CHUNKS_MODEL"]
SUMARY_MODEL = config["SUMARY_MODEL"]
WORD_LIMIT = config["WORD_LIMIT"]

MODEL_DIR = "Models"
MODEL_ENCODE = "Sentence_Transformer"
MODEL_SUMARY = "Summarizer"
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

exceptData = loadHardcodes(exceptPath, wanted=["common_words", "proper_names", "abbreviations"])
markerData = loadHardcodes(markerPath, wanted=["keywords", "markers"])
statusData = loadHardcodes(statusPath, wanted=["brackets", "sentence_ends"])

Loader = ML.ModelLoader()
indexer, embeddDevice = Loader.load_encoder(EMBEDD_MODEL, EMBEDD_CACHED_MODEL)
chunker, chunksDevice = Loader.load_encoder(CHUNKS_MODEL, CHUNKS_CACHED_MODEL)

tokenizer, summarizer, summaryDevice = Loader.load_summarizer(SUMARY_MODEL, SUMARY_CACHED_MODEL)

Mapping = MU.read_json(MappingPath)
MapData = MU.read_json(MapDataPath)
MapChunk = MU.read_json(MapChunkPath)
faissIndex = faiss.read_index(FaissPath)

dataExtractor = ExtractData.B1Extractor(
    exceptData,
    markerData,
    statusData,
    proper_name_min_count=10
)

chunkUnder = ChunkUnder.ChunkUndertheseaBuilder(
    embedder=indexer,
    device=embeddDevice,
    min_words=256,
    max_words=768,
    sim_threshold=0.7,
    key_sent_ratio=0.4
)

summarizer_engine = SummaryRun.RecursiveSummarizer(
    tokenizer=tokenizer,
    summarizer=summarizer,
    sum_device=summaryDevice,
    chunk_builder=chunkUnder,
    max_length=200,
    min_length=100,
    max_depth=4
)

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

def extractRun(pdf_doc):
    extractedData = dataExtractor.extract(pdf_doc)
    RawDataDict = MergeData.mergeLinesToParagraphs(extractedData)
    return RawDataDict

def runSearch(query):
    results = searchEngine.search(
        query=query,
        faissIndex=faissIndex,
        Mapping=Mapping,
        MapData=MapData,
        top_k=20
    )
    return results

def runRerank(query, results):
    reranked = searchEngine.rerank(
        query=query,
        results=results,
        top_k=10
    )
    return reranked

def mainRun(pdf_doc):
    RawDataDict = extractRun(pdf_doc)
    full_text = TP.merge_txt(RawDataDict, JsonKey, JsonField)
    summarized = summarizer_engine.summarize(full_text, minInput = 256, maxInput = 1024)
    print(summarized["summary_text"])
    resuls = runSearch(summarized["summary_text"])
    reranked = runRerank(summarized["summary_text"], resuls)
    best_text = reranked[0]["text"] if reranked else ""
    print(best_text)
    return best_text


def fileProcess(pdf_bytes):
    """Nhận file PDF bytes, thực hiện pipeline chính."""
    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    checker = QualityCheck.PDFQualityChecker()
    is_good, metrics = checker.evaluate(pdf_doc)
    print(metrics["check_mess"])

    if not is_good:
        print("⚠️ Bỏ qua file này.")
        check_status = "deline"
        summaryText = metrics["check_mess"]
        best_text = ""
        reranked = ""
    else:
        print("✅ Tiếp tục xử lý.")
        check_status = "accept",
        RawDataDict = extractRun(pdf_doc)
        full_text = TP.merge_txt(RawDataDict, JsonKey, JsonField)
        summarized = summarizer_engine.summarize(full_text, minInput = 256, maxInput = 1024)
        summaryText = summarized["summary_text"]
        resuls = runSearch(summaryText)
        reranked = runRerank(summaryText, resuls)
        best_text = reranked[0]["text"] if reranked else ""

    pdf_doc.close()
    return {
        "checkstatus": check_status,
        "summary": summaryText,
        "category": best_text,
        "reranked": reranked[:5] if reranked else []
    }
