# Decisions

## Dataset
Chosen repo: TODO

Reason:
TODO

## Label mapping
| GitHub label | Project label |
|---|---|
| bug | bug |
| feature | feature |
| docs | docs |
| question | question |

## Split strategy
Time-based stratified split:
- Train: older issues
- Val: middle/recent issues
- Test: strictly newer than train

Reason:
The project requires test to be more recent than train.

## Classical model
TODO

## Fine-tuned transformer
TODO

## LLM baseline
TODO

## Deployment model choice
TODO after metrics.

## Embedding model comparison
TODO

## Chunking strategy
TODO

## Hybrid retrieval weighting
TODO

## Reranker
TODO

## Query transformation
TODO

## Memory choice
Chosen long-term memory type: episodic

Reason:
Episodic memory is easiest to demonstrate across conversations and fits maintainer preferences/actions.

## Redis TTL
Short-term memory TTL: 24 hours

Reason:
Preserves active triage context across breaks without keeping temporary debugging context forever.

## Tracing backend
TODO

## Widget bundle target
TODO
