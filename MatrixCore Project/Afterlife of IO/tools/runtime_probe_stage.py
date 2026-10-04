from __future__ import annotations

"""Isolated runtime compatibility stages for Afterlife of IO.

Each stage runs in its own Python process.  If pygame/SDL terminates that child
process natively, the parent probe survives and records the Windows exit code.
"""

import json
import os
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYER_A = ROOT / "assets" / "source" / "layers" / "0a.png"
WALK_A = ROOT / "assets" / "source" / "layers" / "2awalk.png"

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def emit(stage: str, status: str = "PASS", **data) -> None:
    payload = {"stage": stage, "status": status, **data}
    print(json.dumps(payload, sort_keys=True), flush=True)


def pygame_info(pygame) -> dict:
    info = {
        "pygame_version": getattr(getattr(pygame, "version", None), "ver", "unknown"),
    }
    try:
        info["sdl_linked"] = list(pygame.get_sdl_version(linked=True))
        info["sdl_compiled"] = list(pygame.get_sdl_version(linked=False))
    except Exception as exc:
        info["sdl_version_error"] = f"{type(exc).__name__}: {exc}"
    try:
        info["image_extended"] = bool(pygame.image.get_extended())
    except Exception:
        pass
    return info


def stage_python() -> None:
    emit(
        "python",
        executable=sys.executable,
        version=sys.version,
        version_info=list(sys.version_info[:3]),
        architecture=platform.architecture()[0],
        machine=platform.machine(),
        platform=platform.platform(),
    )


def stage_import() -> None:
    import pygame
    emit("pygame_import", **pygame_info(pygame))


def stage_init() -> None:
    import pygame
    result = pygame.init()
    emit(
        "pygame_init",
        init_result=list(result),
        display_init=bool(pygame.display.get_init()),
        font_init=bool(pygame.font.get_init()),
        mixer_init=repr(pygame.mixer.get_init()),
        **pygame_info(pygame),
    )
    pygame.quit()


def stage_display() -> None:
    # Keep audio entirely out of the display probe.
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.display.init()
    screen = pygame.display.set_mode((640, 360), pygame.RESIZABLE)
    pygame.display.set_caption("Afterlife of IO Runtime Probe")
    screen.fill((18, 21, 25))
    pygame.draw.rect(screen, (210, 210, 210), (40, 40, 180, 80), 2)
    pygame.display.flip()
    deadline = time.monotonic() + 0.18
    while time.monotonic() < deadline:
        pygame.event.pump()
        time.sleep(0.01)
    emit(
        "display_plain",
        driver=pygame.display.get_driver(),
        size=list(screen.get_size()),
        bitsize=screen.get_bitsize(),
        flags=int(screen.get_flags()),
    )
    pygame.display.quit()


def stage_surface() -> None:
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.display.init()
    screen = pygame.display.set_mode((640, 360))
    src = pygame.Surface((256, 160), pygame.SRCALPHA, 32)
    src.fill((0, 0, 0, 0))
    pygame.draw.circle(src, (180, 220, 255, 170), (128, 80), 60)
    pygame.draw.rect(src, (245, 245, 245, 220), (40, 52, 176, 56), 2)
    scaled = pygame.transform.smoothscale(src, (512, 320))
    tinted = scaled.copy()
    tinted.fill((205, 225, 255, 220), special_flags=pygame.BLEND_RGBA_MULT)
    screen.fill((8, 10, 14))
    screen.blit(tinted, (64, 20), special_flags=pygame.BLEND_PREMULTIPLIED if hasattr(pygame, "BLEND_PREMULTIPLIED") else 0)
    pygame.display.flip()
    pygame.event.pump()
    emit(
        "surface_alpha_transform",
        src_bits=src.get_bitsize(),
        scaled_size=list(scaled.get_size()),
        surface_locked=bool(src.get_locked()),
    )
    pygame.display.quit()


def stage_image() -> None:
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.display.init()
    pygame.display.set_mode((640, 360))
    if not LAYER_A.is_file():
        raise FileNotFoundError(LAYER_A)
    raw = pygame.image.load(str(LAYER_A))
    converted = raw.convert_alpha()
    preview = pygame.transform.smoothscale(converted, (640, 184))
    emit(
        "png_load_convert_scale",
        file=LAYER_A.name,
        raw_size=list(raw.get_size()),
        converted_bits=converted.get_bitsize(),
        preview_size=list(preview.get_size()),
        extended=bool(pygame.image.get_extended()),
    )
    pygame.display.quit()


def stage_mask() -> None:
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.display.init()
    pygame.display.set_mode((64, 64))
    if not WALK_A.is_file():
        raise FileNotFoundError(WALK_A)
    surf = pygame.image.load(str(WALK_A)).convert_alpha()
    mask = pygame.mask.from_surface(surf, 70)
    emit(
        "walk_mask",
        file=WALK_A.name,
        size=list(mask.get_size()),
        count=int(mask.count()),
    )
    pygame.display.quit()


def stage_mixer() -> None:
    import pygame
    try:
        pygame.mixer.init()
        data = {
            "mixer_init": list(pygame.mixer.get_init() or ()),
            "audio_driver_env": os.environ.get("SDL_AUDIODRIVER"),
        }
        try:
            data["sdl_mixer_linked"] = list(pygame.mixer.get_sdl_mixer_version(linked=True))
            data["sdl_mixer_compiled"] = list(pygame.mixer.get_sdl_mixer_version(linked=False))
        except Exception as exc:
            data["sdl_mixer_version_error"] = f"{type(exc).__name__}: {exc}"
        emit("mixer", **data)
        pygame.mixer.quit()
    except Exception as exc:
        # Audio is explicitly optional in Afterlife of IO.  Record rather than
        # making a missing/locked device look like a core renderer failure.
        emit("mixer", status="SOFT_FAIL", error=f"{type(exc).__name__}: {exc}")


def stage_game_import() -> None:
    sys.path.insert(0, str(ROOT))
    import main
    emit("game_import", module=str(Path(main.__file__).resolve()))


def stage_game_smoke(safe: bool) -> None:
    sys.path.insert(0, str(ROOT))
    import main
    args = [str(ROOT / "main.py"), "--windowed", "--smoke-test"]
    if safe:
        args.append("--safe-mode")
    sys.argv = args
    rc = int(main.main() or 0)
    emit("game_smoke_safe" if safe else "game_smoke_normal", return_code=rc)


STAGES = {
    "python": stage_python,
    "pygame_import": stage_import,
    "pygame_init": stage_init,
    "display_plain": stage_display,
    "surface_alpha_transform": stage_surface,
    "png_load_convert_scale": stage_image,
    "walk_mask": stage_mask,
    "mixer": stage_mixer,
    "game_import": stage_game_import,
    "game_smoke_safe": lambda: stage_game_smoke(True),
    "game_smoke_normal": lambda: stage_game_smoke(False),
}


def main_cli() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in STAGES:
        print("usage: runtime_probe_stage.py <stage>", file=sys.stderr)
        print("stages:", ", ".join(STAGES), file=sys.stderr)
        return 2
    stage = sys.argv[1]
    try:
        STAGES[stage]()
        return 0
    except BaseException as exc:
        emit(stage, status="FAIL", error=f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    raise SystemExit(main_cli())
