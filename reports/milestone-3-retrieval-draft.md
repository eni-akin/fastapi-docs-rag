# Draft three-mode retrieval comparison

Snapshot: `279777ae-c949-4cae-8403-2224b314903f`; dataset hash: `f63b73c746a48fea5307d80148ac56ae934ea0f500dfe18c81e958cc19dea50e`.
Records: 60; human approved: 0.

60 of 60 labels await human approval. Retrieval overlap is not answer sufficiency; unsupported questions may still return neighbors.

| Category | Mode | Positive N | Recall@10 | MRR@10 | nDCG@10 | Group coverage@10 | Complete coverage |
|---|---|---:|---:|---:|---:|---:|---:|
| all | keyword | 45 | 0.030 | 0.015 | 0.020 | 0.044 | 0.044 |
| all | vector | 45 | 0.670 | 0.477 | 0.499 | 0.622 | 0.556 |
| all | hybrid | 45 | 0.670 | 0.504 | 0.513 | 0.622 | 0.556 |
| direct_lookup | keyword | 15 | 0.022 | 0.011 | 0.017 | 0.067 | 0.067 |
| direct_lookup | vector | 15 | 0.622 | 0.350 | 0.402 | 0.533 | 0.533 |
| direct_lookup | hybrid | 15 | 0.622 | 0.407 | 0.426 | 0.533 | 0.533 |
| paraphrase | keyword | 15 | 0.067 | 0.033 | 0.042 | 0.067 | 0.067 |
| paraphrase | vector | 15 | 0.856 | 0.628 | 0.677 | 0.800 | 0.800 |
| paraphrase | hybrid | 15 | 0.856 | 0.650 | 0.693 | 0.800 | 0.800 |
| multi_section | keyword | 15 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| multi_section | vector | 15 | 0.533 | 0.455 | 0.419 | 0.533 | 0.333 |
| multi_section | hybrid | 15 | 0.533 | 0.455 | 0.419 | 0.533 | 0.333 |
| unsupported | keyword | 0 | — | — | — | — | — |
| unsupported | vector | 0 | — | — | — | — | — |
| unsupported | hybrid | 0 | — | — | — | — | — |

The hybrid ranking reuses one keyword and one vector candidate list per question. The vector stage includes one query encode. Categories include related questions; family count and repeated families are recorded in JSON.

## Questions with incomplete proposed fact coverage

