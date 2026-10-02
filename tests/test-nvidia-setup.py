#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MOCK = '''#!/usr/bin/env python3
import sys, os, subprocess
from pathlib import Path
name=Path(sys.argv[0]).name; args=sys.argv[1:]
with open(os.environ['CALLS'],'a') as f: f.write(name+' '+ ' '.join(args)+'\\n')
if name=='sudo':
 if args==['-v']: sys.exit(0)
 sys.exit(subprocess.run(args).returncode)
if name=='nvidia-smi':
 if os.environ.get('DRIVER_FAIL')=='1': sys.exit(1)
 print('GPU fixture: driver=595 memory=16376 compute=8.9')
elif name=='lspci': print('01:00.0 VGA NVIDIA fixture')
elif name=='ubuntu-drivers': print('driver : nvidia-driver-595-open - distro non-free recommended')
elif name=='curl': Path(args[args.index('--output')+1]).write_text('deb https://nvidia.example/stable /\\n')
elif name=='gpg': Path(args[args.index('--output')+1]).write_text('fixture-key')
elif name=='nvidia-ctk':
 if args==['--version']: print('NVIDIA Container Toolkit CLI version fixture')
 elif args[:2]==['cdi','list']:
  if os.environ.get('CDI_MISSING')=='1': print('No devices')
  else: print('nvidia.com/gpu=all')
 elif args[:2]==['cdi','generate']:
  if os.environ.get('GEN_FAIL')=='1': sys.exit(1)
  dest=next(a.split('=',1)[1] for a in args if a.startswith('--output='))
  Path(dest).write_text('cdiVersion: 0.5.0\\nkind: nvidia.com/gpu\\n')
elif name=='podman':
 if args==['--version']: print('podman version '+os.environ.get('PODMAN_VERSION','6.1.2'))
 elif args[:2]==['image','exists']: sys.exit(int(os.environ.get('IMAGE_STATUS','0')))
 elif args[0]=='run':
  if os.environ.get('CUDA_FAIL')=='1': sys.exit(1)
  print('8.9' if '/opt/bonsai/cuda-compute-capability' in args else 'Dependencies passed')
 elif args[0]=='info': print('rootless=true runtime=crun cgroup=v2')
 elif args[:2]==['image','inspect']: print('image=fixture source=fixture version=1.5.0')
