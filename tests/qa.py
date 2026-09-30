#!/usr/bin/env -S python3 -B

# Keep imports from writing bytecode caches, including when run via python3.
import sys
sys.dont_write_bytecode = True

import json,re
from pathlib import Path
r=Path(__file__).resolve().parent.parent / 'results'; log=(r/'server.log').read_text()
checks={
 'all_layers_cuda': 'offloaded 66/66 layers to GPU' in log,
 'all_model_buffers_cuda': bool(re.search(r'CUDA0 model buffer size',log)) and not re.search(r'(?:CPU|CPU_Mapped|CUDA_Host)\s+model buffer size',log),
 'flash_attention_main_and_mtp': log.count('flash_attn            = enabled')>=2,
 'q8_main_and_mtp': len(re.findall(r'K \(q8_0\).*V \(q8_0\)',log))>=2,
 'mtp_n2': 'n_max=2,' in log and 'speculative decoding enabled: draft-mtp' in log,
 'gpu_draft': 'devices=[CUDA0]' in log,
 'no_cuda_init_error': 'failed to initialize CUDA' not in log,
 'context_16k': 'n_ctx_slot = 16384' in log,
 'context_env_8k': json.loads((r/'context-env-8192.json').read_text())['default_generation_settings']['n_ctx']==8192,
 'api_long_context': json.loads((r/'api-test-summary.json').read_text())['long_context_pass'],
 'vision_cpu_backend': 'CLIP using CPU backend' in log,
 'vision_bf16_projector': "loaded multimodal model, '/models/Ternary-Bonsai-2-27B-mmproj-BF16.gguf'" in log,
 'vision_api_pass': all(x['passed'] for x in json.loads((r/'vision/summary.json').read_text())),
 'coding_all_pass': all(x['passed'] for x in json.loads((r/'coding/summary.json').read_text())),
}
(r/'qa-summary.json').write_text(json.dumps(checks,indent=2))
print(json.dumps(checks,indent=2))
assert all(checks.values()), 'Quality assurance failed'
