import os
import json
import numpy as np
import pandas as pd
from typing import Optional, Dict, Any, Union

import evaluate
from datasets import Dataset, DatasetDict, load_from_disk

from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    EarlyStoppingCallback,
    set_seed,
)


class SummarizationTrainer:
    """
    Fine-tune mô hình tóm tắt (Seq2Seq) đa dụng — thống nhất interface:
    run(Checkpoint, ModelPath, DataPath | dataset, tokenizer)
    """

    def __init__(
        self,
        Max_Input_Length: int = 1024,
        Max_Target_Length: int = 256,
        prefix: str = "",
        input_column: str = "article",
        target_column: str = "summary",
        Learning_Rate: float = 3e-5,
        Weight_Decay: float = 0.01,
        Batch_Size: int = 8,
        Num_Train_Epochs: int = 3,
        gradient_accumulation_steps: int = 1,
        warmup_ratio: float = 0.05,
        lr_scheduler_type: str = "linear",
        seed: int = 42,
        num_beams: int = 4,
        generation_max_length: Optional[int] = None,
        fp16: bool = True,
        early_stopping_patience: int = 2,
        logging_steps: int = 200,
        report_to: str = "none",
    ):
        # Hyperparams
        self.Max_Input_Length = Max_Input_Length
        self.Max_Target_Length = Max_Target_Length
        self.prefix = prefix
        self.input_column = input_column
        self.target_column = target_column

        self.Learning_Rate = Learning_Rate
        self.Weight_Decay = Weight_Decay
        self.Batch_Size = Batch_Size
        self.Num_Train_Epochs = Num_Train_Epochs
        self.gradient_accumulation_steps = gradient_accumulation_steps
        self.warmup_ratio = warmup_ratio
        self.lr_scheduler_type = lr_scheduler_type
        self.seed = seed

        self.num_beams = num_beams
        self.generation_max_length = generation_max_length
        self.fp16 = fp16
        self.early_stopping_patience = early_stopping_patience
        self.logging_steps = logging_steps
        self.report_to = report_to

        self._rouge = evaluate.load("rouge")
        self._tokenizer = None
        self._model = None

    # =========================================================
    # 1️⃣  Đọc dữ liệu JSONL hoặc Arrow
    # =========================================================
    def _load_jsonl_to_datasetdict(self, DataPath: str) -> DatasetDict:
        print(f"Đang tải dữ liệu từ {DataPath} ...")
        data_list = []
        with open(DataPath, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data_list.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        df = pd.DataFrame(data_list)
        if self.input_column not in df or self.target_column not in df:
            raise ValueError(f"File {DataPath} thiếu cột {self.input_column}/{self.target_column}")
        df = df[[self.input_column, self.target_column]].dropna()

        dataset = Dataset.from_pandas(df, preserve_index=False)
        split = dataset.train_test_split(test_size=0.1, seed=self.seed)
        print(f"✔ Dữ liệu chia: {len(split['train'])} train / {len(split['test'])} validation")
        return DatasetDict({"train": split["train"], "validation": split["test"]})

    def _ensure_datasetdict(self, dataset: Optional[Union[Dataset, DatasetDict]], DataPath: Optional[str]) -> DatasetDict:
        if dataset is not None:
            if isinstance(dataset, DatasetDict):
                return dataset
            if isinstance(dataset, Dataset):
                split = dataset.train_test_split(test_size=0.1, seed=self.seed)
                return DatasetDict({"train": split["train"], "validation": split["test"]})
            raise TypeError("dataset phải là datasets.Dataset hoặc datasets.DatasetDict.")
        if DataPath:
            if os.path.isdir(DataPath):
                print(f"Load DatasetDict từ thư mục Arrow: {DataPath}")
                return load_from_disk(DataPath)
            return self._load_jsonl_to_datasetdict(DataPath)
        raise ValueError("Cần truyền dataset hoặc DataPath")

    # =========================================================
    # 2️⃣  Token hóa
    # =========================================================
    def _preprocess_function(self, examples):
        inputs = examples[self.input_column]
        if self.prefix:
            inputs = [self.prefix + x for x in inputs]
        model_inputs = self._tokenizer(inputs, max_length=self.Max_Input_Length, truncation=True)
        with self._tokenizer.as_target_tokenizer():
            labels = self._tokenizer(examples[self.target_column], max_length=self.Max_Target_Length, truncation=True)
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    # =========================================================
    # 3️⃣  Tính điểm ROUGE
    # =========================================================
    def _compute_metrics(self, eval_pred):
        preds, labels = eval_pred
        decoded_preds = self._tokenizer.batch_decode(preds, skip_special_tokens=True)
        labels = np.where(labels != -100, labels, self._tokenizer.pad_token_id)
        decoded_labels = self._tokenizer.batch_decode(labels, skip_special_tokens=True)
        result = self._rouge.compute(predictions=decoded_preds, references=decoded_labels, use_stemmer=True)
        return {k: round(v * 100, 4) for k, v in result.items()}

    # =========================================================
    # 4️⃣  Chạy huấn luyện
    # =========================================================
    def run(
        self,
        Checkpoint: str,
        ModelPath: str,
        DataPath: Optional[str] = None,
        dataset: Optional[Union[Dataset, DatasetDict]] = None,
        tokenizer: Optional[AutoTokenizer] = None,
    ):
        set_seed(self.seed)
        ds = self._ensure_datasetdict(dataset, DataPath)
        self._tokenizer = tokenizer or AutoTokenizer.from_pretrained(Checkpoint)
        print(f"Tải model checkpoint: {Checkpoint}")
        self._model = AutoModelForSeq2SeqLM.from_pretrained(Checkpoint)

        print("Tokenizing dữ liệu ...")
        tokenized = ds.map(self._preprocess_function, batched=True)
        data_collator = DataCollatorForSeq2Seq(tokenizer=self._tokenizer, model=self._model)
        gen_max_len = self.generation_max_length or self.Max_Target_Length

        training_args = Seq2SeqTrainingArguments(
            output_dir=ModelPath,
            evaluation_strategy="epoch",
            save_strategy="epoch",
            learning_rate=self.Learning_Rate,
            per_device_train_batch_size=self.Batch_Size,
            per_device_eval_batch_size=self.Batch_Size,
            weight_decay=self.Weight_Decay,
            num_train_epochs=self.Num_Train_Epochs,
            predict_with_generate=True,
            generation_max_length=gen_max_len,
            generation_num_beams=self.num_beams,
            fp16=self.fp16,
            gradient_accumulation_steps=self.gradient_accumulation_steps,
            warmup_ratio=self.warmup_ratio,
            lr_scheduler_type=self.lr_scheduler_type,
            logging_steps=self.logging_steps,
            load_best_model_at_end=True,
            metric_for_best_model="rougeL",
            greater_is_better=True,
            save_total_limit=3,
            report_to=self.report_to,
        )

        trainer = Seq2SeqTrainer(
            model=self._model,
            args=training_args,
            train_dataset=tokenized["train"],
            eval_dataset=tokenized["validation"],
            tokenizer=self._tokenizer,
            data_collator=data_collator,
            compute_metrics=self._compute_metrics,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=self.early_stopping_patience)],
        )

        print("\n🚀 BẮT ĐẦU HUẤN LUYỆN ...")
        trainer.train()
        print("✅ HUẤN LUYỆN HOÀN TẤT.")
        trainer.save_model(ModelPath)
        self._tokenizer.save_pretrained(ModelPath)
        print(f"💾 Đã lưu model & tokenizer tại: {ModelPath}")
        return trainer

    # =========================================================
    # 5️⃣  Sinh tóm tắt
    # =========================================================
    def generate(self, text: str, max_new_tokens: Optional[int] = None) -> str:
        if self._model is None or self._tokenizer is None:
            raise RuntimeError("Model/tokenizer chưa khởi tạo, hãy gọi run() trước.")
        prompt = (self.prefix + text) if self.prefix else text
        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=self.Max_Input_Length)
        gen_len = max_new_tokens or self.Max_Target_Length
        outputs = self._model.generate(**inputs, max_new_tokens=gen_len, num_beams=self.num_beams)
        return self._tokenizer.decode(outputs[0], skip_special_tokens=True)

    # =========================================================
    # 6️⃣  Load lại Dataset Arrow
    # =========================================================
    @staticmethod
    def load_local_dataset(DataPath: str) -> DatasetDict:
        return load_from_disk(DataPath)
