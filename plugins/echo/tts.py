"""文字转语音（TTS）：使用 Qwen3-TTS-12Hz-1.7B-Base 生成音频，超 60 秒自动降级为文字。

参考音频放 `voice_ref/` 文件夹（项目根目录下），程序自动扫描首个 .wav/.mp3/.m4a 文件。
对应文字在 `llm_config.ini` 的 [tts] -> ref_text 配置。
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from .llm_ini import section_dict

logger = logging.getLogger(__name__)

_TTS_MODEL: object | None = None

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_VOICE_REF_DIR = _PROJECT_ROOT / "voice_ref"


def _truthy(raw: str | None, default: bool = False) -> bool:
    s = (raw or "").strip().lower()
    if not s:
        return default
    return s in ("1", "true", "yes", "on")


def _scan_voice_ref() -> tuple[str | None, str | None]:
    """扫描 voice_ref/ 文件夹，返回首个音频文件路径和扩展名。"""
    if not _VOICE_REF_DIR.is_dir():
        return None, None
    for ext in (".wav", ".mp3", ".m4a", ".ogg", ".flac"):
        files = sorted(_VOICE_REF_DIR.glob(f"*{ext}"))
        if files:
            return str(files[0].resolve()), ext
    return None, None


def _validate_voice_ref() -> tuple[bool, str]:
    """校验参考音频是否就绪。返回 (ok, message)。"""
    cfg = _tts_config()
    ref_text = (cfg.get("ref_text") or "").strip()
    explicit = (cfg.get("ref_audio") or "").strip()
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            return False, f"ref_audio 文件不存在: {explicit}"
        return True, f"使用显式 ref_audio: {p.name}"
    auto_path, _ = _scan_voice_ref()
    if not auto_path:
        return False, "voice_ref/ 文件夹为空或不存在，请放入音频文件并在 [tts] -> ref_text 配置文字"
    if not ref_text:
        return False, f"已找到参考音频: {Path(auto_path).name}，但 ref_text 未配置"
    return True, f"使用 voice_ref/{Path(auto_path).name}"


def _tts_enabled() -> bool:
    return _truthy(section_dict("tts").get("enabled"), False)


def _tts_config() -> dict[str, str]:
    return section_dict("tts")


def _wav_duration_seconds(wav_path: str) -> float:
    """返回 WAV 文件时长（秒）。失败返回 999。"""
    try:
        import wave as _wave
        with _wave.open(wav_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate <= 0:
                return 999
            return frames / rate
    except Exception as e:
        logger.warning("could not read WAV duration: %s", e)
        return 999


async def _load_tts_model() -> object | None:
    """懒加载 Qwen3-TTS。"""
    global _TTS_MODEL
    if _TTS_MODEL is not None:
        return _TTS_MODEL

    cfg = _tts_config()
    model_path = (cfg.get("model_path") or "").strip()
    if not model_path:
        logger.warning("TTS model_path not configured")
        return None

    model_dir = Path(model_path)
    if not model_dir.is_absolute():
        model_dir = _PROJECT_ROOT / model_dir
    if not model_dir.is_dir():
        logger.warning("TTS model_path not a directory: %s", model_dir)
        return None

    try:
        import torch
        from qwen_tts import Qwen3TTSModel
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        logger.info("Loading Qwen3-TTS from %s (device=%s, dtype=%s)", model_dir, device, dtype)
        model = Qwen3TTSModel.from_pretrained(str(model_dir), device_map=device, dtype=dtype)
        _TTS_MODEL = model
        logger.info("Qwen3-TTS loaded successfully")
        return model
    except ImportError:
        logger.warning("qwen-tts not installed")
        return None
    except Exception as e:
        logger.error("failed to load Qwen3-TTS: %s", e)
        return None


async def synthesize_speech(text: str) -> tuple[str, bool]:
    """
    合成语音。返回 (file_path, is_qq_format)：
      - file_path: WAV 文件路径，使用后由调用方删除
      - is_qq_format: True = QQ 可播放（silk/amr），False = WAV

    失败或超长返回 ("", False)。
    """
    cfg = _tts_config()
    max_dur = float(cfg.get("max_duration_seconds", "60"))
    language = (cfg.get("language") or "Chinese").strip()
    explicit_ref_audio = (cfg.get("ref_audio") or "").strip()
    ref_text = (cfg.get("ref_text") or "").strip()

    if not text or not text.strip():
        return "", False

    ref_audio = explicit_ref_audio
    if not ref_audio:
        auto_path, _ = _scan_voice_ref()
        ref_audio = auto_path or ""

    if not ref_audio:
        logger.info("TTS skipped: no reference audio")
        return "", False

    if not ref_text:
        logger.info("TTS skipped: ref_text not configured")
        return "", False

    model = await _load_tts_model()
    if model is None:
        return "", False

    try:
        import soundfile as sf
        wavs, sr = await asyncio.to_thread(
            lambda: model.generate_voice_clone(
                text=text,
                language=language,
                ref_audio=ref_audio,
                ref_text=ref_text,
            ),
        )
        wav = wavs[0]
        sample_rate = sr or 24000
    except Exception as e:
        logger.error("Qwen3-TTS synthesis failed: %s", e)
        return "", False

    # 写临时 WAV
    tmp_path = tempfile.mktemp(suffix=".wav")
    try:
        sf.write(tmp_path, wav, sample_rate)
    except Exception as e:
        logger.error("soundfile write failed: %s", e)
        return "", False

    duration = _wav_duration_seconds(tmp_path)
    logger.info("TTS generated audio: %.1f sec (limit=%.0f)", duration, max_dur)

    if duration > max_dur:
        logger.info("Audio too long (%.1f s > %.0f s), falling back to text", duration, max_dur)
        Path(tmp_path).unlink(missing_ok=True)
        return "", False

    return tmp_path, False


def cleanup_temp_file(path: str) -> None:
    """删除临时音频文件。"""
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def tts_is_available() -> bool:
    """TTS 是否可用。"""
    if not _tts_enabled():
        return False
    cfg = _tts_config()
    model_path = (cfg.get("model_path") or "").strip()
    if not model_path:
        return False
    p = Path(model_path)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    if not p.is_dir():
        return False
    ok, _ = _validate_voice_ref()
    return ok