- `dev-01` (direct_lookup): {'keyword': ['support'], 'vector': ['support'], 'hybrid': ['support']}
- `dev-02` (direct_lookup): {'keyword': ['support']}
- `dev-03` (direct_lookup): {'keyword': ['support']}
- `dev-04` (paraphrase): {'keyword': ['support']}
- `dev-05` (direct_lookup): {'keyword': ['support']}
- `dev-06` (direct_lookup): {'keyword': ['support'], 'vector': ['support'], 'hybrid': ['support']}
- `dev-08` (direct_lookup): {'keyword': ['support'], 'vector': ['support'], 'hybrid': ['support']}
- `dev-09` (direct_lookup): {'keyword': ['support'], 'vector': ['support'], 'hybrid': ['support']}
- `dev-10` (direct_lookup): {'keyword': ['support'], 'vector': ['support'], 'hybrid': ['support']}
- `dev-11` (paraphrase): {'keyword': ['support'], 'vector': ['support'], 'hybrid': ['support']}
- `dev-12` (direct_lookup): {'keyword': ['support'], 'vector': ['support'], 'hybrid': ['support']}
- `dev-13` (paraphrase): {'keyword': ['support'], 'vector': ['support'], 'hybrid': ['support']}
- `dev-14` (direct_lookup): {'keyword': ['support'], 'vector': ['support'], 'hybrid': ['support']}
- `dev-15` (paraphrase): {'keyword': ['support']}
- `dev-16` (paraphrase): {'keyword': ['support'], 'vector': ['support'], 'hybrid': ['support']}
- `dev-17` (direct_lookup): {'keyword': ['support']}
- `dev-18` (direct_lookup): {'keyword': ['support']}
- `dev-21` (direct_lookup): {'keyword': ['fact-1']}
- `dev-22` (direct_lookup): {'keyword': ['fact-1']}
- `dev-23` (multi_section): {'keyword': ['fact-1', 'fact-2'], 'vector': ['fact-2'], 'hybrid': ['fact-2']}
- `dev-24` (paraphrase): {'keyword': ['fact-1']}
- `dev-25` (paraphrase): {'keyword': ['fact-1']}
- `dev-26` (paraphrase): {'keyword': ['fact-1']}
- `dev-27` (paraphrase): {'keyword': ['fact-1']}
- `dev-29` (paraphrase): {'keyword': ['fact-1']}
- `dev-30` (paraphrase): {'keyword': ['fact-1']}
- `dev-31` (paraphrase): {'keyword': ['fact-1']}
- `dev-32` (paraphrase): {'keyword': ['fact-1']}
- `dev-33` (paraphrase): {'keyword': ['fact-1']}
- `dev-34` (multi_section): {'keyword': ['fact-1', 'fact-2'], 'vector': ['fact-1'], 'hybrid': ['fact-1']}
- `dev-35` (multi_section): {'keyword': ['fact-1', 'fact-2'], 'vector': ['fact-2'], 'hybrid': ['fact-2']}
- `dev-36` (multi_section): {'keyword': ['fact-1', 'fact-2']}
- `dev-37` (multi_section): {'keyword': ['fact-1', 'fact-2']}
- `dev-38` (multi_section): {'keyword': ['fact-1', 'fact-2']}
- `dev-39` (multi_section): {'keyword': ['fact-1', 'fact-2'], 'vector': ['fact-1'], 'hybrid': ['fact-1']}
- `dev-40` (multi_section): {'keyword': ['fact-1', 'fact-2'], 'vector': ['fact-2'], 'hybrid': ['fact-2']}
- `dev-41` (multi_section): {'keyword': ['fact-1', 'fact-2'], 'vector': ['fact-1', 'fact-2'], 'hybrid': ['fact-1', 'fact-2']}
- `dev-42` (multi_section): {'keyword': ['fact-1', 'fact-2'], 'vector': ['fact-1', 'fact-2'], 'hybrid': ['fact-1', 'fact-2']}
- `dev-43` (multi_section): {'keyword': ['fact-1', 'fact-2']}
- `dev-44` (multi_section): {'keyword': ['fact-1', 'fact-2'], 'vector': ['fact-1'], 'hybrid': ['fact-1']}
- `dev-45` (multi_section): {'keyword': ['fact-1', 'fact-2'], 'vector': ['fact-1', 'fact-2'], 'hybrid': ['fact-1', 'fact-2']}
- `dev-46` (multi_section): {'keyword': ['fact-1', 'fact-2']}
- `dev-47` (multi_section): {'keyword': ['fact-1', 'fact-2'], 'vector': ['fact-1', 'fact-2'], 'hybrid': ['fact-1', 'fact-2']}

## Runtime and provenance

- Model load: 2.9119011249858886 seconds; first question: 0.024 seconds; remaining mean: 0.009 seconds.
- Execution: 0.531 seconds; throughput: 112.99 questions/second.
- Build reuse: {'snapshot_id': '279777ae-c949-4cae-8403-2224b314903f', 'reused': False, 'state': 'ready', 'document_count': 14, 'chunk_count': 637, 'encoded_inputs': 266, 'reused_inputs': 346}.
- Snapshot profile hash: `983b1abf73f3dfd87b9c9902d2acf1a24c92c84683c56208406a47ba9be57487`; retrieval profile hash: `c122daa937ae2744fc3d16055ff1371be114fe738e2ae4ee5947a08de3a45443`; corpus hash: `47a4caa9dcbe4bd3d7268fecccdaad9a50424c9facbe643aac7de98a26fe70be`.
- Full ranks, scores, source spans, missing groups, code and migration hashes are in the JSON report.
