---
title: Doc Ai Api

emoji: 📊

colorFrom: yellow

colorTo: red

sdk: docker

pinned: false
---
Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference

---

# [PDF] PROCESSOR

```
PDF PROCESSOR
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
├── Database/			*.json - faiss
│
├── Demo/
│ ├── Assets
│ │ ├── Style.css
│ │ └── Script.js
│ └── index.html
│
├── Documents/
│ ├── *.xlsx			# FileName = Service
│ └── *.pdf			# FileName = Service
│
├── Environment/
│ └── *.yml			# Read-only
│
├── Libraries/
│ ├── Common_*.py		# Common Modules
│ ├── Faiss_*.py		# Vector Embedding + Searching
│ ├── Json_*.py			# Chunk Processor
│ ├── PDF_*.py			# PDF Extractor
│ └── Summarizer_*.py		# Texts Summary
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
├── _*ipynb			# Notebooks - Test
│
├── .gitattributes
├── .gitignore
│
├── app.py			# BE Deployed Runner 	--Call to App_Caller.py
├── appCalled.py		# Backend Main 		--Extract - Filter - Chunk - Summary - Search
├── appTest.py			# BE Local Runner 	--Call to App_Caller.py
│
├── Dockerfile
├── README.md
├── requirements.txt		# Virtual Environment Resource --Deploy
├── requirements.yml		# Virtual Environment Resource --Local
└── start.sh

```

---

# USAGES

1. conda env create -f requirements_cuda12.yml
2. conda activate master
3. uvicorn api:app --host 0.0.0.0 --port 8000
4. Demo > index.html >

---