elif name in ['apt-get','systemctl','journalctl','mokutil','modinfo','dpkg-query']: print(name+' fixture')
'''

def run_case(name, args, expected, settings=None, inspect=None, distribution='linuxmint', wsl=False):
    with tempfile.TemporaryDirectory(prefix='nvidia-setup-', dir='/tmp/bonsai27') as directory:
        base=Path(directory); (base/'data').mkdir(); (base/'bin').mkdir()
        shutil.copy(ROOT/'data/logging.sh',base/'data/logging.sh')
        source=(ROOT/'install_nvidia.sh').read_text()
        for path in ['/etc/cdi','/var/run/cdi','/etc/nvidia-container-toolkit','/usr/share/keyrings','/etc/apt/sources.list.d']:
            source=source.replace(path,str(base/path.lstrip('/')))
            (base/path.lstrip('/')).mkdir(parents=True,exist_ok=True)
        os_release=base/'os-release';os_release.write_text(f'ID={distribution}\nPRETTY_NAME="Fixture Linux"\n')
        source=source.replace('/etc/os-release',str(os_release))
        kernel_release=base/'kernel-release'; kernel_release.write_text('fixture-kernel\n')
        source=source.replace('/proc/sys/kernel/osrelease',str(kernel_release))
        dxg=base/'dxg'
        if wsl: dxg.touch()
        source=source.replace('/dev/dxg',str(dxg))
        script=base/'install_nvidia.sh';script.write_text(source)
        for tool in ['sudo','nvidia-smi','lspci','ubuntu-drivers','curl','gpg','nvidia-ctk','podman','apt-get','systemctl','journalctl','mokutil','modinfo','dpkg-query']:
            file=base/'bin'/tool;file.write_text(MOCK);file.chmod(0o755)
        calls=base/'calls';log=base/'diagnostic.log'
        env=dict(os.environ,PATH=str(base/'bin')+':'+os.environ['PATH'],CALLS=str(calls),TMPDIR=str(base),PYTHONDONTWRITEBYTECODE='1',**(settings or {}))
        result=subprocess.run(['bash',str(script),*args,'--log',str(log)],env=env,text=True,capture_output=True,timeout=30)
        assert result.returncode==expected,(name,result.returncode,result.stdout,result.stderr)
        recorded=calls.read_text() if calls.exists() else ''; saved=log.read_text()
        if not wsl and distribution in ['linuxmint','ubuntu','debian']:
            assert 'Fixture Linux' in saved and 'kernel=' in saved
        if inspect: inspect(recorded,saved,base)
        print('Passed:',name)

def readonly(calls,log,base):
    assert 'apt-get' not in calls and 'sudo ' not in calls and 'cdi generate' not in calls
    assert '--network none' in calls and '--pull=never' in calls
    assert 'Actual container CUDA' in log

def reboot(calls,log,base):
    assert 'apt-get install nvidia-driver-595-open' in calls
    assert 'cdi generate' not in calls and 'Reboot' in log

def repair(calls,log,base):
    assert 'apt-get' not in calls and 'curl ' not in calls
    assert '--feature-flag no-additional-gids-for-device-nodes' in calls
    assert 'no-additional-gids-for-device-nodes' in (base/'etc/nvidia-container-toolkit/nvidia-cdi-refresh.env').read_text()

def install(calls,log,base):
    assert 'apt-get install nvidia-driver' not in calls
    assert 'apt-get install nvidia-container-toolkit-base' in calls
    assert not any('nvidia-cuda-toolkit' in line for line in calls.splitlines() if line.startswith('apt-get install '))
    assert 'signed-by=' in (base/'etc/apt/sources.list.d/nvidia-container-toolkit.list').read_text()

def unverified(calls, log, base):
    assert 'container CUDA remains unverified' in log


def generation_failed(calls, log, base):
    assert not (base/'etc/cdi/nvidia.yaml').exists()


def debian_driver(calls, log, base):
    assert 'apt-get install nvidia-driver\n' in calls


Path('/tmp/bonsai27').mkdir(exist_ok=True)
run_case('read-only real probe path',['--check','--verify-container'],0,inspect=readonly)
run_case('missing driver diagnosed',['--check'],1,{'DRIVER_FAIL':'1'})
run_case('driver install requires reboot',[],3,{'DRIVER_FAIL':'1'},reboot)
run_case('working driver preserved during installation',[],0,inspect=install)
run_case('Podman 4 repair avoids package downloads',['--repair-cdi'],0,{'PODMAN_VERSION':'4.9.3'},repair)
run_case('missing CDI fails check',['--check'],1,{'CDI_MISSING':'1'})
run_case('container CUDA failure propagates',['--check','--verify-container'],1,{'CUDA_FAIL':'1'})
run_case('missing required image fails',['--check','--verify-container'],1,{'IMAGE_STATUS':'1'})
run_case('engine failure distinguished from missing image',['--check'],1,{'IMAGE_STATUS':'125'})
run_case('no image yields explicit unverified warning',['--check'],0,{'IMAGE_STATUS':'1'},unverified)
run_case('failed generation does not publish CDI',['--repair-cdi'],1,{'GEN_FAIL':'1'},generation_failed)
run_case('WSL rejected before installation',[],1,wsl=True)
run_case('unsupported distribution rejected',[],1,distribution='fedora')
run_case('Debian driver package selected',[],3,{'DRIVER_FAIL':'1'},debian_driver,distribution='debian')
print('All NVIDIA setup fixtures passed; no host packages or configuration changed.')
