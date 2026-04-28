# Layout Scaling Notes

## Purpose

This document records the current CPU scaling observations for the
PP-DocLayoutV3 layout service and sketches a future worker-pool strategy.

No layout worker pool is implemented yet. The current production path still
uses one `LAYOUT_SERVICE_URL` selected by environment configuration.

## Current Runtime

The current real layout backend is:

```text
services/layout_ppdoclayoutv3_cpu/
```

It runs PP-DocLayoutV3 through PaddleOCR/Paddle on CPU. The installed PaddleOCR
runtime already enables internal CPU parallelism by default:

```text
DEFAULT_ENABLE_MKLDNN = True
DEFAULT_CPU_THREADS = 10
DEFAULT_MKLDNN_CACHE_CAPACITY = 10
```

This means one unrestricted layout worker is not single-threaded. It already
tries to use roughly 8-10 CPU threads inside one inference process.

## Local Measurements

Observed local measurements:

```text
1 unrestricted layout worker:
  ~5.3 seconds per page

3 separate layout containers limited to 2 CPU each:
  ~18.8 seconds per page on average
```

The multi-container test was slower because each container was constrained too
tightly. Paddle inference inside one worker wants approximately 8-10 threads,
but each worker only received 2 CPU. That starved the internal MKLDNN/Paddle
thread pool instead of increasing useful throughput.

Memory measurement for one warmed layout worker:

```text
observed peak RSS: ~668 MiB
planning estimate: ~1.0 GiB with 1.5x safety margin
conservative container budget: ~1.2 GiB
```

## Scaling Implication

Adding many CPU cores to a single worker should not be expected to make one page
linearly faster. Once a single inference has enough threads for Paddle's
internal parallelism, additional cores mostly help by allowing more pages to be
processed concurrently.

The useful scaling direction for large machines is therefore throughput:

```text
many pages/PDFs in parallel
not one page on hundreds of cores
```

For example, a 400-core machine should probably not run one layout worker with
400 CPU. A better future direction is a pool of workers where each worker has
enough CPU for one efficient Paddle inference process.

## Future Auto Worker Strategy

A future launcher or orchestrator-side pool could use this heuristic:

```text
cpu_threads_per_worker = 10
memory_gb_per_worker = 1.2

cpu_limited_workers = floor(usable_cpu_cores / cpu_threads_per_worker)
memory_limited_workers = floor(available_memory_gb / memory_gb_per_worker)

worker_count = max(1, min(cpu_limited_workers, memory_limited_workers, max_workers))
```

If memory cannot be measured reliably, the first implementation can use CPU as
the primary limit and allow a manual override.

Example CPU-only sizing:

```text
8 cores   -> 1 worker
10 cores  -> 1 worker
15 cores  -> 1 worker
20 cores  -> 2 workers
32 cores  -> 3 workers
64 cores  -> 6 workers
400 cores -> about 40 workers, if memory and I/O allow it
```

On shared desktop machines, the launcher should reserve some CPU for the OS and
other services. A conservative rule:

```text
usable_cpu_cores = total_cpu_cores - reserved_cpu_cores

reserved_cpu_cores:
  0-1 on small machines
  2 on machines with 12+ cores
```

## Proposed Configuration

Future configuration should support both auto mode and manual override:

```text
LAYOUT_WORKER_MODE=auto
LAYOUT_WORKER_COUNT=0
LAYOUT_CPU_THREADS_PER_WORKER=10
LAYOUT_MEMORY_GB_PER_WORKER=1.2
LAYOUT_RESERVED_CPU_CORES=auto
LAYOUT_MAX_WORKERS=0
```

Suggested behavior:

```text
LAYOUT_WORKER_COUNT > 0:
  use the explicit worker count

LAYOUT_WORKER_COUNT = 0 and LAYOUT_WORKER_MODE=auto:
  derive worker count from CPU and memory

LAYOUT_MAX_WORKERS > 0:
  cap the derived worker count
```

## Orchestrator Direction

The clean architectural split is:

```text
launcher decides how many layout workers exist
orchestrator distributes pages across a list of layout service URLs
```

The orchestrator should not need to know Docker-specific details. A future
multi-worker implementation can introduce:

```text
LAYOUT_SERVICE_URLS=http://layout_1:8000,http://layout_2:8000,http://layout_3:8000
```

Then the layout stage can distribute page requests across those URLs with a
bounded concurrency limit. The existing single-worker `LAYOUT_SERVICE_URL`
should remain supported for ordinary local machines and simple deployments.

## What Not To Do

Avoid splitting a normal desktop CPU into many underpowered layout containers.
For example:

```text
3 workers x 2 CPU each
```

This is worse than one unrestricted or properly sized worker because it starves
the internal Paddle thread pool.

## Open Questions

- Whether PP-DocLayoutV3 can benefit from batch page inference through PaddleOCR
  APIs or a dedicated service endpoint.
- Whether a GPU PP-DocLayoutV3 container gives better latency per page than CPU
  MKLDNN on target hardware.
- Whether Docker CPU limits should be set explicitly per worker or left
  unrestricted while controlling worker count.
- How much I/O contention appears when many workers read rendered page PNGs and
  write overlays/crops concurrently.
- Whether OCR, vision, and layout should share a global resource scheduler so
  one stage does not starve the rest of the pipeline.
