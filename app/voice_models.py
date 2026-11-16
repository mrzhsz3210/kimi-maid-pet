"""External, local models used by the optional voice input feature."""
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import time
import http.client
import urllib.error
import urllib.request

from platform_support import user_data

KWS_NAME = 'sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20'
ASR_NAME = 'sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17'
RELEASE = 'https://github.com/k2-fsa/sherpa-onnx/releases/download'
ARCHIVES = {
    KWS_NAME: RELEASE + '/kws-models/' + KWS_NAME + '.tar.bz2',
}
ASR_SOURCE = 'https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main/'
ASR_FILES = ('model.int8.onnx', 'tokens.txt')
VAD_URL = RELEASE + '/asr-models/silero_vad.onnx'


def model_root():
    return user_data() / 'voice-models'


def model_paths(root=None):
    root = Path(root) if root else model_root()
    kws = root / KWS_NAME
    asr = root / ASR_NAME
    return {
        'encoder': kws / 'encoder-epoch-13-avg-2-chunk-16-left-64.int8.onnx',
        'decoder': kws / 'decoder-epoch-13-avg-2-chunk-16-left-64.onnx',
        'joiner': kws / 'joiner-epoch-13-avg-2-chunk-16-left-64.int8.onnx',
        'kws_tokens': kws / 'tokens.txt',
        'lexicon': kws / 'en.phone',
        'asr_model': asr / 'model.int8.onnx',
        'asr_tokens': asr / 'tokens.txt',
        'vad': root / 'silero_vad.onnx',
    }


def missing_models(root=None):
    return [path for path in model_paths(root).values() if not path.is_file()]


def download(url, target, progress):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + '.part')
    for attempt in range(5):
        received = partial.stat().st_size if partial.exists() else 0
        headers = {'User-Agent': 'KimiMaidPet/voice-setup'}
        if received:
            headers['Range'] = f'bytes={received}-'
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                resumed = received and response.status == 206
                if not resumed:
                    received = 0
                total = int(response.headers.get('Content-Length') or 0) + received
                with partial.open('ab' if resumed else 'wb') as output:
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                        received += len(block)
                        if total:
                            progress(f'{target.name}：{received / 1048576:.0f} / {total / 1048576:.0f} MB')
                        else:
                            progress(f'{target.name}：已下载 {received / 1048576:.0f} MB')
            if total and received != total:
                raise OSError(f'下载长度不完整：{received} / {total}')
            os.replace(partial, target)
            return
        except (OSError, urllib.error.URLError, http.client.HTTPException) as error:
            if attempt == 4:
                raise RuntimeError(f'下载失败，已保留断点可稍后继续：{target.name}：{error}') from error
            progress(f'{target.name} 连接中断，稍后从断点重试（{attempt + 1}/4）')
            time.sleep(2 ** attempt)


def install_archive(name, root, progress):
    target = root / name
    archive = root / (name + '.tar.bz2')
    download(ARCHIVES[name], archive, progress)
    with tempfile.TemporaryDirectory(dir=root, prefix='.extract-') as folder:
        with tarfile.open(archive, 'r:bz2') as source:
            source.extractall(folder, filter='data')
        extracted = Path(folder) / name
        if not extracted.is_dir():
            raise RuntimeError('模型压缩包内容不完整：' + name)
        if target.exists():
            shutil.rmtree(target)
        os.replace(extracted, target)
    archive.unlink(missing_ok=True)


def install_models(root=None, progress=print):
    root = Path(root) if root else model_root()
    root.mkdir(parents=True, exist_ok=True)
    for name in ARCHIVES:
        paths = model_paths(root)
        required = ('encoder', 'decoder', 'joiner', 'kws_tokens', 'lexicon')
        if all(paths[key].is_file() for key in required):
            progress('已存在：' + name)
            continue
        progress('正在安装：' + name)
        install_archive(name, root, progress)
    paths = model_paths(root)
    for filename in ASR_FILES:
        target = root / ASR_NAME / filename
        if not target.is_file():
            progress('正在安装：SenseVoice ' + filename)
            download(ASR_SOURCE + filename, target, progress)
    if not paths['vad'].is_file():
        download(VAD_URL, paths['vad'], progress)
    missing = missing_models(root)
    if missing:
        raise RuntimeError('语音模型安装不完整：' + '、'.join(path.name for path in missing))
    progress('语音模型已就绪：' + str(root))
    return root
