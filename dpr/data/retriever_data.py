import collections
import csv
import hydra
import json
import jsonlines
import logging

from omegaconf import DictConfig
from typing import Dict
from dpr.data.biencoder_data import BiEncoderPassage, split_tables_to_chunks
from dpr.data.tables import read_nq_tables_jsonl

logger = logging.getLogger(__name__)
QASample = collections.namedtuple("QuerySample", ["query", "id", "answers"])
TableChunk = collections.namedtuple("TableChunk", ["text", "title", "table_id"])


class QASrc(object):
    def __init__(self, selector: DictConfig = None, special_query_token: str = None):
        self.data = None
        self.selector = hydra.utils.instantiate(selector) if selector else None
        self.special_query_token = special_query_token

    def __getitem__(self, index):
        return self.data[index]

    def __len__(self):
        return len(self.data)


class CsvQASrc(QASrc):
    def __init__(
        self,
        file: str,
        question_col: int = 0,
        answers_col: int = 1,
        id_col: int = -1,
        selector: DictConfig = None,
        special_query_token: str = None,
    ):
        super().__init__(selector=selector, special_query_token=special_query_token)
        self.question_col = question_col
        self.answers_col = answers_col
        self.id_col = id_col
        self.file = file

    def load_data(self):
        data = []
        with open(self.file) as ifile:
            reader = csv.reader(ifile, delimiter="\t")
            for row in reader:
                question = row[self.question_col]
                answers = eval(row[self.answers_col])
                id = None
                if self.id_col >= 0:
                    id = row[self.id_col]
                data.append(QASample(question, id, answers))

        self.data = data


class JsonlQASrc(QASrc):
    def __init__(
        self,
        file: str,
        question_attr: str = "question",
        answers_attr: str = "answers",
        id_attr: str = "id",
    ):
        super().__init__(selector=None)
        self.question_attr = question_attr
        self.answers_attr = answers_attr
        self.id_attr = id_attr
        self.file = file

    def load_data(self):
        data = []
        with jsonlines.open(self.file, mode="r") as jsonl_reader:
            for jline in jsonl_reader:
                question = jline[self.question_attr]
                answers = jline[self.answers_attr]
                id = None
                if self.id_attr in jline:
                    id = jline[self.id_attr]
                data.append(QASample(question, id, answers))
        self.data = data


class KiltCsvQASrc(CsvQASrc):
    def __init__(
        self,
        file: str,
        kilt_gold_file: str,
        question_col: int = 0,
        answers_col: int = 1,
        id_col: int = -1,
        selector: DictConfig = None,
        special_query_token: str = None,
    ):
        super().__init__(
            file,
            question_col,
            answers_col,
            id_col,
            selector=selector,
            special_query_token=special_query_token,
        )
        self.kilt_gold_file = kilt_gold_file


# TODO: super class for CtxSrc ?
class CsvCtxSrc(object):
    def __init__(
        self,
        file: str,
        id_col: int = 0,
        text_col: int = 1,
        title_col: int = 2,
        id_prefix: str = None,
    ):
        self.text_col = text_col
        self.title_col = title_col
        self.id_col = id_col
        self.file = file
        self.id_prefix = id_prefix

    def load_data_to(self, ctxs: Dict):
        ctxs_dict = {}
        with open(self.file) as ifile:
            reader = csv.reader(ifile, delimiter="\t")
            for row in reader:
                if row[self.id_col] != "id":
                    if self.id_prefix:
                        sample_id = self.id_prefix + str(row[self.id_col])
                    else:
                        sample_id = row[self.id_col]
                    ctxs_dict[sample_id] = BiEncoderPassage(
                        row[self.text_col], row[self.title_col]
                    )

        ctxs.update(ctxs_dict)


class KiltCsvCtxSrc(CsvCtxSrc):
    def __init__(
        self,
        file: str,
        id_col: int = 0,
        text_col: int = 1,
        title_col: int = 2,
        id_prefix: str = None,
    ):
        super().__init__(file, id_col, text_col, title_col, id_prefix)

    def convert_to_kilt(self, kilt_gold_file, dpr_output, kilt_out_file):
        logger.info("Converting to KILT format file: %s", dpr_output)

        with open(dpr_output, "rt") as fin:
            dpr_output = json.load(fin)

        with jsonlines.open(kilt_gold_file, "r") as reader:
            kilt_gold_file = list(reader)
        assert len(kilt_gold_file) == len(dpr_output)

        chunk_id_to_wikipedia_id = []
        with open(self.file, "rt", newline="") as fin:
            reader = csv.DictReader(fin, delimiter="\t")
            for i, row in enumerate(reader):
                assert i == int(row["id"])
                chunk_id_to_wikipedia_id.append(int(row["wikipedia_id"]))

        with jsonlines.open(kilt_out_file, mode="w") as writer:
            for dpr_entry, kilt_gold_entry in zip(dpr_output, kilt_gold_file):
                assert dpr_entry["question"] == kilt_gold_entry["input"]
                provenance = []
                for ctx in dpr_entry["ctxs"]:
                    provenance.append(
                        {"wikipedia_id": str(chunk_id_to_wikipedia_id[int(ctx["id"])])}
                    )
                kilt_entry = {
                    "id": kilt_gold_entry["id"],
                    "input": dpr_entry["question"],
                    "output": [{"provenance": provenance}],
                }
                writer.write(kilt_entry)

        logger.info("Saved KILT formatted results to: %s", kilt_out_file)


class JsonlTablesCtxSrc(object):
    def __init__(
        self,
        file: str,
        tables_chunk_sz: int = 100,
        split_type: str = "type1",
        id_prefix: str = None,
    ):
        self.tables_chunk_sz = tables_chunk_sz
        self.split_type = split_type
        self.file = file
        self.id_prefix = id_prefix

    def load_data_to(self, ctxs: Dict):
        docs = {}
        logger.info("Parsing Tables data from: %s", self.file)
        tables_dict = read_nq_tables_jsonl(self.file)
        table_chunks = split_tables_to_chunks(
            tables_dict, self.tables_chunk_sz, split_type=self.split_type
        )
        for chunk in table_chunks:
            # "tab." + str(chunk[0])
            sample_id = self.id_prefix + str(chunk[0])
            docs[sample_id] = TableChunk(chunk[1], chunk[2], chunk[3])
        logger.info("Loaded %d tables chunks", len(docs))
        ctxs.update(docs)