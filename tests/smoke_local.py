"""Run inside the derived image with /models mounted; no network or VLM required."""
import json
import math
import time
from openviking.models.embedder.local_embedders import LocalDenseEmbedder

start = time.monotonic()
model = LocalDenseEmbedder(model_path='/models/bge-small-zh-v1.5-f16.gguf')
loaded = time.monotonic()
texts = ['飞牛 NAS 可以通过 Docker 容器部署应用并保存文件。',
         '香蕉和苹果是常见水果，可以制作果汁。',
         '篮球比赛需要投篮得分。']
vectors = [model.embed(text).dense_vector for text in texts]
query = model.embed('如何在 NAS 上部署 Docker 应用？', is_query=True).dense_vector
def similarity(a, b):
    return sum(x*y for x, y in zip(a, b)) / math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
scores = [similarity(query, vector) for vector in vectors]
assert all(len(vector) == 512 for vector in [query, *vectors])
assert all(math.isfinite(x) for vector in [query, *vectors] for x in vector)
assert max(range(len(scores)), key=scores.__getitem__) == 0, scores
print(json.dumps(dict(dimension=512, load_seconds=round(loaded-start, 3),
                     inference_seconds=round(time.monotonic()-loaded, 3), scores=scores,
                     passed=True), ensure_ascii=False))
model.close()
