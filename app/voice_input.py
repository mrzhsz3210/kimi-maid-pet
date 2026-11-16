"""Local wake-word, voice-activity and speech-to-text input for the pet."""
import os
from pathlib import Path
import re
import threading
import time

from PySide6.QtCore import QObject, QThread, Signal

from voice_models import missing_models, model_paths, model_root

SAMPLE_RATE = 16000
DEFAULT_WAKE_WORDS = '没药，Kimi，Kimi娘'
CANCEL_PHRASES = {'没事了', '没事', '退下吧', '退下', '取消', '不用了', '算了'}
PRONUNCIATIONS = {
    '没药': 'm ò y ào',
    'kimi': 'K IH1 M IY0',
    'kimi娘': 'K IH1 M IY0 n iáng',
}


def parse_wake_words(value):
    if isinstance(value, str):
        values = re.split(r'[,，;；\n]+', value)
    else:
        values = value
    result = []
    for item in values:
        word = str(item).strip()
        if not word or word in result:
            continue
        if len(word) > 24 or re.search(r'[\s@:#]', word):
            raise ValueError('每个唤醒词不超过 24 个字符，且不能包含空格或 @ : #')
        result.append(word)
    if not result:
        raise ValueError('至少保留一个唤醒词')
    return result


def english_phones(word, lexicon):
    special = PRONUNCIATIONS.get(word.lower())
    if special and word.isascii():
        return special
    with open(lexicon, encoding='utf-8') as source:
        for line in source:
            parts = line.strip().split()
            if parts and parts[0].upper() == word.upper():
                return ' '.join(parts[1:])
    raise ValueError(f'英文唤醒词 {word} 不在发音词典中；Kimi 已内置，可直接使用')


def keyword_pronunciation(word, lexicon):
    special = PRONUNCIATIONS.get(word) or PRONUNCIATIONS.get(word.lower())
    if special:
        return special
    from pypinyin import Style, pinyin
    pieces = []
    for part in re.findall(r'[\u3400-\u9fff]|[A-Za-z]+', word):
        if part.isascii():
            pieces.append(english_phones(part, lexicon))
            continue
        initials = pinyin(part, style=Style.INITIALS, strict=False, errors='ignore')
        finals = pinyin(part, style=Style.FINALS_TONE, strict=False, errors='ignore')
        if not initials or not finals or not finals[0][0]:
            raise ValueError('暂时无法确定唤醒词发音：' + part)
        for initial, final in zip(initials, finals):
            pieces.extend((initial[0], final[0]))
    if len(''.join(re.findall(r'[\u3400-\u9fff]|[A-Za-z]+', word))) != len(word):
        raise ValueError('唤醒词目前只支持中文和英文字母：' + word)
    return ' '.join(piece for piece in pieces if piece)


def write_keywords(path, words, lexicon):
    lines = []
    for word in parse_wake_words(words):
        pronunciation = keyword_pronunciation(word, lexicon)
        lines.append(f'{pronunciation} :1.0 #0.25 @{word}')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    os.replace(temporary, path)
    return path


def is_cancel_phrase(text):
    normalized = re.sub(r'[\s，。！？,.!?、~～]', '', text)
    return normalized in CANCEL_PHRASES


