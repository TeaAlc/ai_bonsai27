# Historical performance comparisons

These are retained October 2 observations. Current defaults and acceptance are
in the [README](../../README.md#performance-and-validation).

## Historical Ada comparison — thinking disabled

On the RTX 4070 Ti SUPER, three fresh-container runs per mode with the optimized
Ada backend produced the following means. All nine benchmark conversations were
identical; each used about 16k cumulative API usage and a 16,384-token window.

| Mode | Mean decode tokens/s | Mean wall time ± sample SD |
| --- | ---: | ---: |
| MTP=1 | 89.13 | 16.096 ± 0.047 s |
| **MTP=2 (default)** | **87.32** | **15.852 ± 0.048 s** |
| No speculation | 73.49 | 17.385 ± 0.015 s |

MTP=2 has the shortest total time on this benchmark. The optional backend gained
about 4% decode throughput over the original backend in the earlier comparison.
On that Ada host, tested DFlash/DFlash2 drafts, including the official Qwen3.8
DFlash2 checkpoint in BF16 and Q8_0, were slower on this conversation. Paired quality probes against the original
image found no degradation. These are workload-specific results, not universal
speed or quality guarantees. Measurements, confidence intervals, model/build
identities, and research sources are in [RECHERCHE.md](../../RECHERCHE.md).

## Historical Blackwell backend comparison — thinking disabled

On the RTX 5070 Ti Laptop (12 GB, WSL2), the October 2 Blackwell comparison
was repeated after the user stopped a GPU-intensive background application.
The initial timings are retained as contaminated evidence, excluded from this
comparison. Baseline and native builds were alternated, each with three fresh
containers, 20 messages, 16k context, q8_0 caches, Flash Attention, and CPU vision:

| Blackwell mode | Runs | Mean decode tokens/s | Mean conversation wall time |
| --- | ---: | ---: | ---: |
| Published Blackwell backend, MTP=2 | 3 | 39.91 | 34.708 s |
| **Native SM120 Prism backend, MTP=2** | **3** | **43.34** | **32.934 s** |
| Native + Qwen3.5 DFlash, draft depth 3 | 3 | 34.99 | 39.650 s |
| Native + Bonsai DFlash2, draft depth 3 | 3 | 31.41 | 41.172 s |
| Native + Bonsai DFlash2, draft depth 7 | 3 | 30.34 | 43.109 s |

The clean native MTP comparison measured **8.6% higher decode throughput** and
5.1% less conversation wall time. MTP runs used 15,949 cumulative API tokens,
including 823 output tokens, with 87.37% prompt-cache hits. DFlash2 depth 7 used
15,951 tokens including 841 output tokens; cache hits were 87.50%. Its output
can differ at near-tied greedy choices under batched verification. These runs
do not measure throughput with a filled 16k context.

Both DFlash modes completed all three clean conversations, passed nine quality
probes, and passed the three restricted coding tasks (23 assertions). Bonsai
DFlash2 reached 104.69–119.80 tokens/s on those individual coding tasks and
100.83–105.99 tokens/s on two individual thinking probes. It was nevertheless
slower on the library conversation, with only 19.65% draft-token acceptance.
Native MTP reached 63.07–70.11 tokens/s on the separate clean coding probes.
The container default therefore remains MTP=2; DFlash is a workload-specific
experimental option rather than a general speed improvement.

Earlier draft loading failures exposed an upstream device-split bug when CUDA
reported zero free memory; the container now fixes the split to CUDA0. Slow
prefill under the competing GPU load also exceeded test deadlines. The clean
DFlash/DFlash2 repetitions succeeded with CUDA PDL enabled; the known older
Blackwell PDL race is already fixed in the pinned source. Full details and
limits are in [Blackwell research](../../RECHERCHE.md#native-blackwell-and-dflash-experiments-october-2-2026).

## Historical Blackwell depth comparison — thinking disabled

A separate October 2 comparison used the same native SM120 image for MTP=1,
MTP=2, and MTP=4, with three fresh containers per depth and rotated orders
1/2/4, 2/4/1, and 4/1/2. All other settings remained unchanged: 16k context,
main/draft q8_0 caches, Flash Attention, CUDA0 language model, CPU vision,
and the 20-message conversation with thinking disabled.

| Maximum MTP draft depth | Mean decode tokens/s | Mean conversation wall time |
| --- | ---: | ---: |
| Disabled (`--spec-type none`) | 42.43 | 31.935 s |
| 1 | **48.36** | **30.919 s** |
| 2 | 43.49 | 32.640 s |
| 4 | 31.98 | 36.409 s |

Three additional fresh-container runs with speculation disabled measured
42.43 tokens/s. MTP=1 was **14.0% faster in decode** than disabled MTP and
**11.2% faster** than the fresh MTP=2 control; MTP=4 was
**26.5% slower**. Disabled MTP and MTP=1/2 produced 823 output tokens per
conversation, while
MTP=4 produced 743 and different answers. These are approximately 16k
*cumulative* API tokens, not a filled 16k context. Each depth passed nine
quality probes, including three thinking probes. This small check does not
establish broad quality equivalence, and the project default remains MTP=2.
MTP=2 improved decode by only 2.5% over disabled MTP and took slightly longer
over the complete conversation; a general improvement is not established.
The disabled runs followed the rotated series rather than being interleaved.
Actual process arguments and nonzero API draft/accepted-draft counters confirm
that each requested depth was active; disabled runs had no draft counters.
See the
[measurement record](../../data/research/blackwell-mtp-20261002/measurements.json)
for repetitions, cache hits, acceptance rates, and evidence checksums.

## Earlier 32k validation and reasoning comparisons

**Current policy:** MTP=2 on every supported architecture; benchmarks enable
thinking at `medium`. On Blackwell, the recorded reasoning comparison favored
MTP=2 over MTP=1 by 9.3% in decode speed, and over DFlash2 depth 4 by 8.6%
(60.98 versus 55.78 and 56.13 tokens/s respectively). These are single-run,
workload-specific observations, not guaranteed throughput. The Ada figures
below used thinking disabled and have not been repeated with the new policy.

### Earlier single-run 32,000-token validation — measured on Blackwell

The rebuilt image completed one fresh-container run on the RTX 5070 Ti Laptop
GPU (12 GB, WSL2), with MTP=2, thinking enabled at `medium`, q8_0 main/draft
caches, Flash Attention, and CPU BF16 vision:

| Metric | Recorded value |
| --- | ---: |
| Context allocation | 32,000 tokens |
| Decode speed | 62.77 tokens/s |
| Ten-exchange conversation | 231.195 s |
| Mean / peak total VRAM | 9,504.85 / **9,516 MiB (9.29 GiB peak)** |
| Thinking tokens | **12,800**, server-retokenized estimate |
| Completion / cumulative API usage | 13,752 / 20,352 tokens |
| Prompt-cache hit rate | 80.45% |
| Subsequent quality probes | 9/9 passed |

The actual API and process arguments confirm the 32,000-token setting. This
conversation did not fill the context window; cumulative usage counts repeated
history. The 16k cumulative usage target was exceeded and reported explicitly.
Thinking tokens are already part of completion usage. VRAM figures include
other processes and were sampled once per second. This is one run, not a mean
or proof that every 32k prompt fits. See the
[32k measurement record](../../data/research/blackwell-32000-20261002/validation.json).

Historical Ada/Blackwell depth, backend and DFlash comparisons are retained
in [historical performance](../../docs/history/performance-20261002.md).


### Recorded reasoning on/off comparison — 16k context

Two additional single runs enabled actual thinking with reasoning effort
`medium`, one each for MTP=1 and MTP=2. The disabled comparison below reuses
block 1 of the previous series; these are **individual runs, not averages**.
All use the same native SM120 image, 16k context, q8_0, and Flash Attention.

| MTP depth | Reasoning | Decode tokens/s | Conversation time | Output tokens, including thinking | Peak GPU memory |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Off, recorded earlier | 49.69 | 30.678 s | 823 | 8,773 MiB |
| 2 | Off, recorded earlier | 42.42 | 32.827 s | 823 | 9,001 MiB |
| 1 | On, `medium` | 55.78 | 259.639 s | 13,752 | 8,688 MiB |
| **2** | **On, `medium`** | **60.98** | **237.738 s** | **13,752** | **8,938 MiB** |

With thinking enabled, MTP=2 decoded **9.3% faster** than MTP=1 and finished
8.4% sooner. Both produced identical reasoning and final-answer text across
all ten exchanges. This reverses the non-thinking result for this workload;
it does not establish a universal best depth.

Thinking used a 4,096-token completion cap instead of 128 to avoid cutting off
reasoning. All twenty new responses ended normally and contained nonempty
`reasoning_content`. Cumulative API usage reached **20,352 tokens** in each
thinking run, exceeding the approximate 16k usage target. The largest actual
input plus output was only **3,774 tokens**, so a 32k context was unnecessary.
Decode rates include thinking tokens; the longer conversation times reflect
much larger output volumes, not necessarily slower decoding.

GPU memory was sampled once per second during each benchmark on a device with
12,227 MiB total memory. Peaks include desktop and other processes; they are
not exact container allocations. Idle memory was 1,350 MiB before the recorded
disabled runs and 1,271–1,276 MiB before the thinking runs. Similar peaks do
not demonstrate that thinking saves VRAM. See the
[reasoning measurement record](../../data/research/blackwell-mtp-20261002/reasoning-comparison.json)
for mean/peak memory, cache hits, draft acceptance, and evidence checksums.

A further single run used **Bonsai DFlash2 r3 Q4_K_M, draft depth 4**, with
thinking enabled at `medium` and CUDA PDL enabled. It reached **56.13 decode
tokens/s**, versus MTP=2's 60.98: **8.0% slower**, with peak GPU memory of
**10,470 MiB**, **1,532 MiB more** than MTP=2. All ten responses finished
normally with reasoning content. Draft acceptance was 75.09% and prompt-cache
hits 79.69%. It generated 11,782 output tokens with different answers and
18,098 cumulative API tokens; its 221.643-second wall time therefore reflects
less output, not faster decoding. For this measured reasoning conversation,
MTP=2 was faster and used less VRAM. This is one run, not a general DFlash2
quality or performance conclusion. See the
[DFlash2 reasoning record](../../data/research/blackwell-mtp-20261002/dflash2-reasoning.json).
