# main_pipeline.py
import fitz, faiss
from transformers import pipeline
from Config import Configs
from Config import ModelLoader as ML
from Libraries import Common_MyUtils as MU, Common_TextProcess as TP
from Libraries import PDF_ExtractData as ExtractData, PDF_MergeData as MergeData, PDF_QualityCheck as QualityCheck
from Libraries import Json_ChunkUnder as ChunkUnder
from Libraries import Faiss_Searching as F_Searching
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
MODEL_TYPE = "Sentence_Transformer"
EMBEDD_CACHED_MODEL = f"{MODEL_DIR}/{MODEL_TYPE}/{EMBEDD_MODEL}"
CHUNKS_CACHED_MODEL = F"{MODEL_DIR}/{MODEL_TYPE}/{CHUNKS_MODEL}"
SUMARY_CACHED_MODEL = f"{MODEL_DIR}/{MODEL_TYPE}/{SUMARY_MODEL}"

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

indexer, embeddDevice = ML.init_sentence_model(EMBEDD_MODEL, EMBEDD_CACHED_MODEL)
chunker, chunksDevice = ML.init_sentence_model(CHUNKS_MODEL, CHUNKS_CACHED_MODEL)

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
    embedder=chunker,
    min_words=512,
    max_words=1024,
    sim_threshold=0.7
)

reranker = CrossEncoder(RERANK_MODEL, device=str(embeddDevice))
engine = F_Searching.SemanticSearchEngine(
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

def modelTest(sample_text=None, ModelPath=None, max_length=256, min_length=64):
    summarizer_pipeline = pipeline("summarization", model=ModelPath)
    summary = summarizer_pipeline(
        sample_text,
        max_length=max_length,
        min_length=min_length,
        do_sample=False,
        num_beams=4,
        no_repeat_ngram_size=3,
        early_stopping=True
    )
    return summary[0]['summary_text']

def summarize_recursive(text, depth=0, max_depth=5):
    word_count = len(text.split())
    indent = "  " * depth
    print(f"{indent}🔹 Level {depth}: {word_count} từ")

    if word_count < 512:
        return text
    elif word_count < 1024:
        return modelTest(text, SUMARY_CACHED_MODEL, MAX_TARGET, MIN_TARGET)
    else:
        chunks = chunkUnder.build(text)
        summaries = []

        for item in chunks:
            content = item["Content"]
            idx = item.get("Index", "?")
            print(f"{indent}  🔸 Chunk {idx}: {len(content.split())} từ")
            try:
                sub_summary = modelTest(content, SUMARY_CACHED_MODEL, MAX_TARGET, MIN_TARGET)
            except Exception as e:
                return "Bruh"
            
            summaries.append(sub_summary)

        merged_summary = "\n".join(summaries)
        merged_len = len(merged_summary.split())
        if merged_len > 1024 and depth < max_depth:
            return summarize_recursive(merged_summary, depth + 1, max_depth)
        
        return merged_summary
    
def runSearch(query):
    results = engine.search(
        query=query,
        faissIndex=faissIndex,
        Mapping=Mapping,
        MapData=MapData,
        top_k=20
    )
    return results

def runRerank(query, results):
    reranked = engine.rerank(
        query=query,
        results=results,
        top_k=10
    )
    return reranked

def mainRun(pdf_doc):
    RawDataDict = extractRun(pdf_doc)
    full_text = TP.merge_txt(RawDataDict, JsonKey, JsonField)
    if len(full_text.split()) > 512:
        final_summary = summarize_recursive(text=full_text)
    else:
        final_summary = modelTest(full_text, SUMARY_CACHED_MODEL, MAX_TARGET, MIN_TARGET)
    print("\n✨ FINAL SUMMARY ✨\n")
    print(final_summary)
    resuls = runSearch(final_summary)
    reranked = runRerank(final_summary, resuls)
    best_text = reranked[0]["text"] if reranked else ""
    print(best_text)
    return best_text


def fileProcess(pdf_bytes):
    """Nhận file PDF bytes, thực hiện pipeline chính."""
    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    checker = QualityCheck.PDFQualityChecker()
    is_good, info = checker.evaluate(pdf_doc)
    print(info["status"])

    if not is_good:
        print("⚠️ Bỏ qua file này.")
        check_status = "deline"
        final_summary = ""
        best_text = ""
        reranked = []
    else:
        print("✅ Tiếp tục xử lý.")
        check_status = "accept",
        RawDataDict = extractRun(pdf_doc)
        full_text = TP.merge_txt(RawDataDict, JsonKey, JsonField)
        # 🔹 Summarization
        if len(full_text.split()) > 512:
            final_summary = summarize_recursive(text=full_text)
        else:
            final_summary = modelTest(full_text, SUMARY_CACHED_MODEL, MAX_TARGET, MIN_TARGET)
        # 🔹 Search + Rerank
        resuls = runSearch(final_summary)
        reranked = runRerank(final_summary, resuls)
        best_text = reranked[0]["text"] if reranked else ""

    pdf_doc.close()
    return {
        "status": check_status,
        "summary": final_summary,
        "category": best_text,
        "reranked": reranked[:5] if reranked else []
    }
