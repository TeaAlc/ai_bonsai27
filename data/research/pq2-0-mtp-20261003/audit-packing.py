import sys
sys.dont_write_bytecode = True
import collections
import hashlib
import json
from pathlib import Path
import struct

FORMATS = {0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}

def inspect(path):
    with path.open('rb') as stream:
        def number(fmt):
            return struct.unpack('<'+fmt, stream.read(struct.calcsize('<'+fmt)))[0]
        def string(keep=True):
            size = number('Q')
            if keep:
                return stream.read(size).decode('utf-8')
            stream.seek(size,1)
        def value(kind,keep=False):
            if kind in FORMATS:
                result=number(FORMATS[kind])
                return result if keep else None
            if kind==8:
                return string(keep)
            if kind==9:
                element, count=number('I'), number('Q')
                if not keep and element in FORMATS:
                    stream.seek(count*struct.calcsize('<'+FORMATS[element]),1)
                    return
                result=[] if keep else None
                for _ in range(count):
                    item=value(element,keep)
                    if keep: result.append(item)
                return result
            raise ValueError('Unknown metadata type '+str(kind))
        assert stream.read(4)==b'GGUF'
        version,tensor_count,metadata_count=number('I'),number('Q'),number('Q')
        assert version==3
        metadata={}
        tokenizer_hashes={}
        alignment=32
        for _ in range(metadata_count):
            key=string();kind=number('I');start=stream.tell()
            item=value(kind,key in ('general.architecture','general.alignment','qwen35.block_count','qwen35.nextn_predict_layers','general.name'))
            end=stream.tell()
            if item is not None: metadata[key]=item
            if key.startswith(('tokenizer.', 'prism.hadamard.', 'qwen35.')):
                stream.seek(start)
                tokenizer_hashes[key]=hashlib.sha256(stream.read(end-start)).hexdigest()
            if key=='general.alignment': alignment=item
        tensors=[]
        for _ in range(tensor_count):
            name=string();dimensions=number('I');shape=[number('Q') for _ in range(dimensions)]
            kind,offset=number('I'),number('Q')
            tensors.append({'name':name,'shape':shape,'type_id':kind,'offset':offset})
        data_start=(stream.tell()+alignment-1)//alignment*alignment
        ordered=sorted(tensors,key=lambda tensor:tensor['offset'])
        for i,tensor in enumerate(ordered):
            tensor['span_bytes']=(ordered[i+1]['offset']-tensor['offset']) if i+1<len(ordered) else path.stat().st_size-data_start-tensor['offset']
        head=[]
        for tensor in ordered:
            if tensor['name'].startswith('blk.64.'):
                stream.seek(data_start+tensor['offset'])
                remaining=tensor['span_bytes'];checksum=hashlib.sha256()
                while remaining:
                    block=stream.read(min(remaining,1024*1024));assert block
                    remaining-=len(block);checksum.update(block)
                head.append({key:tensor[key] for key in ('name','shape','type_id','span_bytes')} | {'stored_span_sha256':checksum.hexdigest()})
        return {'file':path.name,'bytes':path.stat().st_size,'metadata':metadata,
                'data_start':data_start,'tensors':tensors,'tensor_count':tensor_count,'tensor_type_counts':dict(collections.Counter(t['type_id'] for t in tensors)),
                'runtime_metadata_sha256':tokenizer_hashes,'mtp_head':head}



def main():
    import argparse
    import math
    import subprocess
    import tempfile
    parser = argparse.ArgumentParser(description='Compare pinned PQ2/PTQ codes, scales and remaining tensor bytes.')
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = [args.model_dir / 'Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf',
             args.model_dir / 'Bonsai-2-27B-PQ2_0-MTP.gguf']
    models = [inspect(path) for path in paths]
    expected = ['1e33c571a5ce7a9a3e42474d66192923d5a6d77da7fb3a22986dc809522b5685',
                '78df4279d40ebebdccfd2dae0e9d4847afee52e94f48f3542ae9437220dbd847']
    hashes = []
    for path, pin in zip(paths, expected):
        with path.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        assert checksum == pin, 'Model hash does not match the pinned artifact'
        hashes.append(checksum)
    tables = [{t['name']: t for t in model['tensors']} for model in models]
    assert tables[0].keys() == tables[1].keys()
    manifest = []
    other_tensors = []
    with paths[0].open('rb') as ptq, paths[1].open('rb') as pq2:
        for name, tensor in tables[1].items():
            other = tables[0][name]
            assert other['shape'] == tensor['shape']
            offsets = [models[0]['data_start'] + other['offset'],
                       models[1]['data_start'] + tensor['offset']]
            if tensor['type_id'] == 142:
                assert other['type_id'] == 143
                blocks = math.prod(tensor['shape']) // 128
                manifest.append(f'{name} {offsets[0]} {offsets[1]} {blocks}')
                continue
            assert tensor['type_id'] == other['type_id']
            assert tensor['span_bytes'] == other['span_bytes']
            ptq.seek(offsets[0]); pq2.seek(offsets[1])
            remaining = tensor['span_bytes']
            checksum = hashlib.sha256()
            while remaining:
                size = min(remaining, 1024 * 1024)
                left, right = ptq.read(size), pq2.read(size)
                assert len(left) == size and left == right, name
                checksum.update(left); remaining -= size
            other_tensors.append({'name': name, 'stored_span_sha256': checksum.hexdigest()})
    assert models[0]['runtime_metadata_sha256'] == models[1]['runtime_metadata_sha256']
    source = Path(__file__).with_suffix('.cpp')
    scratch = Path('/tmp/bonsai27'); scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='packing-audit.', dir=scratch) as directory:
        temporary = Path(directory)
        layout = temporary / 'manifest.txt'
        layout.write_text('\n'.join(manifest) + '\n')
        executable = temporary / 'compare'
        subprocess.run(['g++', '-O3', '-std=c++17', '-pthread', str(source), '-o', str(executable)], check=True)
        full = json.loads(subprocess.check_output([str(executable), *map(str, paths), str(layout)], text=True))
    result = {'scope': 'All 402 main tensors: exact decoded integer codes and FP16 scale bits; all 464 other tensor stored spans',
              'model_files': [p.name for p in paths], 'model_sha256': hashes,
              'gguf_type_ids': [143, 142], 'full_comparison': full,
              'runtime_metadata_identical': True,
              'runtime_metadata_sha256': models[0]['runtime_metadata_sha256'],
              'other_tensor_spans_identical': True, 'other_tensors': other_tensors,
              'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'cpp_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'codec_reference_revision': 'f13265492743209a0fbedc2a2781af3f5f0eab13',
              'limitations': ['Stored weight equality does not guarantee equal floating-point kernel results or continuations.',
                              'The exact cause of the conflicting upstream code-count reports is not established.']}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(full))


if __name__ == '__main__':
    main()