class VoiceWorker(QThread):
    state = Signal(str, str)
    recognized = Signal(str)
    failed = Signal(str)

    def __init__(self, wake_words, silence_seconds=1.2, root=None, parent=None):
        super().__init__(parent)
        self.wake_words = wake_words
        self.silence_seconds = max(0.6, min(3.0, float(silence_seconds)))
        self.root = Path(root) if root else model_root()
        self.cancel = threading.Event()
        self.paused = threading.Event()
        self.followup_request = threading.Event()
        self.followup_seconds = 20.0

    def set_paused(self, value):
        if value:
            self.followup_request.clear()
            self.paused.set()
        else:
            self.paused.clear()

    def start_followup(self, seconds):
        self.followup_seconds = max(5.0, min(120.0, float(seconds)))
        self.followup_request.set()
        self.paused.clear()

    def stop(self):
        self.cancel.set()
        self.followup_request.clear()
        self.paused.clear()

    def make_vad(self, sherpa_onnx, paths):
        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(paths['vad'])
        config.silero_vad.min_silence_duration = self.silence_seconds
        config.silero_vad.min_speech_duration = 0.2
        config.silero_vad.max_speech_duration = 50.0
        config.sample_rate = SAMPLE_RATE
        return sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=65)

    def run(self):
        try:
            import numpy as np
            import sherpa_onnx
            import sounddevice as sd
            paths = model_paths(self.root)
            keywords = write_keywords(self.root / 'keywords.txt', self.wake_words, paths['lexicon'])
            self.state.emit('loading', '正在准备本地语音模型…')
            spotter = sherpa_onnx.KeywordSpotter(
                tokens=str(paths['kws_tokens']), encoder=str(paths['encoder']),
                decoder=str(paths['decoder']), joiner=str(paths['joiner']),
                num_threads=1, max_active_paths=4, keywords_file=str(keywords),
                keywords_score=1.0, keywords_threshold=0.25,
                num_trailing_blanks=1, provider='cpu')
            recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(paths['asr_model']), tokens=str(paths['asr_tokens']),
                num_threads=2, use_itn=True, debug=False)
            stream = spotter.create_stream()
            vad = None
            pending = np.empty(0, dtype=np.float32)
            listening_since = 0.0
            heard_speech = False
            followup_deadline = None
            was_paused = False
            samples_per_read = SAMPLE_RATE // 10
            self.state.emit('waiting', '等待唤醒')
            with sd.InputStream(channels=1, dtype='float32', samplerate=SAMPLE_RATE) as microphone:
                while not self.cancel.is_set():
                    samples, overflowed = microphone.read(samples_per_read)
                    samples = samples.reshape(-1)
                    if self.paused.is_set():
                        if not was_paused:
                            stream = spotter.create_stream()
                            vad = None
                            followup_deadline = None
                            pending = np.empty(0, dtype=np.float32)
                            was_paused = True
                        continue
                    if was_paused:
                        stream = spotter.create_stream()
                        was_paused = False
                        if not self.followup_request.is_set():
                            self.state.emit('waiting', '等待唤醒')
                    if vad is None and self.followup_request.is_set():
                        self.followup_request.clear()
                        vad = self.make_vad(sherpa_onnx, paths)
                        pending = np.empty(0, dtype=np.float32)
                        listening_since = time.monotonic()
                        followup_deadline = listening_since + self.followup_seconds
                        heard_speech = False
                        self.state.emit('followup', '连续对话')
                    if vad is None:
                        stream.accept_waveform(SAMPLE_RATE, samples)
                        while spotter.is_ready(stream):
                            spotter.decode_stream(stream)
                            keyword = spotter.get_result(stream)
                            if keyword:
                                spotter.reset_stream(stream)
                                vad = self.make_vad(sherpa_onnx, paths)
                                pending = np.empty(0, dtype=np.float32)
                                listening_since = time.monotonic()
                                followup_deadline = None
                                heard_speech = False
                                self.state.emit('listening', '正在聆听')
                                break
                        if vad is None:
                            continue
                    pending = np.concatenate((pending, samples))
                    window_size = 512
                    while len(pending) >= window_size:
                        vad.accept_waveform(pending[:window_size])
                        if vad.is_speech_detected():
                            heard_speech = True
                        pending = pending[window_size:]
                    elapsed = time.monotonic() - listening_since
                    if elapsed >= 60:
                        vad.flush()
                    utterance = None
                    if not vad.empty():
                        utterance = vad.front.samples
                        vad.pop()
                    no_speech_limit = followup_deadline - listening_since if followup_deadline is not None else 8
                    if utterance is None and elapsed >= no_speech_limit and not heard_speech:
                        was_followup = followup_deadline is not None
                        vad = None
                        followup_deadline = None
                        stream = spotter.create_stream()
                        if was_followup:self.state.emit('waiting', '等待唤醒')
                        else:self.state.emit('timeout', '没有听到人声')
                        continue
                    if utterance is None:
                        continue
                    self.paused.set()
                    self.state.emit('recognizing', '正在识别')
                    speech = recognizer.create_stream()
                    speech.accept_waveform(SAMPLE_RATE, utterance)
                    recognizer.decode_stream(speech)
                    text = speech.result.text.strip()
                    vad = None
                    followup_deadline = None
                    stream = spotter.create_stream()
                    while microphone.read_available >= samples_per_read:
                        microphone.read(samples_per_read)
                    self.recognized.emit(text)
                    was_paused = True
        except Exception as error:
            if not self.cancel.is_set():
                self.failed.emit(str(error))


class VoiceController(QObject):
    def __init__(self, pet):
        super().__init__(pet)
        self.pet = pet
        self.worker = None
        self.busy = False

    def start(self):
        if self.worker and self.worker.isRunning():
            return
        missing = missing_models()
        if missing:
            raise RuntimeError('本地语音模型尚未安装，请先运行 python work/install_voice_models.py')
        self.worker = VoiceWorker(
            self.pet.settings.value('wakeWords', DEFAULT_WAKE_WORDS),
            self.pet.settings.value('voiceSilence', 1.2, type=float), parent=self)
        self.worker.set_paused(self.busy)
        self.worker.state.connect(self.changed)
        self.worker.recognized.connect(self.recognized)
        self.worker.failed.connect(self.failed)
        self.worker.start()

    def changed(self, state, detail):
        if state == 'listening':
            self.pet.begin_voice_listening()
        elif state == 'followup':
            self.pet.begin_voice_followup()
        elif state == 'recognizing':
            self.pet.end_voice_listening()
            self.pet.say('主人，我正在把声音转成文字…', 0)
        elif state == 'timeout':
            self.pet.end_voice_listening()
            self.pet.say('主人，我没有听到声音，先回去等你啦。', 3500)
        elif state == 'waiting':
            self.pet.end_voice_listening()

    def begin_followup(self):
        if not self.pet.settings.value('voiceFollowup', True, type=bool):
            self.set_busy(False)
            return
        seconds = self.pet.settings.value('voiceFollowupSeconds', 20, type=int)
        self.busy = False
        if self.worker and self.worker.isRunning():
            self.worker.start_followup(seconds)
        else:
            self.set_busy(False)

    def recognized(self, text):
        if not text:
            self.pet.say('唔，这次没有听清。可以再叫我一次吗？', 4000)
            self.set_busy(False)
            return
        if is_cancel_phrase(text):
            self.pet.say('好呀，主人，我在这里等你。', 3000)
            self.set_busy(False)
            return
        self.pet.submit_voice_prompt(text)

    def failed(self, error):
        self.pet.end_voice_listening()
        self.pet.say('语音输入暂时不可用：' + error, 10000)

    def set_busy(self, value):
        self.busy = bool(value)
        if self.worker:
            self.worker.set_paused(self.busy)

    def shutdown(self):
        worker = self.worker
        if not worker:
            return True
        worker.stop()
        worker.wait(8000)
        if not worker.isRunning():
            self.worker = None
            return True
        return False
