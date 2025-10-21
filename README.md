---
title: Doc Ai Api

emoji: 📊

colorFrom: yellow

colorTo: red

sdk: docker

pinned: false
---
Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference

# ENGINE XỬ LÝ TÀI LIỆU [PDF]

```
RAG
│
├── Assets/
│ ├── ex.exceptions.json
│ ├── ex.markers.json
│ └── ex.status.json
│
├── Config/
│ ├── Config.json
│ ├── Configs.py
│ └── ModelLoader.py
│
├── Database/
│ └── FolderName = Sevices
│
├── Demo/
│ ├── Assets
│ │ ├── Style.css
│ │ └── Script.js
│ └── index.html
│
├── Documents/
│ ├── *.xlsx	# FileName = Service
│ └── *.pdf	# FileName = Service
│
├── Environment/
│ └── *.yml
│
├── Libraries/
│ ├── Common_*.py	# Common Modules
│ ├── PDF_*.py		# PDF Extractor
│ ├── Json_*.py		# Chunk Processor
│ ├── Summarizer_*.py	# Texts Summary
│ └── Faiss_*.py	# Vector Embedding + Searching
│
├── Models/
│ ├── Sentence_Transformer/	# Transformer Cached Models
│ └── Summarizer/		# Summarizer Cached Models
│
├── Private/
│ ├── Data/			# Datasets
│ ├── Images/			# Charts, Imgs...
│ ├── Prompts/			# Prompt txt Files
│ ├── Data/			# Test input Files
│ └── pdfGenerate.ipynb		# Bad version pdf generator
│
├── .gitignore
│
├── App_Caller.py		# Backend Main --Extract - Filter - Chunk - Summary - Search
├── App_Run.py			# API Runner --Call to App_Caller.py
├── Pipeline_PDFprocess.ipynb	# Notebook --Extract - Filter - Chunk - Summary - Search
├── Pipeline_Summarizer.ipynb	# Notebook --Use to Train Summarizers
├── Pipeline_VectorGener.ipynb	# Notebook --Extract - Chunk - Embedding to Faiss Index
├── Pipeline_VectorSearch.ipynb	# Notebook --Search highest faiss score for queries
│
└── README.md
```

---

---
