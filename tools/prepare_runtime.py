# [INPUT]: 依赖已校验的 SQLite 题库、RapidOCR 模型清单与官方模型文件。
# [OUTPUT]: 生成精简运行题库与离线模型，记录来源和 SHA-256。
# [POS]: tools 的资源准备入口；运行包不包含原始采集数据或默认大模型。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import hashlib
import json
import shutil
import sqlite3
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    ("det.onnx", "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/onnx/PP-OCRv5/det/ch_PP-OCRv5_mobile_det.onnx", "4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae"),
    ("rec.onnx", "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.4.0/onnx/PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile_infer.onnx", "5825fc7ebf84ae7a412be049820b4d86d77620f204a041697b0494669b1742c5"),
)


def download(item):
    name, url, expected = item
    target = ROOT / "models" / name
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        temporary = target.with_suffix(".download")
        request = urllib.request.Request(url, headers={"User-Agent": "TrainerLevel3Build/0.2"})
        with urllib.request.urlopen(request, timeout=45) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
            temporary.unlink()
            raise ValueError("模型摘要与官方清单不符：" + name)
        temporary.replace(target)
    return {"file": name, "url": url, "sha256": expected, "bytes": target.stat().st_size}


def main():
    import rapidocr
    models_dir = Path(rapidocr.__file__).parent / "models"
    with ThreadPoolExecutor(max_workers=2) as pool:
        manifest = list(pool.map(download, MODELS))
    for source_name, target_name in (("ch_ppocr_mobile_v2.0_cls_infer.onnx", "cls.onnx"), ("ppocrv5_dict.txt", "keys.txt")):
        target = ROOT / "models" / target_name
        shutil.copyfile(models_dir / source_name, target)
        manifest.append({"file": target_name, "source": "rapidocr==3.4.2/" + source_name,
                         "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "bytes": target.stat().st_size})
    (ROOT / "models/manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    destination = ROOT / "bank.sqlite3"
    temporary = ROOT / ".bank.sqlite3.tmp"
    if temporary.exists():
        temporary.unlink()
    with sqlite3.connect(str(ROOT / "question_bank/questions.sqlite3")) as source, sqlite3.connect(str(temporary)) as target:
        target.execute("CREATE TABLE questions(id INTEGER PRIMARY KEY,type_base TEXT,stem_text TEXT,options_json TEXT,answer_keys_json TEXT,answer_contents_json TEXT,status TEXT)")
        source_rows = source.execute("SELECT id,type_base,stem_text,options_json,answer_keys_json,answer_contents_json,status FROM questions").fetchall()
        target.executemany("INSERT INTO questions VALUES(?,?,?,?,?,?,?)", source_rows)
        target.execute("PRAGMA user_version=1")
        target.commit()
        assert target.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    temporary.replace(destination)
    print(json.dumps({"questions": len(source_rows), "database_bytes": destination.stat().st_size,
                      "model_bytes": sum(item["bytes"] for item in manifest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
